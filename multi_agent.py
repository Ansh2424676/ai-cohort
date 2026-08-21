import os
import re
import sys
import sqlite3
import asyncio
from pathlib import Path
from typing import TypedDict, Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY not found. Please check your .env file."
    )


llm = ChatOpenAI(
    model=GROQ_MODEL,
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    temperature=0,
)


# ============================================================
# DAY 24 - MCP + MEMORY CONFIGURATION
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent
MCP_SERVER_PATH = ROOT_DIR / "mcp_server.py"
MEMORY_DB_PATH = ROOT_DIR / "coverage-chatbot-api" / "coverage.db"

TOOL_TIMEOUT_SECONDS = 10
MAX_RETRIES = 1
FALLBACK_MESSAGE = (
    "I'm having trouble accessing that right now, "
    "please contact member support."
)

DEFAULT_SESSION_ID = os.getenv(
    "DAY24_SESSION_ID",
    "day20-memory-test"
)


# ============================================================
# DAY 24 - DAY 20 MEMORY
# ============================================================

def load_memory_history(session_id: str):
    """Load Day 20 conversation history from SQLite."""
    if not MEMORY_DB_PATH.exists():
        print(f"[MEMORY] Database not found: {MEMORY_DB_PATH}")
        return []

    try:
        with sqlite3.connect(str(MEMORY_DB_PATH)) as connection:
            rows = connection.execute(
                """
                SELECT role, content, timestamp
                FROM conversations
                WHERE session_id = ?
                ORDER BY rowid ASC
                """,
                (session_id,),
            ).fetchall()

        return [
            {
                "role": row[0],
                "content": row[1],
                "timestamp": row[2],
            }
            for row in rows
        ]

    except Exception as error:
        print(f"[MEMORY] Could not load history: {error}")
        return []


def extract_memory_plan_id(text: str):
    """Extract and normalize the selected plan from Day 20 memory."""
    if not text:
        return None

    patterns = [
        r"\bplan[_\s-]?id\s*[:=]\s*([A-Za-z0-9_-]+)",
        r"\bplan\s+id\s+is\s+([A-Za-z0-9_-]+)",
        r"\bremembered\s+plan\s+id\s*[:=]\s*([A-Za-z0-9_-]+)",
        r"\b(P10[1-3])\b",
        r"\bPLAN-GOLD-2026\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            value = match.group(1) if match.lastindex else match.group(0)
            value = value.upper()

            if value == "PLAN-GOLD-2026":
                return "P101"

            return value

    return None


def build_day20_memory_context(session_id: str):
    """Build recent conversation + selected plan context for agents."""
    history = load_memory_history(session_id)

    selected_plan = None

    for item in reversed(history):
        found = extract_memory_plan_id(
            item.get("content", "")
        )
        if found:
            selected_plan = found
            break

    recent_messages = history[-10:]

    recent_text = "\n".join(
        f"{item['role'].upper()}: {item['content']}"
        for item in recent_messages
        if item["role"] != "summary"
    )

    summaries = "\n".join(
        item["content"]
        for item in history
        if item["role"] == "summary"
    )

    memory_context = f"""
DAY 20 CONVERSATION MEMORY

Session ID: {session_id}

REMEMBERED SELECTED PLAN:
{selected_plan or "P101"}

LONG-TERM MEMORY:
{summaries or "No long-term summary found."}

RECENT CONVERSATION:
{recent_text or "No previous conversation found."}
"""

    return memory_context, selected_plan or "P101"


# ============================================================
# DAY 24 - MCP CLIENT
# ============================================================

async def _call_mcp_tool_once(
    tool_name: str,
    arguments: dict,
):
    """Start mcp_server.py over STDIO and call one MCP tool."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(MCP_SERVER_PATH)],
        cwd=str(ROOT_DIR),
    )

    async with stdio_client(server_params) as (
        read_stream,
        write_stream,
    ):
        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            await session.initialize()

            result = await session.call_tool(
                tool_name,
                arguments,
            )

            if getattr(result, "is_error", False):
                raise RuntimeError(
                    f"MCP tool error: {result}"
                )

            output = []

            for content in getattr(
                result,
                "content",
                [],
            ):
                value = getattr(
                    content,
                    "text",
                    None,
                )
                if value:
                    output.append(value)

            if not output:
                return "MCP tool returned no text."

            return "\n".join(output).strip()


def call_mcp_tool_with_resilience(
    tool_name: str,
    arguments: dict,
):
    """
    Day 24 resilience:
    10-second timeout -> maximum 1 retry -> canned fallback.
    """

    last_error = None

    for attempt in range(MAX_RETRIES + 1):

        try:
            result = asyncio.run(
                asyncio.wait_for(
                    _call_mcp_tool_once(
                        tool_name,
                        arguments,
                    ),
                    timeout=TOOL_TIMEOUT_SECONDS,
                )
            )

            return result, False

        except Exception as error:
            last_error = error

            print(
                f"[MCP] {tool_name} failed "
                f"(attempt {attempt + 1}/{MAX_RETRIES + 1}): "
                f"{error}"
            )

            if attempt < MAX_RETRIES:
                print("[MCP] Retrying once...")

    print(
        f"[MCP] {tool_name} failed after retry: "
        f"{last_error}"
    )

    return FALLBACK_MESSAGE, True


# ============================================================
# GRAPH STATE
# ============================================================

class AgentState(TypedDict, total=False):
    question: str
    route: str
    answer: str
    session_id: str
    memory_context: str
    selected_plan: str


# ============================================================
# CLEAN MODEL OUTPUT
# ============================================================

def clean_answer(text: str) -> str:
    """
    Remove hidden reasoning / <think> blocks
    and accidental markdown fences from model output.
    """

    if not text:
        return ""

    # Remove <think>...</think> blocks
    text = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Remove any remaining think tags
    text = re.sub(
        r"</?think>",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove accidental markdown code fences
    text = text.replace("```text", "")
    text = text.replace("```", "")

    return text.strip()


# ============================================================
# ROUTER AGENT
# ============================================================

def router_agent(state: AgentState) -> AgentState:

    question = state["question"]

    question_lower = question.lower()
    question_upper = question.upper()

    # --------------------------------------------------------
    # CLAIMS
    # --------------------------------------------------------

    claim_id_found = re.search(
        r"\bCLM-\d+\b",
        question_upper,
    )

    claim_keywords = [
        "claim status",
        "claim approved",
        "claim denied",
        "claim pending",
        "claim processing",
        "claim processed",
        "my claim",
        "claim",
    ]

    if (
        claim_id_found
        or any(
            keyword in question_lower
            for keyword in claim_keywords
        )
    ):
        route = "claims"

    # --------------------------------------------------------
    # COVERAGE
    # --------------------------------------------------------

    elif (
        "P101" in question_upper
        or "P102" in question_upper
        or "P103" in question_upper
        or "mri" in question_lower
        or "physical therapy" in question_lower
        or "coverage" in question_lower
        or "covered" in question_lower
        or "deductible" in question_lower
        or "premium" in question_lower
        or "copay" in question_lower
        or "out-of-pocket" in question_lower
        or "out of pocket" in question_lower
        or "benefit" in question_lower
        or "benefits" in question_lower
        or "network" in question_lower
    ):
        route = "coverage"

    # --------------------------------------------------------
    # ENROLLMENT
    # --------------------------------------------------------

    elif (
        "enroll" in question_lower
        or "enrollment" in question_lower
        or "join a plan" in question_lower
        or "eligible to enroll" in question_lower
    ):
        route = "enrollment"

    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    else:
        route = "coverage"

    print()
    print("=" * 70)
    print("ROUTER AGENT")
    print("=" * 70)
    print("Question:", question)
    print("Selected route:", route)

    return {
        **state,
        "route": route,
    }


# ============================================================
# EXTRACT PLAN ID
# ============================================================

def extract_plan_id(question: str):

    match = re.search(
        r"\bP10[1-3]\b",
        question.upper(),
    )

    if match:
        return match.group(0)

    return None


# ============================================================
# EXTRACT CLAIM ID
# ============================================================

def extract_claim_id(question: str):

    match = re.search(
        r"\bCLM-\d+\b",
        question.upper(),
    )

    if match:
        return match.group(0)

    return None


# ============================================================
# COVERAGE SPECIALIST
# ============================================================

def coverage_specialist(state: AgentState) -> AgentState:

    question = state["question"]
    question_lower = question.lower()

    print()
    print("=" * 70)
    print("COVERAGE SPECIALIST")
    print("=" * 70)

    explicit_plan_id = extract_plan_id(question)
    remembered_plan = state.get(
        "selected_plan"
    ) or "P101"

    plan_id = explicit_plan_id or remembered_plan

    # Day 24: the Day 23 MCP server exposes check_coverage(question).
    # Pass the selected/remembered plan into the natural-language query.
    mcp_question = (
        f"{question}\n"
        f"Selected plan for this conversation: {plan_id}"
    )

    tool_result, tool_failed = call_mcp_tool_with_resilience(
        "check_coverage",
        {
            "question": mcp_question,
        },
    )

    if tool_failed:
        print("[MCP] Coverage fallback returned.")
        return {
            **state,
            "answer": FALLBACK_MESSAGE,
        }

    # --------------------------------------------------------
    # Generate answer
    # --------------------------------------------------------

    final_prompt = f"""
You are the Coverage Specialist in a healthcare
insurance multi-agent system.

Answer the user's question using ONLY the tool result.

IMPORTANT RULES:

1. Do not invent insurance information.
2. Do not invent percentages.
3. Do not invent prices.
4. Do not invent plan details.
5. Use the tool result as the source of truth.
6. If the tool result does not contain enough information,
   clearly say that the information cannot be confirmed.
7. Keep the answer short and clear.
8. Do not provide reasoning.
9. Do not provide analysis.
10. Do not use <think> tags.
11. Return ONLY the final answer.

User question:
{question}

Tool result:
{tool_result}
"""

    try:

        response = llm.invoke(
            [
                SystemMessage(content=final_prompt),
                HumanMessage(content=question),
            ]
        )

        answer = clean_answer(
            response.content
        )

    except Exception as error:

        if tool_failed:
            answer = FALLBACK_MESSAGE
        else:
            answer = (
                "I'm unable to generate the final answer "
                "right now. Please contact member support."
            )

    print("Tool result:", tool_result)
    print()
    print("Answer:", answer)

    return {
        **state,
        "answer": answer,
    }


# ============================================================
# CLAIMS SPECIALIST
# ============================================================

def claims_specialist(state: AgentState) -> AgentState:

    question = state["question"]

    print()
    print("=" * 70)
    print("CLAIMS SPECIALIST")
    print("=" * 70)

    claim_id = extract_claim_id(question)

    # --------------------------------------------------------
    # Day 24: call the real Day 23 MCP claim tool.
    # --------------------------------------------------------

    if claim_id:
        tool_result, tool_failed = call_mcp_tool_with_resilience(
            "get_claim_status",
            {
                "claim_id": claim_id,
            },
        )
    else:
        tool_result = "No valid claim ID was found."
        tool_failed = False

    if tool_failed:
        print("[MCP] Claim fallback returned.")
        return {
            **state,
            "answer": FALLBACK_MESSAGE,
        }

    # --------------------------------------------------------
    # Generate answer
    # --------------------------------------------------------

    final_prompt = f"""
You are the Claims Specialist in a healthcare
insurance multi-agent system.

Answer the user's question using ONLY the claim
tool result.

IMPORTANT RULES:

1. Do not invent claim status.
2. Do not invent claim dates.
3. Do not invent claim information.
4. Use the tool result as the source of truth.
5. If information is missing, clearly say that
   it cannot be confirmed.
6. Keep the answer short and clear.
7. Do not provide reasoning.
8. Do not provide analysis.
9. Do not use <think> tags.
10. Return ONLY the final answer.

User question:
{question}

Claim tool result:
{tool_result}
"""

    try:

        response = llm.invoke(
            [
                SystemMessage(content=final_prompt),
                HumanMessage(content=question),
            ]
        )

        answer = clean_answer(
            response.content
        )

    except Exception as error:

        answer = (
            f"Unable to generate the final answer: {error}"
        )

    print("Claim tool result:", tool_result)
    print()
    print("Answer:", answer)

    return {
        **state,
        "answer": answer,
    }


# ============================================================
# ENROLLMENT SPECIALIST
# ============================================================

def enrollment_specialist(state: AgentState) -> AgentState:

    question = state["question"]

    print()
    print("=" * 70)
    print("ENROLLMENT SPECIALIST")
    print("=" * 70)

    enrollment_prompt = """
You are the Enrollment Specialist in a healthcare
insurance multi-agent system.

You handle questions about:

- joining an insurance plan
- enrollment
- eligibility to enroll
- enrollment process

IMPORTANT RULES:

1. Do not invent company-specific enrollment rules.
2. If information is insufficient, clearly say so.
3. Keep the answer concise.
4. Do not provide reasoning.
5. Do not provide analysis.
6. Do not use <think> tags.
7. Return ONLY the final answer.
"""

    try:

        response = llm.invoke(
            [
                SystemMessage(
                    content=enrollment_prompt
                ),
                HumanMessage(content=question),
            ]
        )

        answer = clean_answer(
            response.content
        )

    except Exception as error:

        answer = (
            f"Unable to generate the final answer: {error}"
        )

    print("Answer:", answer)

    return {
        **state,
        "answer": answer,
    }


# ============================================================
# ROUTING FUNCTION
# ============================================================

def route_question(
    state: AgentState,
) -> Literal[
    "coverage",
    "claims",
    "enrollment",
]:

    route = state.get(
        "route",
        "coverage",
    )

    if route == "claims":
        return "claims"

    if route == "enrollment":
        return "enrollment"

    return "coverage"


# ============================================================
# BUILD LANGGRAPH
# ============================================================

builder = StateGraph(AgentState)

# Add Router
builder.add_node(
    "router",
    router_agent,
)

# Add Coverage Specialist
builder.add_node(
    "coverage",
    coverage_specialist,
)

# Add Claims Specialist
builder.add_node(
    "claims",
    claims_specialist,
)

# Add Enrollment Specialist
builder.add_node(
    "enrollment",
    enrollment_specialist,
)


# ------------------------------------------------------------
# START -> ROUTER
# ------------------------------------------------------------

builder.add_edge(
    START,
    "router",
)


# ------------------------------------------------------------
# ROUTER -> SPECIALIST
# ------------------------------------------------------------

builder.add_conditional_edges(
    "router",
    route_question,
    {
        "coverage": "coverage",
        "claims": "claims",
        "enrollment": "enrollment",
    },
)


# ------------------------------------------------------------
# SPECIALISTS -> END
# ------------------------------------------------------------

builder.add_edge(
    "coverage",
    END,
)

builder.add_edge(
    "claims",
    END,
)

builder.add_edge(
    "enrollment",
    END,
)


# Compile graph
graph = builder.compile()


# ============================================================
# ============================================================
# DAY 24 TEST QUESTIONS
# ============================================================

TEST_QUESTIONS = [
    "Is an MRI covered under P101?",
    "What is the status of claim CLM-1001?",
    "What are the deductible, monthly premium, and copay for P101?",
    "Does P102 cover physical therapy?",
]


# ============================================================
# RUN TESTS
# ============================================================

def run_tests():

    print()
    print("#" * 70)
    print("DAY 24 - AGENTIC CHATBOT FULL INTEGRATION")
    print("#" * 70)

    session_id = DEFAULT_SESSION_ID

    memory_context, selected_plan = (
        build_day20_memory_context(
            session_id
        )
    )

    print()
    print("[MEMORY]")
    print("Session:", session_id)
    print("Selected Plan:", selected_plan)
    print("Memory DB:", MEMORY_DB_PATH)

    for number, question in enumerate(
        TEST_QUESTIONS,
        start=1,
    ):

        print()
        print()
        print(f"TEST QUESTION {number}")
        print("-" * 70)
        print(question)

        try:

            result = graph.invoke(
                {
                    "question": question,
                    "session_id": session_id,
                    "memory_context": memory_context,
                    "selected_plan": selected_plan,
                }
            )

            route = result.get(
                "route",
                "unknown",
            )

            answer = result.get(
                "answer",
                "",
            )

            print()
            print("ROUTE:", route)

            print()
            print("FINAL ANSWER:")
            print(answer)

        except Exception as error:

            print()
            print(
                "ERROR:",
                error,
            )

    print()
    print("#" * 70)
    print("DAY 24 TEST RUN COMPLETED")
    print("#" * 70)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    run_tests()
