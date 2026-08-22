"""Simple PHI/PII redaction helper for the Day 25 demo.

This project uses synthetic data only. The function is intentionally
deterministic and dependency-free so it can be unit-tested easily.
"""

import re
import unittest


_PATTERNS = [
    # Labeled identifiers first.
    (
        re.compile(r"(?i)(\bmember[_\s-]?id\s*[:=]\s*)([A-Za-z0-9_-]+)"),
        r"\1[REDACTED_MEMBER_ID]",
    ),
    (
        re.compile(r"(?i)(\bclaim[_\s-]?id\s*[:=]\s*)(CLM-\d+)"),
        r"\1[REDACTED_CLAIM_ID]",
    ),
    (
        re.compile(r"(?i)(\b(?:patient|member)\s+name\s*[:=]\s*)([A-Za-z][A-Za-z .'-]{1,80})"),
        r"\1[REDACTED_NAME]",
    ),
    (
        re.compile(r"(?i)(\bdate\s+of\s+birth\s*[:=]\s*)(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})"),
        r"\1[REDACTED_DOB]",
    ),
    # Common unlabelled PII formats.
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED_EMAIL]",
    ),
    (
        re.compile(r"(?<!\d)(?:\+?91[-.\s]?)?[6-9]\d{9}(?!\d)"),
        "[REDACTED_PHONE]",
    ),
    (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[REDACTED_SSN]",
    ),
    (
        re.compile(r"\bCLM-\d+\b", re.IGNORECASE),
        "[REDACTED_CLAIM_ID]",
    ),
]


def redact_pii(text: str) -> str:
    """Redact common PHI/PII patterns from text."""
    if not text:
        return text

    result = str(text)
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class TestRedactPII(unittest.TestCase):
    def test_member_id_and_email(self):
        sample = "member_id=MEM-12345 email=test@example.com"
        result = redact_pii(sample)
        self.assertIn("[REDACTED_MEMBER_ID]", result)
        self.assertIn("[REDACTED_EMAIL]", result)
        self.assertNotIn("MEM-12345", result)
        self.assertNotIn("test@example.com", result)

    def test_phone_and_ssn(self):
        sample = "Call 9876543210. SSN 123-45-6789."
        result = redact_pii(sample)
        self.assertIn("[REDACTED_PHONE]", result)
        self.assertIn("[REDACTED_SSN]", result)

    def test_claim_id(self):
        sample = "Claim CLM-1001 was approved."
        result = redact_pii(sample)
        self.assertIn("[REDACTED_CLAIM_ID]", result)
        self.assertNotIn("CLM-1001", result)


if __name__ == "__main__":
    unittest.main()
