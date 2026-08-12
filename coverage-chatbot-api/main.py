import sys
import time
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# --------------------------------------------------
# Project root path
# --------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))


# --------------------------------------------------
# Existing Day 10 / Day 13 pipelines
# --------------------------------------------------

from retrieval_engine import retrieve
from tool_calling_chatbot import ask_with_tools


# --------------------------------------------------
# FastAPI app
# --------------------------------------------------

app = FastAPI(
    title="Coverage Chatbot API",
    version="1.0.0"
)


# --------------------------------------------------
# Session store
# --------------------------------------------------

session_store: Dict[str, List[dict]] = {}


# --------------------------------------------------
# Request model
# --------------------------------------------------

class ChatRequest(BaseModel):
    session_id: str
    member_id: str
    message: str


# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "Coverage Chatbot API is running"
    }


# --------------------------------------------------
# POST /chat
# --------------------------------------------------

@app.post("/chat")
def chat(request: ChatRequest):

    start_time = time.time()

    try:
        # Create session if it does not exist
        if request.session_id not in session_store:
            session_store[request.session_id] = []

        # Store user message
        session_store[request.session_id].append({
            "role": "user",
            "message": request.message
        })

        # --------------------------------------------------
        # Day 10 - Retrieval
        # --------------------------------------------------

        context = retrieve(request.message)

        # --------------------------------------------------
        # Day 13 - Tool calling / LLM
        # --------------------------------------------------

        enhanced_question = f"""
User question:
{request.message}

Retrieved coverage context:
{context}

Use the available tools and retrieved information to answer
the user's question accurately. Do not invent information.
"""

        answer = ask_with_tools(enhanced_question)

        # Store assistant response
        session_store[request.session_id].append({
            "role": "assistant",
            "message": answer
        })

        elapsed = round(time.time() - start_time, 3)

        print(
            f"[CHAT] session={request.session_id} "
            f"time={elapsed}s"
        )

        return {
            "session_id": request.session_id,
            "member_id": request.member_id,
            "message": request.message,
            "response": answer,
            "response_time_seconds": elapsed
        }

    except Exception as error:

        elapsed = round(time.time() - start_time, 3)

        print(
            f"[ERROR] session={request.session_id} "
            f"time={elapsed}s "
            f"error={error}"
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to generate chatbot response."
        )


# --------------------------------------------------
# GET /history/{session_id}
# --------------------------------------------------

@app.get("/history/{session_id}")
def get_history(session_id: str):

    history = session_store.get(session_id, [])

    return {
        "session_id": session_id,
        "messages": history
    }