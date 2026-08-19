import os
import re
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
# HEALTHCARE TOOLS
# ============================================================

from tool_calling_chatbot import (
    check_coverage,
    get_claim_status,
    get_plan_details,
)


# ============================================================
# GRAPH STATE
# ============================================================

class AgentState(TypedDict, total=False):
    question: str
    route: str
    answer: str


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

    plan_id = extract_plan_id(question)

    tool_result = ""

    # --------------------------------------------------------
    # Detect procedure
    # --------------------------------------------------------

    procedure = None

    if "mri" in question_lower:
        procedure = "MRI"

    elif "physical therapy" in question_lower:
        procedure = "Physical Therapy"

    elif "blood test" in question_lower:
        procedure = "Blood Test"

    # --------------------------------------------------------
    # Procedure coverage
    # --------------------------------------------------------

    if plan_id and procedure:

        try:

            tool_result = check_coverage(
                plan_id=plan_id,
                procedure=procedure,
            )

        except Exception as error:

            tool_result = (
                f"Coverage tool error: {error}"
            )

    # --------------------------------------------------------
    # Plan details
    # --------------------------------------------------------

    elif plan_id and (
        "premium" in question_lower
        or "deductible" in question_lower
        or "copay" in question_lower
        or "plan details" in question_lower
        or "benefits" in question_lower
    ):

        try:

            tool_result = get_plan_details(
                plan_id=plan_id,
            )

        except Exception as error:

            tool_result = (
                f"Plan details tool error: {error}"
            )

    # --------------------------------------------------------
    # No matching tool
    # --------------------------------------------------------

    else:

        tool_result = (
            "No specific coverage tool result was available."
        )

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

        answer = (
            f"Unable to generate the final answer: {error}"
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

    tool_result = ""

    # --------------------------------------------------------
    # Claim status
    # --------------------------------------------------------

    if claim_id:

        try:

            tool_result = get_claim_status(
                claim_id=claim_id,
            )

        except Exception as error:

            tool_result = (
                f"Claim tool error: {error}"
            )

    else:

        tool_result = (
            "No valid claim ID was found."
        )

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
# DAY 22 TEST QUESTIONS
# ============================================================

TEST_QUESTIONS = [

    # Q1
    "Is an MRI covered under P101?",

    # Q2
    "What is the status of claim CLM-1001?",

    # Q3
    "What are the deductible, monthly premium, and copay for P101?",

    # Q4
    "Does P102 cover physical therapy?",

    # Q5
    "What is the estimated out-of-pocket cost for an MRI under P101?",
]


# ============================================================
# RUN TESTS
# ============================================================

def run_tests():

    print()
    print("#" * 70)
    print("DAY 22 - MULTI-AGENT ORCHESTRATION")
    print("#" * 70)

    results = []

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

            results.append(
                {
                    "question": question,
                    "route": route,
                    "answer": answer,
                }
            )

            print()
            print("ROUTE:", route)

            print()
            print("FINAL ANSWER:")
            print(answer)

        except Exception as error:

            print()
            print("ERROR:")
            print(error)

            results.append(
                {
                    "question": question,
                    "route": "error",
                    "answer": str(error),
                }
            )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()
    print()
    print("#" * 70)
    print("DAY 22 TEST SUMMARY")
    print("#" * 70)

    for index, result in enumerate(
        results,
        start=1,
    ):

        print()
        print(
            f"Q{index}: "
            f"{result['route']}"
        )

    print()
    print("#" * 70)
    print("EXPECTED ROUTING")
    print("#" * 70)

    print("Q1 -> coverage")
    print("Q2 -> claims")
    print("Q3 -> coverage")
    print("Q4 -> coverage")
    print("Q5 -> coverage")

    print()
    print("Multi-agent workflow completed.")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    run_tests()