"""Per-element validation orchestrator and file-level aggregation."""
from collections import Counter
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.classification
import ifcopenshell.util.element

from validator import (
    classification_checker,
    material_checker,
    material_picklist_checker,
    phase_checker,
    proxy_checker,
    pset_madaster_checker,
    quantity_checker,
)
from validator.phase_checker import PHASE_PROPERTY_NAMES
from validator.quantity_checker import AREA_KEYS, VOLUME_KEYS


CHECKERS = (
    classification_checker,
    quantity_checker,
    material_checker,
    material_picklist_checker,
    phase_checker,
    proxy_checker,
    pset_madaster_checker,
)

# IfcProduct subtypes that aren't physical building elements
# (spatial containers, abstract markers, holes, virtual references, grids, annotations).
_NON_PHYSICAL_TYPES = (
    "IfcSpatialStructureElement",
    "IfcSpatialElement",
    "IfcGrid",
    "IfcAnnotation",
    "IfcOpeningElement",
    "IfcVirtualElement",
    "IfcPort",
    "IfcStructuralActivity",
    "IfcStructuralItem",
)


def collect_physical_products(model) -> list:
    """All physical IfcProduct instances — building elements + MEP + furniture + transport."""
    products = model.by_type("IfcProduct")
    return [p for p in products if not any(p.is_a(t) for t in _NON_PHYSICAL_TYPES)]


def _first_classification_code(element) -> str:
    refs = ifcopenshell.util.classification.get_references(element) or []
    for ref in refs:
        code = getattr(ref, "Identification", None) or getattr(ref, "ItemReference", None)
        if code:
            return str(code)
    return ""


def _material_summary(element) -> str:
    material = ifcopenshell.util.element.get_material(element)
    if material is None:
        return ""
    if material.is_a("IfcMaterial"):
        return getattr(material, "Name", "") or ""
    if material.is_a("IfcMaterialLayerSetUsage"):
        layer_set = getattr(material, "ForLayerSet", None)
        if layer_set is None:
            return ""
        names = [
            getattr(getattr(l, "Material", None), "Name", "") or ""
            for l in (getattr(layer_set, "MaterialLayers", None) or [])
        ]
        names = [n for n in names if n]
        return ", ".join(names)
    if material.is_a("IfcMaterialLayerSet"):
        names = [
            getattr(getattr(l, "Material", None), "Name", "") or ""
            for l in (getattr(material, "MaterialLayers", None) or [])
        ]
        return ", ".join(n for n in names if n)
    if material.is_a("IfcMaterialList"):
        names = [getattr(m, "Name", "") or "" for m in (getattr(material, "Materials", None) or [])]
        return ", ".join(n for n in names if n)
    if material.is_a("IfcMaterialConstituentSet"):
        names = [
            getattr(getattr(c, "Material", None), "Name", "") or ""
            for c in (getattr(material, "MaterialConstituents", None) or [])
        ]
        return ", ".join(n for n in names if n)
    return material.is_a()


def _has_quantity(qtos: dict, keys: tuple[str, ...]) -> bool:
    for values in qtos.values():
        if not isinstance(values, dict):
            continue
        for key in keys:
            if key in values and isinstance(values[key], (int, float)):
                return True
    return False


def _phase_value(psets: dict) -> str:
    for pset_values in psets.values():
        if not isinstance(pset_values, dict):
            continue
        for prop_name, value in pset_values.items():
            if prop_name.strip().lower() in PHASE_PROPERTY_NAMES:
                return "" if value is None else str(value)
    return ""


def validate_element(element) -> dict:
    """Run all checkers on an element and return summary + issues."""
    issues: list[dict] = []
    for checker in CHECKERS:
        issues.extend(checker.check(element))

    qtos = ifcopenshell.util.element.get_psets(element, qtos_only=True) or {}
    psets = ifcopenshell.util.element.get_psets(element, psets_only=True) or {}

    summary = {
        "element_id": element.GlobalId,
        "element_name": getattr(element, "Name", None) or "",
        "element_type": element.is_a(),
        "classification_code": _first_classification_code(element),
        "material_name": _material_summary(element),
        "has_volume": _has_quantity(qtos, VOLUME_KEYS),
        "has_area": _has_quantity(qtos, AREA_KEYS),
        "phase": _phase_value(psets),
        "picklist_status": material_picklist_checker.picklist_status(element),
    }
    return {"summary": summary, "issues": issues}


def validate_file(path: Path) -> dict:
    """Open an IFC file and validate every IfcBuildingElement."""
    result = {
        "filename": path.name,
        "path": str(path),
        "schema": "",
        "element_count": 0,
        "type_counts": {},
        "elements": [],
        "issues": [],
        "error_count": 0,
        "warning_count": 0,
        "info_count": 0,
        "load_error": None,
    }

    try:
        model = ifcopenshell.open(str(path))
    except Exception as e:
        result["load_error"] = str(e)
        return result

    result["schema"] = model.schema
    elements = collect_physical_products(model)
    result["element_count"] = len(elements)
    result["type_counts"] = dict(Counter(e.is_a() for e in elements))

    for element in elements:
        per = validate_element(element)
        summary = per["summary"]
        issues = per["issues"]
        summary["issue_count"] = len(issues)
        summary["error_count"] = sum(1 for i in issues if i["severity"] == "ERROR")
        summary["warning_count"] = sum(1 for i in issues if i["severity"] == "WARNING")
        summary["info_count"] = sum(1 for i in issues if i["severity"] == "INFO")
        result["elements"].append(summary)
        result["issues"].extend(issues)

    result["error_count"] = sum(1 for i in result["issues"] if i["severity"] == "ERROR")
    result["warning_count"] = sum(1 for i in result["issues"] if i["severity"] == "WARNING")
    result["info_count"] = sum(1 for i in result["issues"] if i["severity"] == "INFO")
    return result
