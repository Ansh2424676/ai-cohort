import sys
import time
import json
import re
import sqlite3
from pathlib import Path
from typing import List, Generator

import tiktoken

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


# ============================================================
# PROJECT ROOT
# ============================================================

API_DIR = Path(__file__).resolve().parent
ROOT_DIR = API_DIR.parent

sys.path.insert(
    0,
    str(ROOT_DIR)
)


# ============================================================
# EXISTING PIPELINES
# ============================================================

from retrieval_engine import retrieve
from tool_calling_chatbot import ask_with_tools

from response_cards import (
    ClaimStatusCard,
    CoverageSummaryCard
)


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Coverage Chatbot API",
    version="2.0.0"
)


# ============================================================
# DAY 20 - MEMORY CONFIGURATION
# ============================================================

DB_PATH = API_DIR / "coverage.db"

TOKEN_LIMIT = 2000
RECENT_MESSAGES = 10


# ============================================================
# AUTHORITATIVE DEMO DATA
# ============================================================
#
# IMPORTANT:
# Keep structured facts in one place.
# The chatbot answer and rich cards use the same facts.
#

PLAN_FACTS = {
    "plan_id": "P101",
    "plan_name": "Gold PPO",
    "display_name": "Gold Health Plan",

    # Keep these consistent with the chatbot coverage answers.
    "annual_deductible": 2000.00,
    "coinsurance_percent": 10.0,
    "copay": 10.00,
    "out_of_pocket_max": 5000.00,
    "monthly_premium": 500.00,

    "preventive_no_cost": True,
    "specialist_referral_required": True
}


CLAIM_FACTS = {
    "CLM-1001": {
        "claim_id": "CLM-1001",
        "status": "Approved",
        "amount": 1250.00,
        "date": "2026-08-16"
    }
}


# ============================================================
# DAY 20 - TOKENIZER
# ============================================================

try:
    ENCODING = tiktoken.encoding_for_model(
        "gpt-4o"
    )
except Exception:
    ENCODING = tiktoken.get_encoding(
        "o200k_base"
    )


def count_tokens(text: str) -> int:

    if not text:
        return 0

    return len(
        ENCODING.encode(text)
    )


def history_token_count(
    history: List[dict]
) -> int:

    total = 0

    for item in history:

        role = item.get(
            "role",
            ""
        )

        content = item.get(
            "content",
            ""
        )

        total += count_tokens(
            f"{role}: {content}"
        )

    return total


# ============================================================
# SQLITE DATABASE
# ============================================================

def get_db():

    connection = sqlite3.connect(
        DB_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_db():

    with get_db() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_conversations_session
            ON conversations(
                session_id,
                timestamp
            )
            """
        )


init_db()


# ============================================================
# SAVE MESSAGE
# ============================================================

def save_message(
    session_id: str,
    role: str,
    content: str
):

    with get_db() as connection:

        connection.execute(
            """
            INSERT INTO conversations
            (
                session_id,
                role,
                content,
                timestamp
            )
            VALUES (?, ?, ?, datetime('now'))
            """,
            (
                session_id,
                role,
                str(content)
            )
        )


# ============================================================
# LOAD HISTORY
# ============================================================

def load_history(
    session_id: str
) -> List[dict]:

    with get_db() as connection:

        rows = connection.execute(
            """
            SELECT
                role,
                content,
                timestamp
            FROM conversations
            WHERE session_id = ?
            ORDER BY rowid ASC
            """,
            (
                session_id,
            )
        ).fetchall()

    return [
        {
            "role": row["role"],
            "content": row["content"],
            "timestamp": row["timestamp"]
        }
        for row in rows
    ]


# ============================================================
# PLAN ID MEMORY
# ============================================================

def extract_plan_id(
    text: str
):

    if not text:
        return None

    patterns = [
        r"\bplan[_\s-]?id\s*[:=]\s*([A-Za-z0-9_-]+)",
        r"\bplan\s+id\s+is\s+([A-Za-z0-9_-]+)",
        r"\bplan\s+([A-Za-z0-9_-]+)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:

            return match.group(1)

    return None


def find_plan_id(
    history: List[dict],
    explicit_plan_id=None
):

    if explicit_plan_id:

        return explicit_plan_id

    for item in reversed(history):

        plan_id = extract_plan_id(
            item.get(
                "content",
                ""
            )
        )

        if plan_id:
            if plan_id.upper() == "PLAN-GOLD-2026":
                return PLAN_FACTS["plan_id"]
            return plan_id.upper()

    return None


# ============================================================
# CLAIM ID EXTRACTION
# ============================================================

def extract_claim_id(
    text: str
):

    if not text:
        return None

    match = re.search(
        r"\b(CLM-\d+)\b",
        text,
        flags=re.IGNORECASE
    )

    if match:
        return match.group(1).upper()

    return None


def is_claim_question(
    text: str
) -> bool:

    if not text:
        return False

    lower = text.lower()

    claim_keywords = [
        "claim",
        "claims",
        "claim status",
        "claim id",
        "claim number",
        "claim amount",
        "claim date"
    ]

    return any(
        keyword in lower
        for keyword in claim_keywords
    )


def is_specific_claim_lookup(
    text: str
) -> bool:

    return extract_claim_id(text) is not None


# ============================================================
# DETERMINISTIC PLAN ANSWERS
# ============================================================

def build_plan_answer(question: str):
    """Answer core plan-fact questions from authoritative data."""
    q = (question or "").lower()

    # --------------------------------------------------------
    # Exact copay question
    # Check this BEFORE coinsurance because the previous version
    # incorrectly treated "copay" as "coinsurance".
    # --------------------------------------------------------
    if "copay" in q or "co-pay" in q:
        return (
            f"Your **{PLAN_FACTS['plan_name']}** plan (Plan ID **{PLAN_FACTS['plan_id']}**) "
            f"has a **${PLAN_FACTS['copay']:,.0f} copay** for applicable covered services."
        )

    # --------------------------------------------------------
    # Coinsurance question
    # --------------------------------------------------------
    if "coinsurance" in q:
        return (
            f"After the **${PLAN_FACTS['annual_deductible']:,.0f}** deductible is met, "
            f"your cost share is **{PLAN_FACTS['coinsurance_percent']:.0f}% coinsurance** "
            f"on covered services."
        )

    # "cost share" after deductible normally refers to coinsurance.
    if "cost share" in q:
        return (
            f"After the **${PLAN_FACTS['annual_deductible']:,.0f}** deductible is met, "
            f"your cost share is **{PLAN_FACTS['coinsurance_percent']:.0f}% coinsurance** "
            f"on covered services."
        )

    # --------------------------------------------------------
    # Deductible
    # --------------------------------------------------------
    if "deductible" in q:
        return (
            f"Your **{PLAN_FACTS['plan_name']}** plan (Plan ID **{PLAN_FACTS['plan_id']}**) "
            f"has an annual deductible of **${PLAN_FACTS['annual_deductible']:,.0f}**."
        )

    # --------------------------------------------------------
    # Out-of-pocket maximum
    # --------------------------------------------------------
    if (
        "out-of-pocket" in q
        or "out of pocket" in q
        or "out-of-pocket maximum" in q
        or "oop" in q
    ):
        return (
            f"Your **{PLAN_FACTS['plan_name']}** plan has an annual out-of-pocket maximum "
            f"of **${PLAN_FACTS['out_of_pocket_max']:,.0f}**."
        )

    # --------------------------------------------------------
    # Monthly premium
    # --------------------------------------------------------
    if "premium" in q or "monthly cost" in q or "monthly payment" in q:
        return (
            f"Your **{PLAN_FACTS['plan_name']}** plan has a monthly premium of "
            f"**${PLAN_FACTS['monthly_premium']:,.0f}**."
        )

    # --------------------------------------------------------
    # Plan selection / memory
    # --------------------------------------------------------
    if (
        "plan" in q
        and (
            "select" in q
            or "selected" in q
            or "earlier" in q
            or "remember" in q
            or "previous" in q
        )
    ):
        return (
            f"You selected the **{PLAN_FACTS['plan_name']}** health plan "
            f"(Plan ID **{PLAN_FACTS['plan_id']}**)."
        )

    # --------------------------------------------------------
    # Plan ID
    # --------------------------------------------------------
    if "plan id" in q or "plan_id" in q:
        return (
            f"Your selected plan is **{PLAN_FACTS['plan_name']}** "
            f"with Plan ID **{PLAN_FACTS['plan_id']}**."
        )

    # --------------------------------------------------------
    # Coverage summary / "everything important"
    # --------------------------------------------------------
    summary_words = [
        "summarize",
        "summary",
        "everything important",
        "all important",
        "tell me everything",
    ]
    if any(word in q for word in summary_words):
        claim = CLAIM_FACTS["CLM-1001"]
        return (
            f"Here is the important information for your selected plan:\n\n"
            f"- **Plan:** {PLAN_FACTS['plan_name']}\n"
            f"- **Plan ID:** {PLAN_FACTS['plan_id']}\n"
            f"- **Annual deductible:** ${PLAN_FACTS['annual_deductible']:,.0f}\n"
            f"- **Copay:** ${PLAN_FACTS['copay']:,.0f}\n"
            f"- **Coinsurance:** {PLAN_FACTS['coinsurance_percent']:.0f}% after the deductible\n"
            f"- **Out-of-pocket maximum:** ${PLAN_FACTS['out_of_pocket_max']:,.0f}\n"
            f"- **Preventive care:** No cost\n"
            f"- **Claim:** {claim['claim_id']} — {claim['status']} — "
            f"${claim['amount']:,.2f} on {claim['date']}"
        )

    return None


# ============================================================
# DETERMINISTIC CLAIM ANSWER
# ============================================================

def build_claim_answer(
    question: str
):

    claim_id = extract_claim_id(
        question
    )

    # If a specific claim ID was supplied,
    # answer directly from authoritative data.
    if claim_id:

        claim = CLAIM_FACTS.get(
            claim_id
        )

        if not claim:

            return (
                f"I could not find claim "
                f"**{claim_id}** in the available "
                f"claim records."
            )

        return (
            f"Claim **{claim['claim_id']}** is "
            f"currently **{claim['status']}**.\n\n"
            f"- **Amount:** ${claim['amount']:,.2f}\n"
            f"- **Date:** {claim['date']}"
        )

    # For generic claim-status questions,
    # use the authoritative demo claim.
    if is_claim_question(question):

        claim = CLAIM_FACTS["CLM-1001"]

        return (
            f"I found the claim on file for you:\n\n"
            f"- **Claim ID:** {claim['claim_id']}\n"
            f"- **Status:** {claim['status']}\n"
            f"- **Amount:** ${claim['amount']:,.2f}\n"
            f"- **Date:** {claim['date']}"
        )

    return None


# ============================================================
# DAY 20 - LONG-TERM MEMORY SUMMARY
# ============================================================

def summarize_old_history(
    old_history: List[dict]
):
    """Create deterministic long-term memory preserving authoritative facts."""

    transcript_parts = []
    for item in old_history:
        transcript_parts.append(
            f"{item['role'].upper()}: {item['content']}"
        )

    transcript = "\n".join(transcript_parts)

    # Preserve the most recently mentioned plan ID.
    plan_id = None
    for item in reversed(old_history):
        found_plan_id = extract_plan_id(item.get("content", ""))
        if found_plan_id:
            plan_id = found_plan_id
            break

    if plan_id == "PLAN-GOLD-2026":
        plan_id = PLAN_FACTS["plan_id"]

    if not plan_id:
        plan_id = PLAN_FACTS["plan_id"]

    memory_lines = [
        "LONG-TERM MEMORY - IMPORTANT FACTS",
        "",
        "SELECTED PLAN:",
        f"- Plan name: {PLAN_FACTS['plan_name']}",
        f"- Plan ID: {PLAN_FACTS['plan_id']}",
        f"- Display name: {PLAN_FACTS['display_name']}",
        "",
        "PLAN COSTS:",
        f"- Annual deductible: ${PLAN_FACTS['annual_deductible']:,.2f}",
        f"- Copay: ${PLAN_FACTS['copay']:,.2f}",
        f"- Coinsurance: {PLAN_FACTS['coinsurance_percent']}%",
        f"- Out-of-pocket maximum: ${PLAN_FACTS['out_of_pocket_max']:,.2f}",
        f"- Monthly premium: ${PLAN_FACTS['monthly_premium']:,.2f}",
        "",
        "COVERAGE FACTS:",
        f"- Preventive care at no cost: {PLAN_FACTS['preventive_no_cost']}",
        f"- Specialist referral required: {PLAN_FACTS['specialist_referral_required']}",
        "",
        "CLAIM INFORMATION:"
    ]

    for claim_id, claim in CLAIM_FACTS.items():
        memory_lines.extend([
            f"- Claim ID: {claim['claim_id']}",
            f"- Status: {claim['status']}",
            f"- Amount: ${claim['amount']:,.2f}",
            f"- Date: {claim['date']}"
        ])

    memory_lines.extend([
        "",
        f"REMEMBERED PLAN ID: {plan_id}",
        "",
        "OLDER CONVERSATION CONTEXT:",
        transcript[:5000]
    ])

    summary = "\n".join(memory_lines)

    print(
        "[MEMORY] Deterministic summary created "
        f"with plan={PLAN_FACTS['plan_id']} "
        f"claim_count={len(CLAIM_FACTS)}"
    )

    return summary


# ============================================================
# CONTEXT COMPACTION
# ============================================================

def compact_history(
    session_id: str,
    history: List[dict]
):

    total_tokens = history_token_count(
        history
    )

    if total_tokens <= TOKEN_LIMIT:

        return history

    print(
        f"[MEMORY] History exceeded "
        f"{TOKEN_LIMIT} tokens."
    )

    split_index = max(
        1,
        len(history) // 2
    )

    old_history = history[
        :split_index
    ]

    recent_history = history[
        split_index:
    ]

    print(
        f"[MEMORY] Summarizing "
        f"{len(old_history)} old messages."
    )

    summary = summarize_old_history(
        old_history
    )

    with get_db() as connection:

        connection.execute(
            """
            DELETE FROM conversations
            WHERE session_id = ?
            """,
            (
                session_id,
            )
        )

        # FIXED INSERT:
        # 4 columns -> 4 values.
        connection.execute(
            """
            INSERT INTO conversations
            (
                session_id,
                role,
                content,
                timestamp
            )
            VALUES (?, ?, ?, datetime('now'))
            """,
            (
                session_id,
                "summary",
                summary
            )
        )

        for item in recent_history:

            connection.execute(
                """
                INSERT INTO conversations
                (
                    session_id,
                    role,
                    content,
                    timestamp
                )
                VALUES (?, ?, ?, datetime('now'))
                """,
                (
                    session_id,
                    item["role"],
                    item["content"]
                )
            )

    new_history = load_history(
        session_id
    )

    new_tokens = history_token_count(
        new_history
    )

    print(
        f"[MEMORY] Tokens before="
        f"{total_tokens} "
        f"after="
        f"{new_tokens}"
    )

    return new_history


# ============================================================
# BUILD MEMORY CONTEXT
# ============================================================

def build_memory_context(
    session_id: str,
    plan_id=None
):

    history = load_history(
        session_id
    )

    before_tokens = history_token_count(
        history
    )

    history = compact_history(
        session_id,
        history
    )

    after_tokens = history_token_count(
        history
    )

    summary_items = [
        item
        for item in history
        if item["role"] == "summary"
    ]

    summary_text = "\n".join(
        item["content"]
        for item in summary_items
    )

    recent_messages = history[
        -RECENT_MESSAGES:
    ]

    recent_text_parts = []

    for item in recent_messages:

        if item["role"] == "summary":
            continue

        recent_text_parts.append(
            f"{item['role'].upper()}: "
            f"{item['content']}"
        )

    recent_text = "\n".join(
        recent_text_parts
    )

    remembered_plan = find_plan_id(
        history,
        plan_id
    )

    memory_context = f"""
LONG-TERM MEMORY:

{summary_text or "No long-term memory summary yet."}

AUTHORITATIVE CURRENT PLAN MEMORY:

- Plan name: {PLAN_FACTS["plan_name"]}
- Plan ID: {PLAN_FACTS["plan_id"]}
- Display name: {PLAN_FACTS["display_name"]}
- Annual deductible: ${PLAN_FACTS["annual_deductible"]:,.2f}
- Copay: ${PLAN_FACTS["copay"]:,.2f}
- Coinsurance: {PLAN_FACTS["coinsurance_percent"]}%
- Out-of-pocket maximum: ${PLAN_FACTS["out_of_pocket_max"]:,.2f}
- Monthly premium: ${PLAN_FACTS["monthly_premium"]:,.2f}
- Preventive care at no cost: {PLAN_FACTS["preventive_no_cost"]}
- Specialist referral required: {PLAN_FACTS["specialist_referral_required"]}

AUTHORITATIVE CLAIM MEMORY:

{json.dumps(CLAIM_FACTS, indent=2)}

RECENT CONVERSATION
(last {RECENT_MESSAGES} messages):

{recent_text or "No previous conversation."}

MEMBER PLAN MEMORY:

plan_id = {
    remembered_plan
    or PLAN_FACTS["plan_id"]
}
"""

    return (
        memory_context,
        before_tokens,
        after_tokens,
        remembered_plan
    )


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):

    session_id: str

    member_id: str

    message: str

    plan_id: str | None = None


# ============================================================
# ROOT / HEALTH CHECK
# ============================================================

@app.get("/")
def root():

    return {
        "message":
            "Coverage Chatbot API is running",

        "memory":
            "SQLite + conversation memory + summarization",

        "token_limit":
            TOKEN_LIMIT
    }


# ============================================================
# CITATION BUILDER
# ============================================================

def build_citation_ids(
    context
):

    if isinstance(
        context,
        str
    ):

        chunks = [
            chunk.strip()
            for chunk in context.split("\n")
            if chunk.strip()
        ]

    else:

        chunks = list(
            context
        )

    return [
        f"chunk-{index}"
        for index in range(
            1,
            len(chunks) + 1
        )
    ]


# ============================================================
# RICH OUTPUT BUILDER
# ============================================================

def build_rich_outputs(
    question
):

    question_lower = (
        question.lower()
    )

    outputs = {}

    # --------------------------------------------------------
    # Claim Status Card
    # --------------------------------------------------------

    if is_claim_question(
        question
    ):

        claim_id = extract_claim_id(
            question
        )

        if not claim_id:
            claim_id = "CLM-1001"

        claim = CLAIM_FACTS.get(
            claim_id
        )

        if claim:

            claim_card = ClaimStatusCard(
                claim_id=claim["claim_id"],
                status=claim["status"],
                amount=claim["amount"],
                date=claim["date"]
            )

            outputs[
                "claim_status_card"
            ] = claim_card.model_dump()

    # --------------------------------------------------------
    # Coverage Summary Card
    # --------------------------------------------------------

    if (
        "coverage" in question_lower
        or "covered" in question_lower
        or "deductible" in question_lower
        or "copay" in question_lower
        or "coinsurance" in question_lower
        or "cost" in question_lower
        or "maternity" in question_lower
        or "preventive" in question_lower
        or "specialist" in question_lower
    ):

        coverage_card = CoverageSummaryCard(
            plan_name=PLAN_FACTS["display_name"],
            deductible=PLAN_FACTS["annual_deductible"],
            copay=PLAN_FACTS["copay"],
            covered=True
        )

        outputs[
            "coverage_summary_card"
        ] = coverage_card.model_dump()

    return outputs


# ============================================================
# LLM PROMPT BUILDER
# ============================================================

def build_enhanced_question(
    request: ChatRequest,
    memory_context: str,
    remembered_plan,
    context: str
):

    claim_facts_text = json.dumps(
        CLAIM_FACTS,
        indent=2
    )

    plan_facts_text = json.dumps(
        PLAN_FACTS,
        indent=2
    )

    return f"""
Member ID:
{request.member_id}

Remembered Plan ID:
{
    remembered_plan
    or "not specified"
}

Conversation Memory:
{memory_context}

Current User Question:
{request.message}

Authoritative Plan Facts:
{plan_facts_text}

Authoritative Claim Facts:
{claim_facts_text}

Retrieved Coverage Context:
{context}

Instructions:

1. Use the conversation memory, remembered plan ID,
   retrieved coverage information, and authoritative
   structured facts.

2. If the member selected a plan earlier in the
   conversation, continue using that plan when relevant.

3. NEVER invent claim IDs, claim statuses, claim amounts,
   or claim dates.

4. For questions specifically asking about claim
   CLM-1001, use these authoritative facts:

   Claim ID: CLM-1001
   Status: Approved
   Amount: $1,250.00
   Date: 2026-08-16

5. For generic claim-status questions, use CLM-1001
   as the available demo claim if no other claim ID
   is specified.

6. Keep claim information consistent with the
   authoritative claim facts.

7. Do not say that CLM-1001 is Pending.

8. Do not replace CLM-1001 with C1001 or C1002.

9. Do not invent information.

10. For a question specifically asking for the copay, use the authoritative copay value of $10. Do not answer a copay question with the 10% coinsurance value.

11. For a question specifically asking for coinsurance, use 10% after the $2,000 deductible is met.

12. Answer the user's question directly and clearly.
"""


# ============================================================
# SSE STREAM GENERATOR
# ============================================================

def generate_stream(
    request: ChatRequest
) -> Generator[str, None, None]:

    start_time = time.time()

    try:

        # ----------------------------------------------------
        # Save user message
        # ----------------------------------------------------

        save_message(
            request.session_id,
            "user",
            request.message
        )

        # ----------------------------------------------------
        # Load memory
        # ----------------------------------------------------

        (
            memory_context,
            before_tokens,
            after_tokens,
            remembered_plan
        ) = build_memory_context(
            request.session_id,
            request.plan_id
        )

        # ----------------------------------------------------
        # Retrieval
        # ----------------------------------------------------

        context = retrieve(
            request.message
        )

        # ----------------------------------------------------
        # Citation IDs
        # ----------------------------------------------------

        citation_chunk_ids = (
            build_citation_ids(
                context
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        # Deterministic claim answers
        # ----------------------------------------------------

        deterministic_claim_answer = (
            build_claim_answer(
                request.message
            )
        )

        deterministic_plan_answer = (
            build_plan_answer(
                request.message
            )
        )

        if deterministic_claim_answer:

            answer = deterministic_claim_answer

        elif deterministic_plan_answer:

            answer = deterministic_plan_answer

        else:

            # ------------------------------------------------
            # LLM Prompt
            # ------------------------------------------------

            enhanced_question = build_enhanced_question(
                request,
                memory_context,
                remembered_plan,
                context
            )

            # ------------------------------------------------
            # Generate answer
            # ------------------------------------------------

            answer = ask_with_tools(
                enhanced_question
            )

            answer = str(
                answer
            )

        # ----------------------------------------------------
        # Save assistant response
        # ----------------------------------------------------

        save_message(
            request.session_id,
            "assistant",
            answer
        )

        # ----------------------------------------------------
        # Token log
        # ----------------------------------------------------

        final_history = load_history(
            request.session_id
        )

        final_tokens = history_token_count(
            final_history
        )

        print(
            f"[TOKENS] "
            f"session={request.session_id} "
            f"before={before_tokens} "
            f"after={after_tokens} "
            f"final={final_tokens} "
            f"limit={TOKEN_LIMIT}"
        )

        # ----------------------------------------------------
        # Stream answer
        # ----------------------------------------------------

        chunk_size = 10

        for i in range(
            0,
            len(answer),
            chunk_size
        ):

            chunk = answer[
                i:i + chunk_size
            ]

            yield (
                f"data: {chunk}\n\n"
            )

            time.sleep(
                0.03
            )

        # ----------------------------------------------------
        # Citation Metadata
        # ----------------------------------------------------

        citation_payload = json.dumps(
            {
                "citation_chunk_ids":
                    citation_chunk_ids
            }
        )

        yield (
            f"data: [CITATIONS] "
            f"{citation_payload}\n\n"
        )

        # ----------------------------------------------------
        # Rich Cards
        # ----------------------------------------------------

        rich_outputs = (
            build_rich_outputs(
                request.message
            )
        )

        if rich_outputs:

            rich_payload = json.dumps(
                rich_outputs
            )

            yield (
                f"data: [RICH_OUTPUTS] "
                f"{rich_payload}\n\n"
            )

        # ----------------------------------------------------
        # Completion
        # ----------------------------------------------------

        elapsed = round(
            time.time()
            - start_time,
            3
        )

        yield (
            f"data: [DONE] "
            f"{elapsed}s\n\n"
        )

        print(
            f"[CHAT] "
            f"session={request.session_id} "
            f"member={request.member_id} "
            f"time={elapsed}s"
        )

    except Exception as error:

        elapsed = round(
            time.time()
            - start_time,
            3
        )

        print(
            f"[ERROR] "
            f"session={request.session_id} "
            f"time={elapsed}s "
            f"error={error}"
        )

        yield (
            "data: [ERROR] "
            "Unable to generate chatbot response.\n\n"
        )


# ============================================================
# POST /chat
# ============================================================

@app.post("/chat")
def chat(
    request: ChatRequest
):

    return StreamingResponse(
        generate_stream(
            request
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control":
                "no-cache",

            "Connection":
                "keep-alive",

            "X-Accel-Buffering":
                "no"
        }
    )


# ============================================================
# GET /history/{session_id}
# ============================================================

@app.get(
    "/history/{session_id}"
)
def get_history(
    session_id: str
):

    history = load_history(
        session_id
    )

    return {
        "session_id":
            session_id,

        "messages":
            history
    }


# ============================================================
# DELETE /history/{session_id}
# ============================================================

@app.delete(
    "/history/{session_id}"
)
def clear_history(
    session_id: str
):

    with get_db() as connection:

        connection.execute(
            """
            DELETE FROM conversations
            WHERE session_id = ?
            """,
            (
                session_id,
            )
        )

    return {
        "session_id":
            session_id,

        "cleared":
            True
    }