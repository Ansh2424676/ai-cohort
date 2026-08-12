# Day 16 Backend Chat Test

## API

POST /chat

GET /history/{session_id}

## Session

Session ID: `day16-test-001`

Member ID: `M1001`

## Test 1 — MRI Coverage

### Request

```json
{
  "session_id": "day16-test-001",
  "member_id": "M1001",
  "message": "Is an MRI covered under PLAN-001?"
}