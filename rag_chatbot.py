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
"""

def generate_answer(question, context):

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

{context}

Question:

{question}
"""
            }
        ]
    )

    return response.choices[0].message.content


def retrieve_and_answer(question):

    context = retrieve(question)

    return generate_answer(question, context)


if __name__ == "__main__":

    print("=" * 60)
    print("DAY 11 RAG CHATBOT")
    print("=" * 60)

    while True:

        question = input("\nAsk Question (exit to quit): ")

        if question.lower() == "exit":
            break

        print("\nGenerating Answer...\n")

        answer = retrieve_and_answer(question)

        print(answer)