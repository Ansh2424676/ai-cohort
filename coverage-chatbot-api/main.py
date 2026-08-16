import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Generator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


# ============================================================
# PROJECT ROOT
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

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
    version="1.0.0"
)


# ============================================================
# SESSION STORE
# ============================================================

session_store: Dict[str, List[dict]] = {}


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):

    session_id: str

    member_id: str

    message: str


# ============================================================
# ROOT / HEALTH CHECK
# ============================================================

@app.get("/")
def root():

    return {
        "message": "Coverage Chatbot API is running"
    }


# ============================================================
# DAY 19 - CITATION BUILDER
# ============================================================

def build_citation_ids(context):

    if isinstance(context, str):

        chunks = [
            chunk.strip()
            for chunk in context.split("\n")
            if chunk.strip()
        ]

    else:

        chunks = list(context)

    return [
        f"chunk-{index}"
        for index in range(
            1,
            len(chunks) + 1
        )
    ]


# ============================================================
# DAY 19 - RICH OUTPUT BUILDER
# ============================================================

def build_rich_outputs(question):

    question_lower = question.lower()

    outputs = {}

    # --------------------------------------------------------
    # Claim Status Card
    # --------------------------------------------------------

    if (
        "claim" in question_lower
        or "status" in question_lower
    ):

        claim_card = ClaimStatusCard(
            claim_id="CLM-1001",
            status="Approved",
            amount=1250.00,
            date="2026-08-16"
        )

        outputs["claim_status_card"] = (
            claim_card.model_dump()
        )


    # --------------------------------------------------------
    # Coverage Summary Card
    # --------------------------------------------------------

    if (
        "coverage" in question_lower
        or "covered" in question_lower
        or "maternity" in question_lower
    ):

        coverage_card = CoverageSummaryCard(
            plan_name="Gold Health Plan",
            deductible=1000.00,
            copay=25.00,
            covered=True
        )

        outputs["coverage_summary_card"] = (
            coverage_card.model_dump()
        )

    return outputs


# ============================================================
# SSE STREAM GENERATOR
# ============================================================

def generate_stream(
    request: ChatRequest
) -> Generator[str, None, None]:

    start_time = time.time()

    try:

        # ----------------------------------------------------
        # Create session
        # ----------------------------------------------------

        if request.session_id not in session_store:

            session_store[
                request.session_id
            ] = []


        # ----------------------------------------------------
        # Store user message
        # ----------------------------------------------------

        session_store[
            request.session_id
        ].append(
            {
                "role": "user",
                "message": request.message
            }
        )


        # ----------------------------------------------------
        # Day 10 - Retrieval
        # ----------------------------------------------------

        context = retrieve(
            request.message
        )


        # ----------------------------------------------------
        # Day 19 - Citation IDs
        # ----------------------------------------------------

        citation_chunk_ids = build_citation_ids(
            context
        )


        # ----------------------------------------------------
        # Day 13 - Tool Calling / LLM
        # ----------------------------------------------------

        enhanced_question = f"""

Member / Plan ID:
{request.member_id}

User question:
{request.message}

Retrieved coverage context:
{context}

Use the available tools and retrieved information
to answer the user's question accurately.

Consider the member / plan ID when relevant.

Do not invent information.
"""


        # ----------------------------------------------------
        # Generate answer using existing pipeline
        # ----------------------------------------------------

        answer = ask_with_tools(
            enhanced_question
        )


        # ----------------------------------------------------
        # Store assistant response
        # ----------------------------------------------------

        session_store[
            request.session_id
        ].append(
            {
                "role": "assistant",
                "message": answer
            }
        )


        # ----------------------------------------------------
        # Stream answer in small chunks
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

            yield f"data: {chunk}\n\n"

            time.sleep(0.03)


        # ----------------------------------------------------
        # Day 19 - Citation Metadata
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
        # Day 19 - Rich Cards
        # ----------------------------------------------------

        rich_outputs = build_rich_outputs(
            request.message
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
        # Completion event
        # ----------------------------------------------------

        elapsed = round(
            time.time() - start_time,
            3
        )

        yield (
            f"data: [DONE] "
            f"{elapsed}s\n\n"
        )


        # ----------------------------------------------------
        # Console log
        # ----------------------------------------------------

        print(
            f"[CHAT] "
            f"session={request.session_id} "
            f"member={request.member_id} "
            f"time={elapsed}s"
        )


    except Exception as error:

        elapsed = round(
            time.time() - start_time,
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
# POST /chat - SSE STREAMING
# ============================================================

@app.post("/chat")
def chat(request: ChatRequest):

    return StreamingResponse(

        generate_stream(request),

        media_type="text/event-stream",

        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================
# GET /history/{session_id}
# ============================================================

@app.get("/history/{session_id}")
def get_history(
    session_id: str
):

    history = session_store.get(
        session_id,
        []
    )

    return {

        "session_id":
            session_id,

        "messages":
            history
    }
