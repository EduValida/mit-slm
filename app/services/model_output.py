import json
import logging
import re


logger = logging.getLogger(__name__)


def _normalize_json_text(text: str) -> str:
    """Normalize Unicode punctuation that models sometimes emit instead of ASCII."""
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = text.replace("｛", "{").replace("｝", "}")
    text = text.replace("［", "[").replace("］", "]")
    text = text.replace("：", ":").replace("，", ",")
    return text


def extract_json_from_response(response_text: str) -> dict:
    """Extract JSON from model response, handling common formatting mistakes."""
    if not response_text or not response_text.strip():
        return {}

    text = _normalize_json_text(response_text)

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    anchor_match = re.search(r'\{[^{}]*"badge_name".*\}', text, re.DOTALL)
    if anchor_match:
        try:
            return json.loads(anchor_match.group(0).strip())
        except json.JSONDecodeError:
            pass

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0).strip())
        except json.JSONDecodeError:
            pass

    logger.warning("Could not extract valid JSON from response: %s", response_text[:300])
    return {"error": "json_extraction_failed", "raw_response": response_text}
