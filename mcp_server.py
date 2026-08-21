import sqlite3
from pathlib import Path

from mcp.server import MCPServer

from retrieval_engine import vector_lookup


# ============================================================
# PROJECT ROOT
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent

# Prefer coverage.db in project root.
# If it does not exist, use the Day 20/24 chatbot database.
ROOT_DATABASE_PATH = ROOT_DIR / "coverage.db"
CHATBOT_DATABASE_PATH = ROOT_DIR / "coverage-chatbot-api" / "coverage.db"

if ROOT_DATABASE_PATH.exists():
    DATABASE_PATH = ROOT_DATABASE_PATH
else:
    DATABASE_PATH = CHATBOT_DATABASE_PATH


# ============================================================
# MCP SERVER
# ============================================================

mcp = MCPServer(
    "Coverage MCP Server"
)


# ============================================================
# DATABASE HELPER
# ============================================================

def get_db_connection():
    """Create a connection to the coverage database."""
    return sqlite3.connect(str(DATABASE_PATH))


# ============================================================
# TOOL 1 — CHECK COVERAGE
# ============================================================

@mcp.tool()
def check_coverage(question: str) -> str:
    """
    Check insurance coverage using vector retrieval
    and the plans table.
    """

    output = []

    # --------------------------------------------------------
    # Vector retrieval
    # --------------------------------------------------------

    try:
        vector_results = vector_lookup(question)

        if vector_results:
            output.append("Relevant coverage information:")

            for item in vector_results:
                output.append(f"- {item}")

    except Exception as error:
        output.append(f"Vector lookup error: {error}")

    # --------------------------------------------------------
    # Plans database
    # --------------------------------------------------------

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                plan_id,
                plan_name,
                monthly_premium,
                annual_deductible,
                copay_pct,
                coverage_type,
                network_tier
            FROM plans
            """
        )

        plans = cursor.fetchall()
        conn.close()

        if plans:
            output.append("")
            output.append("Available plans:")

            for plan in plans:
                (
                    plan_id,
                    plan_name,
                    monthly_premium,
                    deductible,
                    copay,
                    coverage_type,
                    network_tier,
                ) = plan

                output.append(
                    f"- {plan_id}: {plan_name} | "
                    f"Premium: ${monthly_premium}/month | "
                    f"Deductible: ${deductible} | "
                    f"Copay: {copay}% | "
                    f"Type: {coverage_type} | "
                    f"Tier: {network_tier}"
                )

    except Exception as error:
        output.append(f"Plans database error: {error}")

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    if not output:
        return "No coverage information found."

    return "\n".join(output)


# ============================================================
# TOOL 2 — GET CLAIM STATUS
# ============================================================

@mcp.tool()
def get_claim_status(claim_id: str) -> str:
    """
    Get claim status and details using claim ID.
    """

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                claim_id,
                member_id,
                plan_id,
                procedure,
                claim_amount,
                status,
                date_filed
            FROM claims
            WHERE claim_id = ?
            """,
            (claim_id,),
        )

        claim = cursor.fetchone()
        conn.close()

        if not claim:
            return f"No claim found for claim ID: {claim_id}"

        (
            claim_id,
            member_id,
            plan_id,
            procedure,
            claim_amount,
            status,
            date_filed,
        ) = claim

        return (
            f"Claim ID: {claim_id}\n"
            f"Member ID: {member_id}\n"
            f"Plan ID: {plan_id}\n"
            f"Procedure: {procedure}\n"
            f"Claim Amount: ${claim_amount}\n"
            f"Status: {status}\n"
            f"Date Filed: {date_filed}"
        )

    except Exception as error:
        return f"Claim lookup error: {error}"


# ============================================================
# RUN MCP SERVER
# ============================================================

if __name__ == "__main__":
    mcp.run()