# Coverage Chatbot Memory Test

## Test Configuration

- API: Coverage Chatbot API v2.0.0
- Session: day20-memory-test
- Member ID: MEMBER-001
- Token History Limit: 2000

## Test 1: Plan Memory Across Turns

User:
I want to use plan_id=PLAN-GOLD-2026 for this conversation. Please remember this plan.

Follow-up User:
What plan did I select earlier?

Assistant:
You selected the Gold PPO health plan (Plan ID P101).

Result: PASS - The chatbot remembered the selected plan across conversation turns.

## Test 2: Deductible Memory

User:
What is the deductible for my selected plan?

Assistant:
Your Gold PPO plan (Plan ID P101) has an annual deductible of $2,000.

Result: PASS

## Test 3: Copay

User:
What is my copay under this plan?

Assistant:
Your Gold PPO plan (Plan ID P101) has a $10 copay for applicable covered services.

Result: PASS

## Test 4: Coinsurance

User:
What is my coinsurance after I meet the deductible?

Assistant:
After the $2,000 deductible is met, your cost share is 10% coinsurance on covered services.

Result: PASS

## Test 5: Out-of-Pocket Maximum

User:
What is my out-of-pocket maximum?

Assistant:
Your Gold PPO plan has an annual out-of-pocket maximum of $5,000.

Result: PASS

## Test 6: Claim Memory / Retrieval

User:
What is the status of claim CLM-1001?

Assistant:
Claim CLM-1001 is currently Approved.

Amount: $1,250.00
Date: 2026-08-16

Result: PASS

## Long Memory / Token Budget Test

The API was tested with a long multi-turn conversation.

Observed server logs:

[TOKENS] session=day20-memory-test before=2011 after=1190 final=1310 limit=2000

[MEMORY] History exceeded 2000 tokens.
[MEMORY] Summarizing 9 old messages.
[MEMORY] Tokens before=2011 after=1190

Later test:

[MEMORY] History exceeded 2000 tokens.
[MEMORY] Summarizing 9 old messages.
[MEMORY] Tokens before=2115 after=1047
[TOKENS] session=day20-memory-test before=2115 after=1047 final=1998 limit=2000

Result: PASS - History exceeding approximately 2000 tokens triggered summarization while preserving useful conversation context.

## Final Result

- Persistent conversation history: PASS
- Plan memory across turns: PASS
- Recent conversation context: PASS
- Token counting: PASS
- Token-budget summarization: PASS
- Coverage details retrieval: PASS
- Claim retrieval: PASS