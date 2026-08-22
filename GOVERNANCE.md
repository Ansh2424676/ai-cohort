# AI Governance Checklist

## Scope
This project is a synthetic healthcare coverage chatbot used for learning and demonstration only.
No real member or patient data may be used.

## Data Sources and Sensitivity
- `knowledge_base.jsonl` and related coverage data: internal/synthetic healthcare coverage information.
- SQLite conversation history: potentially sensitive because user messages and chatbot responses may contain PHI/PII.
- Request fields such as `member_id`, claim identifiers, dates, procedures, and coverage details are treated as sensitive.

## PHI/PII Fields
Potential PHI/PII includes:
- member IDs and other member identifiers
- names
- email addresses
- phone numbers
- dates of birth
- claim identifiers and claim-related details
- medical procedures or diagnosis-related information

Use minimum-necessary data and synthetic/fake PHI only.

## Bias Risks
Potential risks include:
- assumptions based on plan tier or member characteristics
- unequal treatment of users or plans
- incorrect or incomplete coverage interpretation
- overconfident medical or eligibility conclusions

Responses must remain factual, explain limitations, and avoid unsupported assumptions.

## Accountability
- Developer/owner: responsible for implementing and testing guardrails.
- Reviewer: responsible for reviewing adversarial test results.
- Production/compliance owner: responsible for formal privacy, security, legal, and compliance approval.

## Input Guardrails
- Detect prompt-injection/jailbreak attempts.
- Do not reveal another member's information.
- Keep the chatbot within its healthcare-coverage scope.
- Reject attempts to override system/developer instructions.

## Output Guardrails
- Redact PHI/PII before sensitive information is written to logs.
- Detect and redact PHI/PII in generated output.
- Redirect medical diagnosis/treatment requests to a licensed healthcare professional.
- Do not expose another member's claim or coverage data.

## Logging
Only redacted user inputs and assistant outputs should be persisted for the Day 25 demo.
Sensitive raw data should not be written to application logs.

## Testing
Five adversarial prompts are required:
1. jailbreak/prompt injection
2. another member's claim data request
3. medical-advice request
4. off-topic request
5. PHI-fishing request

Record pass/fail results in `adversarial_tests.md`.

## Production Notice
This exercise demonstrates governance and guardrail concepts only.
Production use requires a formal compliance, privacy, security, and legal review.
