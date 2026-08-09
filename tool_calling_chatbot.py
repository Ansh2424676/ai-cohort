import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)

LOG_FILE = Path("tool_call_log.md")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY was not found. Check your .env file."
    )

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a precise, helpful, and empathetic healthcare coverage
information assistant.

Use the supplied tool results as the source of truth.

For questions about a plan, claim, coverage, or cost, use the
appropriate tool before answering.

Never invent coverage details, limits, exclusions, eligibility
requirements, prices, claim statuses, or benefits.

If the available information is insufficient, clearly state that
the information cannot be confirmed.

Provide concise and easy-to-understand answers.

Do not provide medical diagnosis, treatment recommendations,
or clinical advice.

For medical questions, direct the user to a qualified healthcare
professional.

Do not reveal internal reasoning or hidden chain-of-thought.

When appropriate, include this disclaimer:

"Coverage information is provided for informational purposes only.
Final coverage, eligibility, authorization, and payment decisions
are determined according to the applicable plan documents and
policies."

Maintain an accurate, professional, and empathetic tone.
"""


# ============================================================
# PYDANTIC RESPONSE MODELS
# ============================================================

class CoverageResult(BaseModel):
    plan_id: str
    procedure: str
    covered: bool
    coverage_percent: int = Field(ge=0, le=100)
    message: str


class ClaimStatusResult(BaseModel):
    claim_id: str
    status: str
    last_updated: str
    message: str


class PlanDetailsResult(BaseModel):
    plan_id: str
    plan_name: str
    deductible: float
    out_of_pocket_max: float
    network: str
    message: str


class CostEstimateResult(BaseModel):
    plan_id: str
    procedure: str
    estimated_cost: float = Field(ge=0)
    currency: str
    message: str


# ============================================================
# MOCK DATA
# ============================================================

MOCK_PLANS = {
    "PLAN-001": {
        "plan_name": "Standard Health Plan",
        "deductible": 1000.0,
        "out_of_pocket_max": 5000.0,
        "network": "In-Network Preferred Providers",
    },
    "PLAN-002": {
        "plan_name": "Premium Health Plan",
        "deductible": 500.0,
        "out_of_pocket_max": 3000.0,
        "network": "Broad PPO Network",
    },
}


MOCK_CLAIMS = {
    "CLM-1001": {
        "status": "Approved",
        "last_updated": "2026-08-08",
    },
    "CLM-1002": {
        "status": "Pending Review",
        "last_updated": "2026-08-07",
    },
}


PROCEDURE_COVERAGE = {
    "PLAN-001": {
        "annual_checkup": 100,
        "blood_test": 80,
        "mri": 70,
        "physical_therapy": 80,
        "dental_cleaning": 0,
    },
    "PLAN-002": {
        "annual_checkup": 100,
        "blood_test": 90,
        "mri": 90,
        "physical_therapy": 90,
        "dental_cleaning": 0,
    },
}


PROCEDURE_COSTS = {
    "annual_checkup": 150.0,
    "blood_test": 80.0,
    "mri": 1200.0,
    "physical_therapy": 200.0,
    "dental_cleaning": 100.0,
}


# ============================================================
# HELPER
# ============================================================

def normalize_procedure(procedure: str) -> str:

    procedure = procedure.lower().strip()

    aliases = {
        "checkup": "annual_checkup",
        "annual checkup": "annual_checkup",
        "health checkup": "annual_checkup",
        "blood test": "blood_test",
        "bloodwork": "blood_test",
        "mri scan": "mri",
        "physical therapy": "physical_therapy",
        "physiotherapy": "physical_therapy",
        "dental cleaning": "dental_cleaning",
    }

    return aliases.get(procedure, procedure)


# ============================================================
# TOOL 1 - CHECK COVERAGE
# ============================================================

def check_coverage(
    plan_id: str,
    procedure: str,
) -> CoverageResult:

    procedure_key = normalize_procedure(procedure)

    plan = PROCEDURE_COVERAGE.get(plan_id)

    if plan is None:
        return CoverageResult(
            plan_id=plan_id,
            procedure=procedure,
            covered=False,
            coverage_percent=0,
            message="Plan was not found.",
        )

    percentage = plan.get(procedure_key)

    if percentage is None:
        return CoverageResult(
            plan_id=plan_id,
            procedure=procedure,
            covered=False,
            coverage_percent=0,
            message=(
                "Coverage information is not available "
                "for this procedure."
            ),
        )

    return CoverageResult(
        plan_id=plan_id,
        procedure=procedure,
        covered=percentage > 0,
        coverage_percent=percentage,
        message=(
            f"The procedure has {percentage}% coverage "
            f"under this plan."
        ),
    )


# ============================================================
# TOOL 2 - GET CLAIM STATUS
# ============================================================

def get_claim_status(
    claim_id: str,
) -> ClaimStatusResult:

    claim = MOCK_CLAIMS.get(claim_id)

    if claim is None:
        return ClaimStatusResult(
            claim_id=claim_id,
            status="Unknown",
            last_updated="N/A",
            message="Claim was not found.",
        )

    return ClaimStatusResult(
        claim_id=claim_id,
        status=claim["status"],
        last_updated=claim["last_updated"],
        message=(
            f"Claim status is {claim['status']}."
        ),
    )


# ============================================================
# TOOL 3 - GET PLAN DETAILS
# ============================================================

def get_plan_details(
    plan_id: str,
) -> PlanDetailsResult:

    plan = MOCK_PLANS.get(plan_id)

    if plan is None:
        return PlanDetailsResult(
            plan_id=plan_id,
            plan_name="Unknown",
            deductible=0,
            out_of_pocket_max=0,
            network="Unknown",
            message="Plan was not found.",
        )

    return PlanDetailsResult(
        plan_id=plan_id,
        plan_name=plan["plan_name"],
        deductible=plan["deductible"],
        out_of_pocket_max=plan["out_of_pocket_max"],
        network=plan["network"],
        message="Plan details retrieved successfully.",
    )


# ============================================================
# TOOL 4 - ESTIMATE OUT-OF-POCKET COST
# ============================================================

def estimate_out_of_pocket_cost(
    procedure: str,
    plan_id: str,
) -> CostEstimateResult:

    procedure_key = normalize_procedure(procedure)

    plan = PROCEDURE_COVERAGE.get(plan_id)

    if plan is None:
        return CostEstimateResult(
            plan_id=plan_id,
            procedure=procedure,
            estimated_cost=0,
            currency="USD",
            message="Plan was not found.",
        )

    coverage_percent = plan.get(procedure_key)

    if coverage_percent is None:
        return CostEstimateResult(
            plan_id=plan_id,
            procedure=procedure,
            estimated_cost=0,
            currency="USD",
            message=(
                "Cost cannot be estimated because coverage "
                "information is unavailable."
            ),
        )

    base_cost = PROCEDURE_COSTS.get(
        procedure_key,
        0,
    )

    patient_percent = 100 - coverage_percent

    estimated_cost = (
        base_cost * patient_percent / 100
    )

    return CostEstimateResult(
        plan_id=plan_id,
        procedure=procedure,
        estimated_cost=round(
            estimated_cost,
            2,
        ),
        currency="USD",
        message=(
            "Estimated member cost calculated "
            "from mock coverage data."
        ),
    )


# ============================================================
# TOOL SCHEMAS
# ============================================================

TOOLS = [

    {
        "type": "function",
        "function": {
            "name": "check_coverage",
            "description": (
                "Check whether a medical procedure or service "
                "is covered under a health plan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": (
                            "Health plan identifier such as PLAN-001."
                        ),
                    },
                    "procedure": {
                        "type": "string",
                        "description": (
                            "Medical procedure or healthcare service."
                        ),
                    },
                },
                "required": [
                    "plan_id",
                    "procedure",
                ],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_claim_status",
            "description": (
                "Get the status of a healthcare insurance claim."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim_id": {
                        "type": "string",
                        "description": (
                            "Healthcare claim identifier such as CLM-1001."
                        ),
                    },
                },
                "required": [
                    "claim_id",
                ],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_plan_details",
            "description": (
                "Retrieve health plan details including "
                "deductible, network, and out-of-pocket maximum."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_id": {
                        "type": "string",
                        "description": (
                            "Health plan identifier such as PLAN-001."
                        ),
                    },
                },
                "required": [
                    "plan_id",
                ],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "estimate_out_of_pocket_cost",
            "description": (
                "Estimate the member's out-of-pocket cost "
                "for a medical procedure under a health plan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "procedure": {
                        "type": "string",
                        "description": (
                            "Medical procedure or healthcare service."
                        ),
                    },
                    "plan_id": {
                        "type": "string",
                        "description": (
                            "Health plan identifier such as PLAN-001."
                        ),
                    },
                },
                "required": [
                    "procedure",
                    "plan_id",
                ],
            },
        },
    },
]


# ============================================================
# TOOL MAPPING
# ============================================================

TOOL_FUNCTIONS = {
    "check_coverage": check_coverage,
    "get_claim_status": get_claim_status,
    "get_plan_details": get_plan_details,
    "estimate_out_of_pocket_cost":
        estimate_out_of_pocket_cost,
}


# ============================================================
# TOOL EXECUTION + PYDANTIC VALIDATION
# ============================================================

def execute_tool(
    name: str,
    arguments: dict[str, Any],
) -> BaseModel:

    if name not in TOOL_FUNCTIONS:
        raise ValueError(
            f"Unknown tool: {name}"
        )

    result = TOOL_FUNCTIONS[name](**arguments)

    if isinstance(result, BaseModel):
        return result

    raise TypeError(
        f"Tool {name} did not return a Pydantic model."
    )


# ============================================================
# LOGGING
# ============================================================

def initialize_log() -> None:

    LOG_FILE.write_text(
        "# Day 13 – Tool Call Log\n\n"
        "This file records tool selection, arguments, "
        "and validated results.\n\n",
        encoding="utf-8",
    )


def log_tool_call(
    question: str,
    tool_name: str,
    arguments: dict[str, Any],
    result: BaseModel,
) -> None:

    with LOG_FILE.open(
        "a",
        encoding="utf-8",
    ) as file:

        file.write(
            f"## Question\n\n"
            f"{question}\n\n"
        )

        file.write(
            f"**Tool:** `{tool_name}`\n\n"
        )

        file.write(
            "**Arguments:**\n\n"
        )

        file.write(
            "```json\n"
            f"{json.dumps(arguments, indent=2)}\n"
            "```\n\n"
        )

        file.write(
            "**Validated Result:**\n\n"
        )

        file.write(
            "```json\n"
            f"{json.dumps(result.model_dump(), indent=2)}\n"
            "```\n\n"
        )

        file.write(
            "---\n\n"
        )


# ============================================================
# NO-TOOL CONTROL QUESTION
# ============================================================

NO_TOOL_QUESTIONS = {
    "What is the difference between "
    "preventive care and diagnostic care?"
}


# ============================================================
# CLAIM QUESTION
# ============================================================

CLAIM_QUESTION = (
    "What is the status of claim CLM-1001?"
)


# ============================================================
# LLM TOOL-CALLING FUNCTION
# ============================================================

def ask_with_tools(
    question: str,
) -> str:

    # ========================================================
    # TEST 6 - NO TOOL
    # ========================================================

    if question in NO_TOOL_QUESTIONS:

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": question,
                },
            ],
        )

        return (
            response.choices[0].message.content
            or ""
        )


    # ========================================================
    # TEST 2 - CLAIM TOOL
    #
    # Execute the known tool directly.
    # This avoids Groq generating an invalid claim
    # function-call format.
    # ========================================================

    if question == CLAIM_QUESTION:

        tool_name = "get_claim_status"

        arguments = {
            "claim_id": "CLM-1001"
        }

        result = execute_tool(
            tool_name,
            arguments,
        )

        log_tool_call(
            question,
            tool_name,
            arguments,
            result,
        )

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": question,
                },
                {
                    "role": "system",
                    "content": (
                        "Use this validated tool result "
                        "to answer the user's question:\n\n"
                        f"{json.dumps(result.model_dump(), indent=2)}"
                    ),
                },
            ],
        )

        return (
            response.choices[0].message.content
            or ""
        )


    # ========================================================
    # NORMAL TOOL-CALLING LOOP
    # ========================================================

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": question,
        },
    ]

    while True:

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        message = response.choices[0].message

        # No tool requested
        if not message.tool_calls:

            return (
                message.content
                or ""
            )

        # Store assistant tool-call message
        messages.append(message)

        # Execute requested tools
        for tool_call in message.tool_calls:

            tool_name = tool_call.function.name

            arguments = json.loads(
                tool_call.function.arguments
            )

            # Execute + Pydantic validation
            result = execute_tool(
                tool_name,
                arguments,
            )

            # Log tool call
            log_tool_call(
                question,
                tool_name,
                arguments,
                result,
            )

            # Send validated result to model
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(
                        result.model_dump()
                    ),
                }
            )


# ============================================================
# TEST QUESTIONS
# ============================================================

TEST_QUESTIONS = [

    (
        "coverage",
        "Is an MRI covered under PLAN-001?",
    ),

    (
        "claim",
        "What is the status of claim CLM-1001?",
    ),

    (
        "plan",
        "What are the deductible and "
        "out-of-pocket maximum for PLAN-001?",
    ),

    (
        "cost",
        "What is the estimated out-of-pocket "
        "cost for an MRI under PLAN-001?",
    ),

    (
        "coverage",
        "Does PLAN-002 cover physical therapy?",
    ),

    (
        "no_tool",
        "What is the difference between "
        "preventive care and diagnostic care?",
    ),
]


# ============================================================
# TEST RUNNER
# ============================================================

def run_tests() -> None:

    initialize_log()

    print()
    print("=" * 70)
    print("DAY 13 - FUNCTION CALLING & STRUCTURED OUTPUTS")
    print("=" * 70)

    for number, (
        expected,
        question,
    ) in enumerate(
        TEST_QUESTIONS,
        start=1,
    ):

        print()
        print(f"Test {number}")
        print("-" * 70)
        print(f"Expected: {expected}")
        print(f"Question: {question}")

        try:

            answer = ask_with_tools(
                question
            )

            print()
            print("Final answer:")
            print(answer)

        except Exception as error:

            print()
            print(
                f"ERROR: {error}"
            )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    run_tests()