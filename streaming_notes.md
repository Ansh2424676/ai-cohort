# Day 18 - SSE Streaming

## Overview

Implemented Server-Sent Events (SSE) streaming for the Healthcare
Coverage Assistant.

The backend streams the chatbot response using FastAPI
StreamingResponse, while the Streamlit frontend consumes the
stream incrementally.

## Architecture

Streamlit Frontend
        ↓
POST /chat
        ↓
FastAPI StreamingResponse
        ↓
Existing Retrieval + Tool Calling Pipeline
        ↓
SSE data events
        ↓
Streamlit response.iter_lines()
        ↓
Incremental UI updates

## Backend Streaming

The `/chat` endpoint uses FastAPI `StreamingResponse`.

The response uses:

`media_type="text/event-stream"`

The backend sends SSE events using the format:

`data: <content>`

A final `[DONE]` event indicates that streaming has completed.

An `[ERROR]` event is returned when an error occurs.

## Frontend Streaming

The Streamlit frontend sends the request using:

`stream=True`

The response is consumed using:

`response.iter_lines()`

A Streamlit `st.empty()` placeholder is updated as new
chunks arrive.

## Loading Experience

A `⏳ Thinking...` indicator is displayed while waiting for
the first response chunk.

The indicator is removed once the first streamed chunk arrives.

## Error Handling

The frontend handles:

- Backend connection errors
- Request timeouts
- HTTP errors
- Unexpected errors

The backend also provides an SSE error event.

## Verification

The `/chat` endpoint was tested successfully through the
FastAPI Swagger interface.

Expected SSE response format:

`data: <response chunk>`

followed by:

`data: [DONE]`

The endpoint returned HTTP 200 and
`text/event-stream` content type.

## Result

The Healthcare Coverage Assistant now provides a streaming
response experience instead of waiting for the complete
response before displaying it.