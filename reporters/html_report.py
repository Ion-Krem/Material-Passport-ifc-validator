"""HTML report generation for IFC material passport validation results."""
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


CHECK_DEFINITIONS = (
    ("Classification",       ("MISSING_CLASSIFICATION", "INVALID_CLASSIFICATION_FORMAT")),
    ("Volume",               ("MISSING_VOLUME", "ZERO_VOLUME")),
    ("Area",                 ("MISSING_AREA",)),
    ("Materials",            ("MISSING_MATERIAL", "EMPTY_MATERIAL_NAME", "ZERO_THICKNESS_LAYER")),
    ("Material Picklist",    ("UNKNOWN_MATERIAL",)),
    ("Phase",                ("MISSING_PHASE", "UNKNOWN_PHASE_VALUE")),
    ("Proxy",                ("PROXY_ELEMENT",)),
    ("Pset_Madaster",        ("MISSING_PSET_MADASTER", "MISSING_MADASTER_PRODUCT_ID")),
)


def _bar_class(percent: float) -> str:
    if percent >= 80:
        return "green"
    if percent >= 50:
        return "amber"
    return "red"


def _row_class(element: dict) -> str:
    if element["error_count"] > 0:
        return "error"
    if element["warning_count"] > 0:
        return "warning"
    return "clean"


def _check_stats(file_result: dict) -> list[dict]:
    total = file_result["element_count"] or 0
    if total == 0:
        return []

    failing_by_check = {check: set() for _, checks in CHECK_DEFINITIONS for check in checks}
    for issue in file_result["issues"]:
        if issue["check"] in failing_by_check:
            failing_by_check[issue["check"]].add(issue["element_id"])

    picklist_applicable = sum(
        1 for e in file_result["elements"] if e.get("picklist_status") != "n/a"
    )

    stats = []
    for name, checks in CHECK_DEFINITIONS:
        failing = set()
        for c in checks:
            failing |= failing_by_check[c]
        if name == "Material Picklist":
            denom = picklist_applicable
            passed = denom - len(failing)
        else:
            denom = total
            passed = total - len(failing)
        percent = (passed / denom * 100) if denom else 100
        stats.append({
            "name": name,
            "passed": passed,
            "total": denom,
            "percent": percent,
            "bar_class": _bar_class(percent),
        })
    return stats


def _prepare_file(file_result: dict) -> dict:
    enriched = dict(file_result)
    total = file_result["element_count"] or 0
    clean = sum(1 for e in file_result["elements"] if e["error_count"] == 0)
    pass_rate = (clean / total) if total else 0
    enriched["pass_rate"] = pass_rate
    enriched["pass_rate_class"] = _bar_class(pass_rate * 100)
    enriched["check_stats"] = _check_stats(file_result)

    issues_by_id: dict[str, list[dict]] = defaultdict(list)
    for issue in file_result["issues"]:
        issues_by_id[issue["element_id"]].append(issue)

    enriched["elements"] = [
        {
            **e,
            "row_class": _row_class(e),
            "issues": issues_by_id.get(e["element_id"], []),
        }
        for e in file_result["elements"]
    ]
    return enriched


def write_report(files: list[dict], output_path: Path) -> None:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html")

    context = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": [_prepare_file(f) for f in files],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(template.render(context), encoding="utf-8")
