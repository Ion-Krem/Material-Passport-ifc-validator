"""Building phase / renovation status validation for IFC material passport import."""
import ifcopenshell.util.element


PHASE_PROPERTY_NAMES = ("phase created", "renovation status", "phase", "status")

PHASE_VALUE_MAP = {
    "demolition": "Demolition",
    "to be demolished": "Demolition",
    "sloop": "Demolition",
    "nieuw": "New",
    "new": "New",
    "casco": "Casco",
    "existing": "Casco",
    "bestaand": "Casco",
}


def _issue(element, check: str, severity: str, message: str) -> dict:
    return {
        "element_id": element.GlobalId,
        "element_name": getattr(element, "Name", None) or "",
        "element_type": element.is_a(),
        "check": check,
        "severity": severity,
        "message": message,
    }


def _find_phase(psets: dict) -> tuple[str | None, object]:
    """Search psets for a phase-style property. Returns (property_name, value) or (None, None)."""
    for pset_values in psets.values():
        if not isinstance(pset_values, dict):
            continue
        for prop_name, value in pset_values.items():
            if prop_name.strip().lower() in PHASE_PROPERTY_NAMES:
                return prop_name, value
    return None, None


def check(element) -> list[dict]:
    issues: list[dict] = []
    psets = ifcopenshell.util.element.get_psets(element, psets_only=True) or {}

    prop_name, value = _find_phase(psets)
    if prop_name is None:
        issues.append(_issue(
            element,
            check="MISSING_PHASE",
            severity="INFO",
            message="No phase property found (looked for: Phase Created, Renovation Status, Phase, Status).",
        ))
        return issues

    if value is None or not str(value).strip():
        issues.append(_issue(
            element,
            check="UNKNOWN_PHASE_VALUE",
            severity="WARNING",
            message=f"Phase property '{prop_name}' is empty.",
        ))
        return issues

    if str(value).strip().lower() not in PHASE_VALUE_MAP:
        issues.append(_issue(
            element,
            check="UNKNOWN_PHASE_VALUE",
            severity="WARNING",
            message=f"Phase value '{value}' (from '{prop_name}') does not map to a known Madaster phase.",
        ))

    return issues
