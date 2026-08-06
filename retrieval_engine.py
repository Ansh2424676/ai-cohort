import sqlite3
import chromadb

# -----------------------------
# Connect SQLite
# -----------------------------
conn = sqlite3.connect("coverage.db")
cursor = conn.cursor()

# -----------------------------
# Connect ChromaDB
# -----------------------------
client = chromadb.PersistentClient(path="chroma_data")
collection = client.get_collection("coverage_kb")


# -----------------------------
# Question Classifier
# -----------------------------
def classify(question):
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

    structured = any(word in q for word in structured_keywords)
    unstructured = any(word in q for word in unstructured_keywords)

    if structured and unstructured:
        return "both"

    elif structured:
        return "structured"

    elif unstructured:
        return "unstructured"

    return "structured"


# -----------------------------
# SQL Lookup
# -----------------------------
def sql_lookup(question):

    q = question.lower()

    try:

        if "copay" in q:

            cursor.execute("""
            SELECT *
            FROM plans
            """)

        elif "deductible" in q:

            cursor.execute("""
            SELECT *
            FROM plans
            """)

        elif "premium" in q:

            cursor.execute("""
            SELECT *
            FROM plans
            """)

        elif "claim" in q or "status" in q:

            cursor.execute("""
            SELECT *
            FROM claims
            """)

        else:

            cursor.execute("""
            SELECT *
            FROM plans
            """)

        rows = cursor.fetchall()

        return rows

    except Exception as e:

        return [str(e)]


# -----------------------------
# Vector Lookup
# -----------------------------
def vector_lookup(question):

    try:

        results = collection.query(
            query_texts=[question],
            n_results=5
        )

        docs = results["documents"][0]

        return docs

    except Exception as e:

        return [str(e)]


# -----------------------------
# Retrieval Engine
# -----------------------------
def retrieve(question):

    route = classify(question)

    final_context = []

    if route == "structured":

        final_context.extend(sql_lookup(question))

    elif route == "unstructured":

        final_context.extend(vector_lookup(question))

    elif route == "both":

        final_context.extend(sql_lookup(question))
        final_context.extend(vector_lookup(question))

    # remove duplicates

    unique = []

    for item in final_context:

        if item not in unique:
            unique.append(item)

    return route, unique


# -----------------------------
# Test Harness
# -----------------------------
questions = [

    "What is my copay?",

    "What is my deductible?",

    "What is the monthly premium?",

    "What is claim status?",

    "Bronze plan coverage",

    "Silver maternity coverage",

    "Gold mental health benefits",

    "Hospital coverage",

    "Enrollment eligibility",

    "Bronze deductible and maternity coverage"

]


print("=" * 70)
print("DAY 10 RETRIEVAL ENGINE TEST")
print("=" * 70)

for i, q in enumerate(questions, start=1):

    route, context = retrieve(q)

    print("\n")
    print("=" * 70)
    print("Test :", i)
    print("Question :", q)
    print("Classification :", route)
    print("Retrieved Results :")

    for item in context:
        print(item)

print("\n")
print("=" * 70)
print("Testing Completed Successfully")
print("=" * 70)

conn.close()