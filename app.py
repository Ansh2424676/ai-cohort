import json
import uuid
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from response_cards import (
    ClaimStatusCard,
    CoverageSummaryCard
)


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


# ============================================================
# Validate Required Columns
# ============================================================

required_columns = [
    "plan_id",
    "plan_name"
]

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

plan_ids = (
    plans_df["plan_id"]
    .astype(str)
    .tolist()
)

plan_names = dict(
    zip(
        plans_df["plan_id"].astype(str),
        plans_df["plan_name"].astype(str)
    )
)


def format_plan(plan_id):

    return (
        f"{plan_id} - "
        f"{plan_names.get(plan_id, '')}"
    )


# ============================================================
# Session State
# ============================================================

if "session_id" not in st.session_state:

    st.session_state.session_id = str(
        uuid.uuid4()
    )


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

        st.session_state.session_id = str(
            uuid.uuid4()
        )

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

st.title(
    "💬 Healthcare Coverage Assistant"
)

st.write(
    "Ask questions about your healthcare coverage, "
    "claims, plans, deductibles, and benefits."
)


# ============================================================
# Display Chat History
# ============================================================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )


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
    # Display User Message
    # --------------------------------------------------------

    with st.chat_message("user"):

        st.markdown(user_message)


    # --------------------------------------------------------
    # Store User Message
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_message
        }
    )


    # --------------------------------------------------------
    # Backend Payload
    # --------------------------------------------------------

    payload = {
        "session_id": st.session_state.session_id,
        "member_id": st.session_state.member_id,
        "message": user_message
    }


    # ========================================================
    # STREAMING RESPONSE
    # ========================================================

    try:

        with st.chat_message("assistant"):

            # ------------------------------------------------
            # Loading Indicator
            # ------------------------------------------------

            loading_placeholder = st.empty()

            loading_placeholder.markdown(
                "⏳ Thinking..."
            )


            # ------------------------------------------------
            # Streaming Request
            # ------------------------------------------------

            response = requests.post(
                f"{BACKEND_URL}/chat",
                json=payload,
                stream=True,
                timeout=(10, 120)
            )

            response.raise_for_status()


            # ------------------------------------------------
            # Response State
            # ------------------------------------------------

            response_placeholder = st.empty()

            assistant_response = ""

            citation_chunk_ids = []

            rich_outputs = {}

            first_chunk_received = False


            # ------------------------------------------------
            # Read SSE Stream
            # ------------------------------------------------

            for line in response.iter_lines(
                decode_unicode=True
            ):

                if not line:
                    continue

                # ------------------------------------------------
                # Process only SSE data lines
                # ------------------------------------------------

                if not line.startswith("data:"):
                    continue

                # ------------------------------------------------
                # Extract data
                # ------------------------------------------------

                data = line[len("data:"):]

                # Remove only the separator space after "data:".
                # Do not strip normal streamed answer content.

                if data.startswith(" "):
                    data = data[1:]


                # ------------------------------------------------
                # DONE Event
                # ------------------------------------------------

                if data.startswith("[DONE]"):

                    loading_placeholder.empty()

                    continue


                # ------------------------------------------------
                # ERROR Event
                # ------------------------------------------------

                if data.startswith("[ERROR]"):

                    loading_placeholder.empty()

                    error_text = data.replace(
                        "[ERROR]",
                        "",
                        1
                    ).strip()

                    st.error(
                        error_text
                    )

                    continue


                # ------------------------------------------------
                # Day 19 - Citation Metadata
                # ------------------------------------------------

                if data.startswith("[CITATIONS]"):

                    citation_text = data.replace(
                        "[CITATIONS]",
                        "",
                        1
                    ).strip()

                    try:

                        citation_payload = json.loads(
                            citation_text
                        )

                        citation_chunk_ids = (
                            citation_payload.get(
                                "citation_chunk_ids",
                                []
                            )
                        )

                    except json.JSONDecodeError:

                        st.warning(
                            "Unable to read citation metadata."
                        )

                    continue


                # ------------------------------------------------
                # Day 19 - Rich Output Metadata
                # ------------------------------------------------

                if data.startswith("[RICH_OUTPUTS]"):

                    rich_text = data.replace(
                        "[RICH_OUTPUTS]",
                        "",
                        1
                    ).strip()

                    try:

                        rich_outputs = json.loads(
                            rich_text
                        )

                    except json.JSONDecodeError:

                        st.warning(
                            "Unable to read rich output metadata."
                        )

                    continue


                # ------------------------------------------------
                # First Answer Chunk
                # ------------------------------------------------

                if not first_chunk_received:

                    first_chunk_received = True

                    loading_placeholder.empty()


                # ------------------------------------------------
                # Append Normal Answer Chunk
                # ------------------------------------------------

                assistant_response += data

                response_placeholder.markdown(
                    assistant_response
                )


            # ------------------------------------------------
            # Remove Loading Indicator
            # ------------------------------------------------

            loading_placeholder.empty()


            # ------------------------------------------------
            # Empty Response Fallback
            # ------------------------------------------------

            if not assistant_response:

                assistant_response = (
                    "Sorry, I could not generate "
                    "a response."
                )

                response_placeholder.markdown(
                    assistant_response
                )


            # ====================================================
            # Day 19 - Rich Outputs
            # ====================================================

            # ----------------------------------------------------
            # Claim Status Card
            # ----------------------------------------------------

            claim_data = rich_outputs.get(
                "claim_status_card"
            )

            if claim_data:

                try:

                    claim_card = ClaimStatusCard(
                        **claim_data
                    )

                    with st.container(border=True):

                        st.subheader(
                            "📋 Claim Status"
                        )

                        col1, col2 = st.columns(2)

                        with col1:

                            st.metric(
                                "Claim ID",
                                claim_card.claim_id
                            )

                            st.metric(
                                "Status",
                                claim_card.status
                            )

                        with col2:

                            st.metric(
                                "Amount",
                                f"${claim_card.amount:,.2f}"
                            )

                            st.caption(
                                f"Claim Date: "
                                f"{claim_card.date}"
                            )

                except Exception as error:

                    st.warning(
                        f"Unable to render claim card: {error}"
                    )


            # ----------------------------------------------------
            # Coverage Summary Card
            # ----------------------------------------------------

            coverage_data = rich_outputs.get(
                "coverage_summary_card"
            )

            if coverage_data:

                try:

                    coverage_card = CoverageSummaryCard(
                        **coverage_data
                    )

                    with st.container(border=True):

                        st.subheader(
                            "🛡️ Coverage Summary"
                        )

                        col1, col2 = st.columns(2)

                        with col1:

                            st.write("**Plan**")

                            st.write(
                                coverage_card.plan_name
                            )

                            st.write("**Deductible**")

                            st.write(
                                f"${coverage_card.deductible:,.2f}"
                            )

                        with col2:

                            st.write("**Copay**")

                            st.write(
                                f"${coverage_card.copay:,.2f}"
                            )

                            if coverage_card.covered:

                                st.success(
                                    "Covered"
                                )

                            else:

                                st.error(
                                    "Not Covered"
                                )

                except Exception as error:

                    st.warning(
                        f"Unable to render coverage card: {error}"
                    )


            # ----------------------------------------------------
            # Policy Sources / Citations
            # ----------------------------------------------------

            if citation_chunk_ids:

                with st.expander(
                    "📚 Policy Sources"
                ):

                    for index, citation_id in enumerate(
                        citation_chunk_ids,
                        start=1
                    ):

                        st.markdown(
                            f"**[{index}]** `{citation_id}`"
                        )


        # ----------------------------------------------------
        # Store Assistant Response
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

            st.error(
                error_message
            )


    except requests.exceptions.Timeout:

        error_message = (
            "⏱️ The backend took too long to respond. "
            "Please try again."
        )

        with st.chat_message("assistant"):

            st.error(
                error_message
            )


    except requests.exceptions.HTTPError as error:

        error_message = (
            f"❌ Backend error: {error}"
        )

        with st.chat_message("assistant"):

            st.error(
                error_message
            )


    except Exception as error:

        error_message = (
            f"❌ Unexpected error: {error}"
        )

        with st.chat_message("assistant"):

            st.error(
                error_message
            )