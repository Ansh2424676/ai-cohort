import uuid
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


# ============================================================
# Configuration
# ============================================================

BACKEND_URL = "http://127.0.0.1:8000"

ROOT_DIR = Path(__file__).resolve().parent
PLANS_FILE = ROOT_DIR / "data" / "plans.csv"


# ============================================================
# Page Configuration
# ============================================================

st.set_page_config(
    page_title="Coverage Chatbot",
    page_icon="💬",
    layout="centered"
)


# ============================================================
# Load Health Plans
# ============================================================

try:
    plans_df = pd.read_csv(PLANS_FILE)

except Exception as error:
    st.error(
        f"Unable to load plans.csv.\n\n"
        f"Expected file: {PLANS_FILE}\n\n"
        f"Error: {error}"
    )
    st.stop()


# Make sure required columns exist
required_columns = ["plan_id", "plan_name"]

missing_columns = [
    column
    for column in required_columns
    if column not in plans_df.columns
]

if missing_columns:
    st.error(
        f"plans.csv is missing required columns: "
        f"{', '.join(missing_columns)}"
    )
    st.stop()


# ============================================================
# Prepare Plan Options
# ============================================================

plan_ids = plans_df["plan_id"].astype(str).tolist()

plan_names = dict(
    zip(
        plans_df["plan_id"].astype(str),
        plans_df["plan_name"].astype(str)
    )
)


def format_plan(plan_id):
    return f"{plan_id} - {plan_names.get(plan_id, '')}"


# ============================================================
# Session State
# ============================================================

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())


if "messages" not in st.session_state:
    st.session_state.messages = []


if "member_id" not in st.session_state:
    st.session_state.member_id = plan_ids[0]


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:

    st.title("Coverage Chatbot")

    st.subheader("Select Health Plan")

    selected_plan = st.selectbox(
        "Health Plan",
        plan_ids,
        format_func=format_plan,
        index=0
    )

    st.session_state.member_id = selected_plan

    st.divider()

    # --------------------------------------------------------
    # New Conversation
    # --------------------------------------------------------

    if st.button(
        "🆕 New Conversation",
        use_container_width=True
    ):

        st.session_state.session_id = str(uuid.uuid4())

        st.session_state.messages = []

        st.rerun()

    st.divider()

    # --------------------------------------------------------
    # Session ID
    # --------------------------------------------------------

    st.caption("Session ID")

    st.code(
        st.session_state.session_id
    )


# ============================================================
# Main Chat UI
# ============================================================

st.title("💬 Healthcare Coverage Assistant")

st.write(
    "Ask questions about your healthcare coverage, "
    "claims, plans, deductibles, and benefits."
)


# ============================================================
# Display Chat History
# ============================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


# ============================================================
# Chat Input
# ============================================================

user_message = st.chat_input(
    "Ask a question about your healthcare plan..."
)


# ============================================================
# Send Message
# ============================================================

if user_message:

    # --------------------------------------------------------
    # Display user message
    # --------------------------------------------------------

    with st.chat_message("user"):

        st.markdown(user_message)


    # --------------------------------------------------------
    # Store user message
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_message
        }
    )


    # --------------------------------------------------------
    # Backend payload
    # --------------------------------------------------------

    payload = {
        "session_id": st.session_state.session_id,
        "member_id": st.session_state.member_id,
        "message": user_message
    }


    # --------------------------------------------------------
    # Call FastAPI backend
    # --------------------------------------------------------

    try:

        with st.chat_message("assistant"):

            with st.spinner("Thinking..."):

                response = requests.post(
                    f"{BACKEND_URL}/chat",
                    json=payload,
                    timeout=60
                )


            response.raise_for_status()

            data = response.json()

            assistant_response = data.get(
                "response",
                "Sorry, I could not generate a response."
            )

            st.markdown(
                assistant_response
            )


        # ----------------------------------------------------
        # Store assistant response
        # ----------------------------------------------------

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": assistant_response
            }
        )


    # ========================================================
    # Error Handling
    # ========================================================

    except requests.exceptions.ConnectionError:

        error_message = (
            "❌ Could not connect to the backend. "
            "Please make sure the FastAPI server is running."
        )

        with st.chat_message("assistant"):

            st.error(error_message)


    except requests.exceptions.Timeout:

        error_message = (
            "⏱️ The backend took too long to respond. "
            "Please try again."
        )

        with st.chat_message("assistant"):

            st.error(error_message)


    except requests.exceptions.HTTPError as error:

        error_message = (
            f"❌ Backend error: {error}"
        )

        with st.chat_message("assistant"):

            st.error(error_message)


    except Exception as error:

        error_message = (
            f"❌ Unexpected error: {error}"
        )

        with st.chat_message("assistant"):

            st.error(error_message)