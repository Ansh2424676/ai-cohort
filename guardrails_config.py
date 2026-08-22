"""Day 25 input/output guardrails.

Deterministic guardrails for:
- Prompt injection / jailbreak attempts
- Unauthorized access to another member's information
- Medical-advice safety redirection
- PHI/PII redaction
"""

import re

from redact_pii import redact_pii


# ============================================================
# INPUT GUARDRAILS
# ============================================================

INPUT_INJECTION_PATTERNS = [
    # --------------------------------------------------------
    # Prompt injection / jailbreak
    # --------------------------------------------------------
    r"\bignore\s+(?:all\s+)?previous\s+instructions\b",
    r"\bignore\s+(?:all\s+)?prior\s+instructions\b",
    r"\bignore\s+the\s+system\s+prompt\b",
    r"\breveal\s+(?:the\s+)?system\s+prompt\b",
    r"\bdisregard\s+(?:all\s+)?(?:previous|prior)\s+instructions\b",
    r"\bact\s+as\s+(?:the\s+)?system\b",
    r"\bforget\s+(?:all\s+)?previous\s+instructions\b",
    r"\bshow\s+(?:me\s+)?(?:the\s+)?system\s+prompt\b",

    # --------------------------------------------------------
    # Another / other member access
    # --------------------------------------------------------
    r"\banother\s+members?\b",
    r"\bother\s+members?\b",
    r"\bsomeone\s+else(?:'s)?\b",

    # --------------------------------------------------------
    # Explicit request for another member's information
    # --------------------------------------------------------
    r"\b(?:show|give|tell|provide|reveal|find|display)\b"
    r".{0,100}\b(?:another|other)\s+members?\b",

    # --------------------------------------------------------
    # PHI / PII fishing involving another member
    # --------------------------------------------------------
    r"\b(?:member[_\s]?id|claim[_\s]?id|claim|email|phone"
    r"(?:\s+number)?|social\s+security|ssn|address|records?|data)\b"
    r".{0,100}\b(?:another|other)\s+members?\b",

    # Another member first, sensitive field later
    r"\b(?:another|other)\s+members?\b"
    r".{0,100}\b(?:member[_\s]?id|claim[_\s]?id|claim|email|phone"
    r"(?:\s+number)?|social\s+security|ssn|address|records?|data)\b",
]


# ============================================================
# MEDICAL SAFETY GUARDRAILS
# ============================================================

MEDICAL_ADVICE_PATTERNS = [
    r"\byou should take\b",
    r"\byou should stop taking\b",
    r"\byou should start taking\b",
    r"\byou should change\b.{0,50}\bmedication\b",

    r"\byour condition is\b",

    r"\byou have\b.{0,80}"
    r"\b(?:disease|disorder|cancer|diabetes|infection)\b",

    r"\bdiagnos(?:e|is|ing)\b",

    r"\bwhat medication should i take\b",
    r"\bwhat medicine should i take\b",
    r"\bwhich medication should i take\b",
    r"\bwhich medicine should i take\b",

    r"\bshould i stop taking\b",
    r"\bshould i change my medication\b",
    r"\bshould i start taking\b",
]


# ============================================================
# INPUT CHECK
# ============================================================

def check_input_guardrail(text: str):
    """Return (allowed, reason)."""

    value = str(text or "").strip()

    if not value:
        return True, "allowed"

    for raw_pattern in INPUT_INJECTION_PATTERNS:
        if re.search(
            raw_pattern,
            value,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            return False, "prompt-injection or unauthorized-data request"

    return True, "allowed"


# ============================================================
# OUTPUT CHECK
# ============================================================

def apply_output_guardrails(text: str):
    """Redact PHI/PII and redirect unsafe medical advice."""

    redacted = redact_pii(str(text or ""))

    for raw_pattern in MEDICAL_ADVICE_PATTERNS:
        if re.search(
            raw_pattern,
            redacted,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            return (
                "For medical diagnosis or treatment advice, please consult "
                "a licensed healthcare professional. I can help explain "
                "general health-coverage information."
            )

    return redacted


# ============================================================
# USER-FACING INPUT GUARDRAIL
# ============================================================

def guardrail_input(text: str) -> str:
    """Return a safe user-facing response for blocked input."""

    allowed, _ = check_input_guardrail(text)

    if not allowed:
        return (
            "I can't help with prompt-injection attempts or another member's "
            "private claim/coverage information. I can help with your own "
            "coverage information."
        )

    return str(text or "")