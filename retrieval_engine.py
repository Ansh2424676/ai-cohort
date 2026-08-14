import sqlite3
from pathlib import Path

import chromadb


# ============================================================
# PROJECT ROOT
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent


# ============================================================
# DATABASE PATHS
# ============================================================

SQLITE_DB_PATH = ROOT_DIR / "coverage.db"
CHROMA_DB_PATH = ROOT_DIR / "chroma_data"


# ============================================================
# SQLITE CONNECTION
# ============================================================

conn = sqlite3.connect(
    str(SQLITE_DB_PATH),
    check_same_thread=False
)

cursor = conn.cursor()


# ============================================================
# CHROMADB CONNECTION
# ============================================================

client = chromadb.PersistentClient(
    path=str(CHROMA_DB_PATH)
)


# ============================================================
# COVERAGE KNOWLEDGE COLLECTION
# ============================================================

try:

    collection = client.get_collection(
        name="coverage_kb"
    )

except Exception as error:

    raise RuntimeError(
        f"Could not load ChromaDB collection 'coverage_kb'. "
        f"Expected location: {CHROMA_DB_PATH}. "
        f"Original error: {error}"
    )


# ============================================================
# QUESTION CLASSIFIER
# ============================================================

def classify(question: str) -> str:

    q = question.lower()

    structured_keywords = [
        "copay",
        "deductible",
        "premium",
        "claim",
        "status",
        "plan id",
        "monthly premium"
    ]

    unstructured_keywords = [
        "covered",
        "coverage",
        "benefits",
        "maternity",
        "mental",
        "hospital",
        "procedure",
        "policy",
        "eligibility"
    ]

    structured = any(
        word in q
        for word in structured_keywords
    )

    unstructured = any(
        word in q
        for word in unstructured_keywords
    )

    if structured and unstructured:
        return "both"

    elif structured:
        return "structured"

    elif unstructured:
        return "unstructured"

    return "structured"


# ============================================================
# SQL RETRIEVAL
# ============================================================

def sql_lookup(question: str):

    q = question.lower()

    try:

        if "claim" in q or "status" in q:

            cursor.execute(
                "SELECT * FROM claims"
            )

        else:

            cursor.execute(
                "SELECT * FROM plans"
            )

        rows = cursor.fetchall()

        return [
            str(row)
            for row in rows
        ]

    except Exception as error:

        return [
            f"SQL retrieval error: {error}"
        ]


# ============================================================
# VECTOR RETRIEVAL
# ============================================================

def vector_lookup(question: str):

    try:

        results = collection.query(
            query_texts=[question],
            n_results=5
        )

        documents = results.get(
            "documents",
            [[]]
        )

        if documents and documents[0]:

            return documents[0]

        return []

    except Exception as error:

        return [
            f"Vector retrieval error: {error}"
        ]


# ============================================================
# MAIN RETRIEVAL FUNCTION
# ============================================================

def retrieve(question: str) -> str:

    route = classify(question)

    context = []

    # --------------------------------------------------------
    # Structured retrieval
    # --------------------------------------------------------

    if route == "structured":

        context.extend(
            sql_lookup(question)
        )

    # --------------------------------------------------------
    # Unstructured retrieval
    # --------------------------------------------------------

    elif route == "unstructured":

        context.extend(
            vector_lookup(question)
        )

    # --------------------------------------------------------
    # Both retrieval methods
    # --------------------------------------------------------

    else:

        context.extend(
            sql_lookup(question)
        )

        context.extend(
            vector_lookup(question)
        )

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique = []

    for item in context:

        if item not in unique:

            unique.append(item)

    # --------------------------------------------------------
    # Return combined context
    # --------------------------------------------------------

    return "\n".join(
        str(item)
        for item in unique
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    questions = [

        "What is my copay?",

        "What is my deductible?",

        "What is monthly premium?",

        "Claim status",

        "Bronze coverage",

        "Silver maternity",

        "Gold mental health",

        "Hospital coverage",

        "Enrollment eligibility",

        "Bronze deductible and maternity"

    ]

    print("=" * 70)

    print(
        "DAY 11 RETRIEVAL TEST"
    )

    print("=" * 70)

    print()

    print(
        f"SQLite DB: {SQLITE_DB_PATH}"
    )

    print(
        f"ChromaDB: {CHROMA_DB_PATH}"
    )

    print(
        f"Collection: {collection.name}"
    )

    print()

    for i, question in enumerate(
        questions,
        start=1
    ):

        print("=" * 70)

        print(
            f"Question {i}: {question}"
        )

        print("-" * 70)

        print(
            retrieve(question)
        )

        print()

    conn.close()