"""SPA HTML rendering for the desktop GUI."""
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from reporters.html_report import CHECK_DEFINITIONS, _bar_class, _prepare_file


def _chart_data(files: list[dict]) -> dict:
    file_rows = []
    for f in files:
        total = f["element_count"] or 0
        clean = sum(1 for e in f["elements"] if e["error_count"] == 0)
        pass_rate = (clean / total * 100) if total else 0
        file_rows.append({
            "filename": f["filename"],
            "elements": total,
            "errors": f["error_count"],
            "warnings": f["warning_count"],
            "info": f["info_count"],
            "pass_rate": pass_rate,
        })

    counts_by_check = {name: 0 for name, _ in CHECK_DEFINITIONS}
    for f in files:
        for issue in f["issues"]:
            for name, checks in CHECK_DEFINITIONS:
                if issue["check"] in checks:
                    counts_by_check[name] += 1
                    break
    issue_dist = [{"name": name, "count": count} for name, count in counts_by_check.items() if count > 0]

    return {"files": file_rows, "issue_dist": issue_dist}


def _totals(files: list[dict]) -> dict:
    total_elements = sum(f["element_count"] for f in files)
    clean = sum(
        1 for f in files for e in f["elements"] if e["error_count"] == 0
    )
    pass_rate = (clean / total_elements) if total_elements else 0
    return {
        "files": len(files),
        "elements": total_elements,
        "errors": sum(f["error_count"] for f in files),
        "warnings": sum(f["warning_count"] for f in files),
        "info": sum(f["info_count"] for f in files),
        "pass_rate": pass_rate,
    }


def _read_chart_js() -> str:
    path = Path(__file__).parent / "templates" / "chart.umd.min.js"
    return path.read_text(encoding="utf-8")


def render(files: list[dict], output_dir: Path) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("app.html")

    context = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": [_prepare_file(f) for f in files],
        "totals": _totals(files),
        "chart_data": _chart_data(files),
        "chart_js": _read_chart_js(),
        "output_dir": str(output_dir),
    }
    return template.render(context)
