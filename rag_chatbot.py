import os
from dotenv import load_dotenv
from openai import OpenAI

from retrieval_engine import retrieve

# Load .env
load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """
Answer ONLY using the context below.

If the answer isn't in the context,
say you don't know.

Do not invent information.

This is not medical advice.

When possible, use the citation IDs provided
with the retrieved context.
"""


def build_citation_context(context):
    """
    Add citation IDs to retrieved context chunks.
    """

    if isinstance(context, str):
        chunks = [
            chunk.strip()
            for chunk in context.split("\n")
            if chunk.strip()
        ]
    else:
        chunks = list(context)

    citation_ids = []
    formatted_chunks = []

    for index, chunk in enumerate(chunks, start=1):

        citation_id = f"chunk-{index}"

        citation_ids.append(citation_id)

        formatted_chunks.append(
            f"[{citation_id}]\n{chunk}"
        )

    formatted_context = "\n\n".join(
        formatted_chunks
    )

    return formatted_context, citation_ids


def generate_answer(question, context):

    formatted_context, citation_ids = (
        build_citation_context(context)
    )

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": f"""
Context:

{formatted_context}

Question:

{question}

Use only the supplied context.
"""
            }
        ]
    )

    answer = response.choices[0].message.content

    return {
        "answer": answer,
        "citation_chunk_ids": citation_ids
    }


def retrieve_and_answer(question):

    context = retrieve(question)

    return generate_answer(
        question,
        context
    )


if __name__ == "__main__":

    print("=" * 60)
    print("DAY 19 - CITATIONS & RICH OUTPUTS")
    print("=" * 60)

    while True:

        question = input(
            "\nAsk Question (exit to quit): "
        )

        if question.lower() == "exit":
            break

        print("\nGenerating Answer...\n")

        result = retrieve_and_answer(
            question
        )

        print(result["answer"])

        print("\nPolicy Sources:")

        for citation_id in result["citation_chunk_ids"]:
            print(f"- {citation_id}")
