"""Classification reference validation for IFC material passport import."""
import re

import ifcopenshell.util.classification


NLSFB_RE = re.compile(r"^\d{2}(\.\d{2})?$")
OMNICLASS_RE = re.compile(r"^\d{2}-\d{2}(\s\d{2}){0,2}$")
UNICLASS_PREFIX = "Ss_"


def _issue(element, check: str, severity: str, message: str) -> dict:
    return {
        "element_id": element.GlobalId,
        "element_name": getattr(element, "Name", None) or "",
        "element_type": element.is_a(),
        "check": check,
        "severity": severity,
        "message": message,
    }


def _code_format_valid(code: str) -> bool:
    if not code:
        return False
    code = code.strip()
    if NLSFB_RE.match(code):
        return True
    if OMNICLASS_RE.match(code):
        return True
    if code.startswith(UNICLASS_PREFIX):
        return True
    return False


def check(element) -> list[dict]:
    issues: list[dict] = []
    refs = ifcopenshell.util.classification.get_references(element) or []

    if not refs:
        issues.append(_issue(
            element,
            check="MISSING_CLASSIFICATION",
            severity="ERROR",
            message="Element has no classification reference (NL/SfB, OmniClass, or Uniclass).",
        ))
        return issues

    for ref in refs:
        code = getattr(ref, "Identification", None) or getattr(ref, "ItemReference", None)
        if not _code_format_valid(code or ""):
            issues.append(_issue(
                element,
                check="INVALID_CLASSIFICATION_FORMAT",
                severity="WARNING",
                message=f"Classification code '{code}' does not match NL/SfB, OmniClass Table 21, or Uniclass 2015 format.",
            ))

    return issues
