"""Pset_Madaster custom property set validation."""
import ifcopenshell.util.element


def _issue(element, check: str, severity: str, message: str) -> dict:
    return {
        "element_id": element.GlobalId,
        "element_name": getattr(element, "Name", None) or "",
        "element_type": element.is_a(),
        "check": check,
        "severity": severity,
        "message": message,
    }


def _empty(value) -> bool:
    return value is None or not str(value).strip()


def check(element) -> list[dict]:
    issues: list[dict] = []
    pset = ifcopenshell.util.element.get_pset(element, "Pset_Madaster")

    if pset is None:
        issues.append(_issue(
            element,
            check="MISSING_PSET_MADASTER",
            severity="INFO",
            message="Pset_Madaster not present on element (optional but recommended).",
        ))
        return issues

    if _empty(pset.get("MaterialOrProductId")):
        issues.append(_issue(
            element,
            check="MISSING_MADASTER_PRODUCT_ID",
            severity="WARNING",
            message="Pset_Madaster.MaterialOrProductId is missing or empty.",
        ))

    return issues
