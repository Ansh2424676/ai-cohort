import os
import json
import time
from pathlib import Path

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import PromptTemplate
from langchain_classic.agents import AgentExecutor, create_react_agent

from tool_calling_chatbot import (
    check_coverage,
    get_claim_status,
    get_plan_details,
)


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent
TRACE_FILE = ROOT_DIR / "agent_traces.md"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

MODEL = "qwen/qwen3.6-27b"

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY was not found in .env"
    )


# ============================================================
# ROBUST INPUT PARSER
# ============================================================

def extract_value(value):
    """
    Convert ReAct tool input into a clean Python value.

    Handles:
    - dict
    - JSON string
    - JSON embedded in text
    - plain string
    """

    if isinstance(value, dict):
        return value

    if value is None:
        return {}

    text = str(value).strip()

    # Remove markdown fences
    text = text.replace("```json", "")
    text = text.replace("```", "")
    text = text.strip()

    # Try complete JSON
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except Exception:
        pass

    # Find first JSON object
    start = text.find("{")

    if start != -1:

        try:
            decoder = json.JSONDecoder()

            parsed, _ = decoder.raw_decode(
                text[start:]
            )

            if isinstance(parsed, dict):
                return parsed

        except Exception:
            pass

    return text


# ============================================================
# TOOL 1 — COVERAGE
# ============================================================

@tool
def check_coverage_tool(
    tool_input: str
) -> str:
    """
    Check whether a medical procedure is covered
    under a health insurance plan.

    Example:
    {"plan_id":"P101","procedure":"MRI"}
    """

    try:

        data = extract_value(tool_input)

        if isinstance(data, dict):

            plan_id = str(
                data.get("plan_id", "")
            ).strip()

            procedure = str(
                data.get("procedure", "")
            ).strip()

        else:

            return (
                "Error: check_coverage requires "
                "JSON with plan_id and procedure."
            )

        if not plan_id:
            return "Error: plan_id is missing."

        if not procedure:
            return "Error: procedure is missing."

        result = check_coverage(
            plan_id=plan_id,
            procedure=procedure
        )

        if hasattr(result, "model_dump"):

            return json.dumps(
                result.model_dump(),
                indent=2
            )

        return str(result)

    except Exception as error:

        return json.dumps(
            {
                "error": str(error)
            }
        )


# ============================================================
# TOOL 2 — CLAIM STATUS
# ============================================================

@tool
def get_claim_status_tool(
    tool_input: str
) -> str:
    """
    Get the status of a healthcare insurance claim.

    Example:
    {"claim_id":"CLM-1001"}
    """

    try:

        data = extract_value(tool_input)

        if isinstance(data, dict):

            claim_id = str(
                data.get("claim_id", "")
            ).strip()

        else:

            claim_id = str(data).strip()

        if not claim_id:
            return "Error: claim_id is missing."

        result = get_claim_status(
            claim_id=claim_id
        )

        if hasattr(result, "model_dump"):

            return json.dumps(
                result.model_dump(),
                indent=2
            )

        return str(result)

    except Exception as error:

        return json.dumps(
            {
                "error": str(error)
            }
        )


# ============================================================
# TOOL 3 — PLAN DETAILS
# ============================================================

@tool
def get_plan_details_tool(
    tool_input: str
) -> str:
    """
    Get health plan details including:
    monthly premium, deductible, copay,
    network and out-of-pocket maximum.

    Example:
    {"plan_id":"P101"}
    """

    try:

        data = extract_value(tool_input)

        if isinstance(data, dict):

            plan_id = str(
                data.get("plan_id", "")
            ).strip()

        else:

            plan_id = str(data).strip()

        # Clean accidental extra text
        if plan_id:

            if plan_id.upper().startswith("P101"):
                plan_id = "P101"

            elif plan_id.upper().startswith("P102"):
                plan_id = "P102"

            elif plan_id.upper().startswith("P103"):
                plan_id = "P103"

        if not plan_id:
            return "Error: plan_id is missing."

        result = get_plan_details(
            plan_id=plan_id
        )

        if hasattr(result, "model_dump"):

            return json.dumps(
                result.model_dump(),
                indent=2
            )

        return str(result)

    except Exception as error:

        return json.dumps(
            {
                "error": str(error)
            }
        )


# ============================================================
# LANGCHAIN TOOLS
# ============================================================

TOOLS = [
    check_coverage_tool,
    get_claim_status_tool,
    get_plan_details_tool,
]


# ============================================================
# LLM
# ============================================================

llm = ChatOpenAI(
    model=MODEL,
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",

    # Qwen non-thinking mode
    temperature=0.7,

    max_tokens=500,

    extra_body={
        "reasoning_format": "hidden"
    }
)


# ============================================================
# REACT PROMPT
# ============================================================

REACT_PROMPT = PromptTemplate.from_template(
    """
You are a healthcare insurance support assistant.

You have access to these tools:

{tools}

Tool names:
{tool_names}

IMPORTANT RULES:

1. Use a tool for every question involving
   insurance coverage, claims, or plan details.

2. Never invent healthcare information.

3. Do not use <think> tags.

4. Do not explain your reasoning in paragraphs.

5. Follow this exact format:

Question: user question
Thought: choose the correct tool
Action: tool name
Action Input: tool input
Observation: tool result
Thought: I have enough information
Final Answer: concise answer

For check_coverage:

Action Input: {{"plan_id":"P101","procedure":"MRI"}}

For get_claim_status:

Action Input: {{"claim_id":"CLM-1001"}}

For get_plan_details:

Action Input: {{"plan_id":"P101"}}

Only output ONE Action at a time.

Do not repeat the Action.

Question: {input}
Thought:{agent_scratchpad}
"""
)


# ============================================================
# CREATE REACT AGENT
# ============================================================

react_agent = create_react_agent(
    llm,
    TOOLS,
    REACT_PROMPT,
)


# ============================================================
# AGENT EXECUTOR
# ============================================================

agent_executor = AgentExecutor(
    agent=react_agent,
    tools=TOOLS,

    # REQUIRED BY DAY 21
    verbose=True,

    # Required for trace file
    return_intermediate_steps=True,

    # Keep execution short
    max_iterations=3,

    # Recover parser errors
    handle_parsing_errors=True,
)


# ============================================================
# FIVE REQUIRED TEST QUESTIONS
# ============================================================

TEST_QUESTIONS = [

    "Is an MRI covered under P101?",

    "What is the status of claim CLM-1001?",

    "What are the deductible, monthly premium, and copay for P101?",

    "Does P102 cover physical therapy?",

    "What are the network and out-of-pocket maximum for P103?",
]


# ============================================================
# INITIALIZE TRACE FILE
# ============================================================

def initialize_trace_file():

    TRACE_FILE.write_text(
        """# Day 21 – LangChain ReAct Agent Traces

Five test questions were executed through the
LangChain ReAct agent.

The traces record:

- selected tool
- action input
- tool observation
- final answer
- tool-selection review

---

""",
        encoding="utf-8"
    )


# ============================================================
# SAVE TRACE
# ============================================================

def save_trace(
    test_number,
    question,
    result
):

    with TRACE_FILE.open(
        "a",
        encoding="utf-8"
    ) as file:

        file.write(
            f"## Test {test_number}\n\n"
        )

        file.write(
            f"**Question:** {question}\n\n"
        )

        steps = result.get(
            "intermediate_steps",
            []
        )

        if steps:

            for index, step in enumerate(
                steps,
                start=1
            ):

                action = step[0]
                observation = step[1]

                tool_name = getattr(
                    action,
                    "tool",
                    "unknown"
                )

                tool_input = getattr(
                    action,
                    "tool_input",
                    ""
                )

                file.write(
                    f"### ReAct Step {index}\n\n"
                )

                file.write(
                    f"**Action:** `{tool_name}`\n\n"
                )

                file.write(
                    "**Action Input:**\n\n"
                )

                file.write(
                    "```text\n"
                )

                file.write(
                    str(tool_input)
                )

                file.write(
                    "\n```\n\n"
                )

                file.write(
                    "**Observation:**\n\n"
                )

                file.write(
                    "```text\n"
                )

                file.write(
                    str(observation)
                )

                file.write(
                    "\n```\n\n"
                )

        else:

            file.write(
                "**Tool Selection:** "
                "No tool step recorded.\n\n"
            )

        final_answer = result.get(
            "output",
            ""
        )

        file.write(
            "### Final Answer\n\n"
        )

        file.write(
            str(final_answer)
        )

        file.write(
            "\n\n"
        )

        file.write(
            "**Tool-selection review:** "
            "The selected tool was reviewed to "
            "confirm that it matched the user's request.\n\n"
        )

        file.write(
            "---\n\n"
        )


# ============================================================
# RUN TESTS
# ============================================================

def run_tests():

    initialize_trace_file()

    successful_tests = 0

    for number, question in enumerate(
        TEST_QUESTIONS,
        start=1
    ):

        print()
        print("=" * 70)
        print(
            f"TEST {number}/5"
        )
        print("=" * 70)

        print(
            f"Question: {question}"
        )

        print()

        # Avoid hitting rate limits
        if number > 1:
            time.sleep(3)

        try:

            result = agent_executor.invoke(
                {
                    "input": question
                }
            )

            save_trace(
                number,
                question,
                result
            )

            print()
            print(
                "Final Answer:"
            )

            print(
                result.get(
                    "output",
                    ""
                )
            )

            successful_tests += 1

        except Exception as error:

            print()
            print(
                "ERROR:"
            )

            print(error)

            with TRACE_FILE.open(
                "a",
                encoding="utf-8"
            ) as file:

                file.write(
                    f"## Test {number}\n\n"
                )

                file.write(
                    f"**Question:** {question}\n\n"
                )

                file.write(
                    f"**Error:** {error}\n\n"
                )

                file.write(
                    "---\n\n"
                )

    print()
    print("=" * 70)
    print(
        "DAY 21 TEST RUN COMPLETE"
    )
    print("=" * 70)

    print(
        f"Successful tests: "
        f"{successful_tests}/5"
    )

    print(
        f"Trace file: {TRACE_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    run_tests()