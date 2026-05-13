"""Base quantity validation for IFC material passport import."""
import ifcopenshell.util.element


VOLUME_KEYS = ("NetVolume", "Volume", "GrossVolume")
AREA_KEYS = (
    "NetSideArea",
    "GrossSideArea",
    "TotalSurfaceArea",
    "GrossSurfaceArea",
    "OuterSurfaceArea",
    "CrossSectionArea",
    "NetFootprintArea",
    "GrossFootprintArea",
    "GrossArea",
    "Area",
)
DIMENSION_KEYS = ("Length", "Width", "Height", "Depth")
WEIGHT_KEYS = ("Weight", "NetWeight", "GrossWeight")


def _issue(element, check: str, severity: str, message: str) -> dict:
    return {
        "element_id": element.GlobalId,
        "element_name": getattr(element, "Name", None) or "",
        "element_type": element.is_a(),
        "check": check,
        "severity": severity,
        "message": message,
    }


def _find_quantity(qtos: dict, keys: tuple[str, ...]) -> tuple[str | None, float | None]:
    """Search qto dict for first matching key. Returns (key, value) or (None, None)."""
    for qto_values in qtos.values():
        if not isinstance(qto_values, dict):
            continue
        for key in keys:
            if key in qto_values:
                value = qto_values[key]
                if isinstance(value, (int, float)):
                    return key, float(value)
    return None, None


def check(element) -> list[dict]:
    issues: list[dict] = []
    qtos = ifcopenshell.util.element.get_psets(element, qtos_only=True) or {}

    volume_key, volume_value = _find_quantity(qtos, VOLUME_KEYS)
    if volume_key is None:
        issues.append(_issue(
            element,
            check="MISSING_VOLUME",
            severity="ERROR",
            message=f"No volume quantity found (looked for: {', '.join(VOLUME_KEYS)}).",
        ))
    elif volume_value == 0:
        issues.append(_issue(
            element,
            check="ZERO_VOLUME",
            severity="ERROR",
            message=f"Volume quantity '{volume_key}' is zero.",
        ))

    area_key, _ = _find_quantity(qtos, AREA_KEYS)
    if area_key is None:
        issues.append(_issue(
            element,
            check="MISSING_AREA",
            severity="WARNING",
            message=f"No area quantity found (looked for: {', '.join(AREA_KEYS)}).",
        ))

    dim_key, _ = _find_quantity(qtos, DIMENSION_KEYS)
    if dim_key is None:
        issues.append(_issue(
            element,
            check="MISSING_DIMENSIONS",
            severity="WARNING",
            message=f"No dimension quantity found (looked for: {', '.join(DIMENSION_KEYS)}).",
        ))

    return issues
