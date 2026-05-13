"""Material name matching against the Madaster approved picklist."""
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

import ifcopenshell.util.element


_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")
_MIN_SUBSTRING_LEN = 4


def _normalize(name: str) -> str:
    return _NORMALIZE_RE.sub(" ", name.lower()).strip()


def _picklist_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    return base / "data" / "material_picklist.json"


@lru_cache(maxsize=1)
def _picklist() -> tuple[set[str], tuple[str, ...]]:
    """Returns (set of normalized names, sorted-by-length tuple of normalized names)."""
    path = _picklist_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set(), tuple()
    normalized = [_normalize(n) for n in raw if isinstance(n, str)]
    normalized = [n for n in normalized if n]
    return set(normalized), tuple(sorted(set(normalized), key=len, reverse=True))


def _matches(name: str) -> bool:
    n = _normalize(name)
    if not n:
        return False
    exact_set, ordered = _picklist()
    if not exact_set:
        return False
    if n in exact_set:
        return True
    for entry in ordered:
        if len(entry) < _MIN_SUBSTRING_LEN:
            continue
        if entry in n or n in entry:
            return True
    return False


def _material_names(element) -> list[str]:
    material = ifcopenshell.util.element.get_material(element)
    if material is None:
        return []
    if material.is_a("IfcMaterial"):
        return [getattr(material, "Name", "") or ""]
    if material.is_a("IfcMaterialLayerSetUsage"):
        layer_set = getattr(material, "ForLayerSet", None)
        if layer_set is None:
            return []
        return [
            getattr(getattr(l, "Material", None), "Name", "") or ""
            for l in (getattr(layer_set, "MaterialLayers", None) or [])
        ]
    if material.is_a("IfcMaterialLayerSet"):
        return [
            getattr(getattr(l, "Material", None), "Name", "") or ""
            for l in (getattr(material, "MaterialLayers", None) or [])
        ]
    if material.is_a("IfcMaterialList"):
        return [getattr(m, "Name", "") or "" for m in (getattr(material, "Materials", None) or [])]
    if material.is_a("IfcMaterialConstituentSet"):
        return [
            getattr(getattr(c, "Material", None), "Name", "") or ""
            for c in (getattr(material, "MaterialConstituents", None) or [])
        ]
    return []


def _issue(element, message: str) -> dict:
    return {
        "element_id": element.GlobalId,
        "element_name": getattr(element, "Name", None) or "",
        "element_type": element.is_a(),
        "check": "UNKNOWN_MATERIAL",
        "severity": "WARNING",
        "message": message,
    }


def check(element) -> list[dict]:
    names = [n for n in _material_names(element) if n and n.strip()]
    if not names:
        return []

    unmatched = [n for n in names if not _matches(n)]
    if not unmatched:
        return []

    if len(unmatched) == 1:
        msg = f"Material '{unmatched[0]}' does not match any entry in the Madaster picklist."
    else:
        joined = ", ".join(f"'{n}'" for n in unmatched)
        msg = f"Materials not in Madaster picklist: {joined}."
    return [_issue(element, msg)]


def picklist_status(element) -> str:
    """Returns 'match', 'no_match', or 'n/a' for reporting."""
    names = [n for n in _material_names(element) if n and n.strip()]
    if not names:
        return "n/a"
    return "match" if all(_matches(n) for n in names) else "no_match"
