"""IfcBuildingElementProxy detection — Madaster cannot classify these."""


def _issue(element, check: str, severity: str, message: str) -> dict:
    return {
        "element_id": element.GlobalId,
        "element_name": getattr(element, "Name", None) or "",
        "element_type": element.is_a(),
        "check": check,
        "severity": severity,
        "message": message,
    }


def check(element) -> list[dict]:
    if not element.is_a("IfcBuildingElementProxy"):
        return []

    name = getattr(element, "Name", None) or "(unnamed)"
    description = getattr(element, "Description", None) or ""
    descriptor = f"'{name}'"
    if description:
        descriptor += f" — {description}"

    return [_issue(
        element,
        check="PROXY_ELEMENT",
        severity="WARNING",
        message=f"Element {descriptor} is IfcBuildingElementProxy; Madaster cannot classify proxies.",
    )]
