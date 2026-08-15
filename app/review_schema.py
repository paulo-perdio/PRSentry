"""
Data model for LLM-generated review results, plus the JSON schema used to
constrain Gemini's structured output.

Deliberately uses only stdlib (dataclasses + json), not pydantic — keeps
this testable in environments without extra dependencies installed, and
avoids a dependency PRSentry doesn't otherwise need.
"""
import json
from dataclasses import dataclass, field

VALID_SEVERITIES = {"high", "medium", "low"}

# Passed to Gemini as response_schema to constrain its output shape.
# See: https://ai.google.dev/gemini-api/docs/structured-output
REVIEW_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "One or two sentence overall summary of the review.",
        },
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "line_hint": {
                        "type": "string",
                        "description": "A short description of where in the file, e.g. 'inside apply_discount' — not required to be an exact line number.",
                    },
                    "description": {
                        "type": "string",
                        "description": "What's wrong and why it matters. Be specific about the actual bug, not generic style commentary.",
                    },
                },
                "required": ["file", "severity", "description"],
            },
        },
    },
    "required": ["summary", "findings"],
}


class ReviewParseError(Exception):
    """Raised when the LLM's response doesn't match the expected shape."""


@dataclass
class Finding:
    file: str
    severity: str
    description: str
    line_hint: str = ""

    def __post_init__(self):
        if self.severity not in VALID_SEVERITIES:
            raise ReviewParseError(
                f"Invalid severity {self.severity!r}; must be one of {VALID_SEVERITIES}"
            )


@dataclass
class ReviewResult:
    summary: str
    findings: list[Finding] = field(default_factory=list)


def parse_review_result(raw_json_text: str) -> ReviewResult:
    """
    Parse and validate the LLM's raw JSON response text into a ReviewResult.
    Raises ReviewParseError with a clear message on any malformed input —
    missing keys, wrong types, invalid severity values, or invalid JSON.
    """
    try:
        data = json.loads(raw_json_text)
    except json.JSONDecodeError as exc:
        raise ReviewParseError(f"Response was not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ReviewParseError(f"Expected a JSON object, got {type(data).__name__}")

    if "summary" not in data:
        raise ReviewParseError("Missing required field: 'summary'")
    if "findings" not in data:
        raise ReviewParseError("Missing required field: 'findings'")
    if not isinstance(data["findings"], list):
        raise ReviewParseError(
            f"'findings' must be a list, got {type(data['findings']).__name__}"
        )

    findings = []
    for i, item in enumerate(data["findings"]):
        if not isinstance(item, dict):
            raise ReviewParseError(f"findings[{i}] is not an object")
        missing = [k for k in ("file", "severity", "description") if k not in item]
        if missing:
            raise ReviewParseError(f"findings[{i}] missing required field(s): {missing}")
        findings.append(Finding(
            file=item["file"],
            severity=item["severity"],
            description=item["description"],
            line_hint=item.get("line_hint", ""),
        ))

    return ReviewResult(summary=data["summary"], findings=findings)
