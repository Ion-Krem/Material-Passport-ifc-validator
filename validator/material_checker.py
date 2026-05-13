"""Material assignment validation for IFC material passport import."""
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


def _name_empty(name: str | None) -> bool:
    return name is None or not str(name).strip()


def _check_layer_set(element, layer_set, issues: list[dict]) -> None:
    layers = getattr(layer_set, "MaterialLayers", None) or []
    if not layers:
        issues.append(_issue(
            element,
            check="MISSING_MATERIAL",
            severity="ERROR",
            message="MaterialLayerSet has no layers.",
        ))
        return

    for idx, layer in enumerate(layers):
        material = getattr(layer, "Material", None)
        name = getattr(material, "Name", None) if material else None
        if _name_empty(name):
            issues.append(_issue(
                element,
                check="EMPTY_MATERIAL_NAME",
                severity="ERROR",
                message=f"Layer {idx} has empty material name.",
            ))
        thickness = getattr(layer, "LayerThickness", None)
        if thickness is None or thickness <= 0:
            issues.append(_issue(
                element,
                check="ZERO_THICKNESS_LAYER",
                severity="WARNING",
                message=f"Layer {idx} ('{name or 'unnamed'}') has zero or missing thickness.",
            ))


def check(element) -> list[dict]:
    issues: list[dict] = []
    material = ifcopenshell.util.element.get_material(element)

    if material is None:
        issues.append(_issue(
            element,
            check="MISSING_MATERIAL",
            severity="ERROR",
            message="Element has no material assignment.",
        ))
        return issues

    if material.is_a("IfcMaterial"):
        if _name_empty(getattr(material, "Name", None)):
            issues.append(_issue(
                element,
                check="EMPTY_MATERIAL_NAME",
                severity="ERROR",
                message="IfcMaterial has empty Name.",
            ))

    elif material.is_a("IfcMaterialLayerSetUsage"):
        layer_set = getattr(material, "ForLayerSet", None)
        if layer_set is None:
            issues.append(_issue(
                element,
                check="MISSING_MATERIAL",
                severity="ERROR",
                message="IfcMaterialLayerSetUsage has no ForLayerSet.",
            ))
        else:
            _check_layer_set(element, layer_set, issues)

    elif material.is_a("IfcMaterialLayerSet"):
        _check_layer_set(element, material, issues)

    elif material.is_a("IfcMaterialList"):
        materials = getattr(material, "Materials", None) or []
        named = [m for m in materials if not _name_empty(getattr(m, "Name", None))]
        if not named:
            issues.append(_issue(
                element,
                check="EMPTY_MATERIAL_NAME",
                severity="ERROR",
                message="IfcMaterialList has no materials with a name.",
            ))

    elif material.is_a("IfcMaterialConstituentSet"):
        constituents = getattr(material, "MaterialConstituents", None) or []
        named = [
            c for c in constituents
            if not _name_empty(getattr(getattr(c, "Material", None), "Name", None))
        ]
        if not named:
            issues.append(_issue(
                element,
                check="EMPTY_MATERIAL_NAME",
                severity="ERROR",
                message="IfcMaterialConstituentSet has no constituents with a named material.",
            ))

    return issues
