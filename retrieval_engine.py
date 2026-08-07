import sqlite3
import chromadb

# ---------------------------------
# SQLite Connection
# ---------------------------------

conn = sqlite3.connect("coverage.db")
cursor = conn.cursor()

# ---------------------------------
# ChromaDB Connection
# ---------------------------------

client = chromadb.PersistentClient(path="chroma_data")
collection = client.get_collection("coverage_kb")

# ---------------------------------
# Question Classifier
# ---------------------------------

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


# ---------------------------------
# SQL Retrieval
# ---------------------------------

def sql_lookup(question):

    q = question.lower()

    try:

        if "claim" in q or "status" in q:
            cursor.execute("SELECT * FROM claims")

        else:
            cursor.execute("SELECT * FROM plans")

        rows = cursor.fetchall()

        return [str(row) for row in rows]

    except Exception as e:

        return [str(e)]


# ---------------------------------
# Vector Retrieval
# ---------------------------------

def vector_lookup(question):

    try:

        results = collection.query(
            query_texts=[question],
            n_results=5
        )

        return results["documents"][0]

    except Exception as e:

        return [str(e)]


# ---------------------------------
# Main Retrieval Function
# ---------------------------------

def retrieve(question):

    route = classify(question)

    context = []

    if route == "structured":

        context.extend(sql_lookup(question))

    elif route == "unstructured":

        context.extend(vector_lookup(question))

    else:

        context.extend(sql_lookup(question))
        context.extend(vector_lookup(question))

    # Remove duplicates

    unique = []

    for item in context:

        if item not in unique:
            unique.append(item)

    return "\n".join(str(x) for x in unique)


# ---------------------------------
# Test
# ---------------------------------

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
    print("DAY 11 RETRIEVAL TEST")
    print("=" * 70)

    for i, question in enumerate(questions, start=1):

        print("\n")
        print("=" * 70)
        print(f"Question {i}: {question}")
        print("-" * 70)

        print(retrieve(question))

    conn.close()