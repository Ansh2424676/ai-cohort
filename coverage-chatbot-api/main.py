import sys
import time
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# ============================================================
# PROJECT ROOT
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(ROOT_DIR)
)


# ============================================================
# EXISTING PIPELINES
# ============================================================

from retrieval_engine import retrieve
from tool_calling_chatbot import ask_with_tools


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Coverage Chatbot API",
    version="1.0.0"
)


# ============================================================
# SESSION STORE
# ============================================================

session_store: Dict[str, List[dict]] = {}


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):

    session_id: str

    member_id: str

    message: str


# ============================================================
# ROOT / HEALTH CHECK
# ============================================================

@app.get("/")
def root():

    return {
        "message": "Coverage Chatbot API is running"
    }


# ============================================================
# POST /chat
# ============================================================

@app.post("/chat")
def chat(request: ChatRequest):

    start_time = time.time()

    try:

        # ----------------------------------------------------
        # Create session
        # ----------------------------------------------------

        if request.session_id not in session_store:

            session_store[
                request.session_id
            ] = []


        # ----------------------------------------------------
        # Store user message
        # ----------------------------------------------------

        session_store[
            request.session_id
        ].append(
            {
                "role": "user",
                "message": request.message
            }
        )


        # ----------------------------------------------------
        # Day 10 - Retrieval
        # ----------------------------------------------------

        context = retrieve(
            request.message
        )


        # ----------------------------------------------------
        # Day 13 - Tool Calling / LLM
        # ----------------------------------------------------

        enhanced_question = f"""

Member / Plan ID:
{request.member_id}

User question:
{request.message}

Retrieved coverage context:
{context}

Use the available tools and retrieved information
to answer the user's question accurately.

Consider the member / plan ID when relevant.

Do not invent information.
"""


        # ----------------------------------------------------
        # Generate answer
        # ----------------------------------------------------

        answer = ask_with_tools(
            enhanced_question
        )


        # ----------------------------------------------------
        # Store assistant response
        # ----------------------------------------------------

        session_store[
            request.session_id
        ].append(
            {
                "role": "assistant",
                "message": answer
            }
        )


        # ----------------------------------------------------
        # Response time
        # ----------------------------------------------------

        elapsed = round(
            time.time() - start_time,
            3
        )


        print(
            f"[CHAT] "
            f"session={request.session_id} "
            f"member={request.member_id} "
            f"time={elapsed}s"
        )


        # ----------------------------------------------------
        # API RESPONSE
        # ----------------------------------------------------

        return {

            "session_id":
                request.session_id,

            "member_id":
                request.member_id,

            "message":
                request.message,

            "response":
                answer,

            "response_time_seconds":
                elapsed
        }


    except Exception as error:

        elapsed = round(
            time.time() - start_time,
            3
        )


        print(
            f"[ERROR] "
            f"session={request.session_id} "
            f"time={elapsed}s "
            f"error={error}"
        )


        raise HTTPException(
            status_code=500,
            detail="Unable to generate chatbot response."
        )


# ============================================================
# GET /history/{session_id}
# ============================================================

@app.get("/history/{session_id}")
def get_history(
    session_id: str
):

    history = session_store.get(
        session_id,
        []
    )


    return {

        "session_id":
            session_id,

        "messages":
            history
    }