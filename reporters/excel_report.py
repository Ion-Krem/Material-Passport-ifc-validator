"""Excel report generation for IFC material passport validation results."""
from pathlib import Path

import xlsxwriter


SUMMARY_HEADERS = (
    "File Name", "Schema", "Total Elements", "Errors", "Warnings", "Info", "Pass Rate %",
)
ELEMENT_HEADERS = (
    "File", "GlobalId", "Name", "Type", "Classification Code",
    "Material Name", "Picklist Match", "Has Volume", "Has Area", "Phase", "Issue Count",
)
ISSUE_HEADERS = (
    "File", "GlobalId", "Element Name", "Element Type", "Check", "Severity", "Message",
)


def _make_formats(wb: xlsxwriter.Workbook) -> dict:
    return {
        "header": wb.add_format({
            "bold": True, "font_color": "white", "bg_color": "#305496",
            "border": 1, "align": "left", "valign": "vcenter",
        }),
        "error": wb.add_format({"bg_color": "#F8CBAD", "font_color": "#9C0006"}),
        "warning": wb.add_format({"bg_color": "#FFE699", "font_color": "#7F6000"}),
        "info": wb.add_format({"bg_color": "#BDD7EE", "font_color": "#1F4E79"}),
        "pass": wb.add_format({"bg_color": "#C6EFCE", "font_color": "#006100"}),
        "bool_true": wb.add_format({"bg_color": "#C6EFCE", "align": "center"}),
        "bool_false": wb.add_format({"bg_color": "#F8CBAD", "align": "center"}),
        "match": wb.add_format({"bg_color": "#C6EFCE", "font_color": "#006100", "align": "center"}),
        "no_match": wb.add_format({"bg_color": "#FFE699", "font_color": "#7F6000", "align": "center"}),
        "na": wb.add_format({"font_color": "#9CA3AF", "align": "center"}),
        "percent": wb.add_format({"num_format": "0.0%"}),
    }


def _write_summary(ws, fmt: dict, files: list[dict]) -> None:
    for col, header in enumerate(SUMMARY_HEADERS):
        ws.write(0, col, header, fmt["header"])

    for row, f in enumerate(files, start=1):
        total = f["element_count"] or 0
        errors = f["error_count"]
        warnings = f["warning_count"]
        info = f["info_count"]
        clean = sum(1 for e in f["elements"] if e["error_count"] == 0)
        pass_rate = (clean / total) if total else 0

        ws.write(row, 0, f["filename"])
        ws.write(row, 1, f["schema"] or (f["load_error"] or ""))
        ws.write(row, 2, total)
        ws.write(row, 3, errors, fmt["error"] if errors else None)
        ws.write(row, 4, warnings, fmt["warning"] if warnings else None)
        ws.write(row, 5, info, fmt["info"] if info else None)
        ws.write(row, 6, pass_rate, fmt["percent"])

    ws.freeze_panes(1, 0)
    ws.set_column(0, 0, 40)
    ws.set_column(1, 1, 10)
    ws.set_column(2, 5, 14)
    ws.set_column(6, 6, 14)


def _write_elements(ws, fmt: dict, files: list[dict]) -> int:
    for col, header in enumerate(ELEMENT_HEADERS):
        ws.write(0, col, header, fmt["header"])

    row = 1
    for f in files:
        for el in f["elements"]:
            issue_fmt = fmt["pass"]
            if el["error_count"] > 0:
                issue_fmt = fmt["error"]
            elif el["warning_count"] > 0:
                issue_fmt = fmt["warning"]

            picklist_status = el.get("picklist_status", "n/a")
            picklist_label = {"match": "Match", "no_match": "No match", "n/a": "—"}[picklist_status]
            picklist_fmt = {"match": fmt["match"], "no_match": fmt["no_match"], "n/a": fmt["na"]}[picklist_status]

            ws.write(row, 0, f["filename"])
            ws.write(row, 1, el["element_id"])
            ws.write(row, 2, el["element_name"])
            ws.write(row, 3, el["element_type"])
            ws.write(row, 4, el["classification_code"])
            ws.write(row, 5, el["material_name"])
            ws.write(row, 6, picklist_label, picklist_fmt)
            ws.write_boolean(row, 7, el["has_volume"], fmt["bool_true"] if el["has_volume"] else fmt["bool_false"])
            ws.write_boolean(row, 8, el["has_area"], fmt["bool_true"] if el["has_area"] else fmt["bool_false"])
            ws.write(row, 9, el["phase"])
            ws.write(row, 10, el["issue_count"], issue_fmt)
            row += 1

    last_row = max(row - 1, 1)
    ws.autofilter(0, 0, last_row, len(ELEMENT_HEADERS) - 1)
    ws.freeze_panes(1, 0)
    ws.set_column(0, 0, 35)
    ws.set_column(1, 1, 24)
    ws.set_column(2, 2, 30)
    ws.set_column(3, 3, 24)
    ws.set_column(4, 4, 18)
    ws.set_column(5, 5, 28)
    ws.set_column(6, 6, 13)
    ws.set_column(7, 8, 11)
    ws.set_column(9, 9, 14)
    ws.set_column(10, 10, 12)
    return row - 1


def _write_issues(ws, fmt: dict, files: list[dict]) -> int:
    for col, header in enumerate(ISSUE_HEADERS):
        ws.write(0, col, header, fmt["header"])

    severity_fmt = {"ERROR": fmt["error"], "WARNING": fmt["warning"], "INFO": fmt["info"]}

    row = 1
    for f in files:
        for issue in f["issues"]:
            sev = issue["severity"]
            sf = severity_fmt.get(sev)
            ws.write(row, 0, f["filename"])
            ws.write(row, 1, issue["element_id"])
            ws.write(row, 2, issue["element_name"])
            ws.write(row, 3, issue["element_type"])
            ws.write(row, 4, issue["check"])
            ws.write(row, 5, sev, sf)
            ws.write(row, 6, issue["message"])
            row += 1

    last_row = max(row - 1, 1)
    ws.autofilter(0, 0, last_row, len(ISSUE_HEADERS) - 1)
    ws.freeze_panes(1, 0)
    ws.set_column(0, 0, 35)
    ws.set_column(1, 1, 24)
    ws.set_column(2, 2, 30)
    ws.set_column(3, 3, 24)
    ws.set_column(4, 4, 28)
    ws.set_column(5, 5, 10)
    ws.set_column(6, 6, 80)
    return row - 1


def write_report(files: list[dict], output_path: Path) -> dict:
    """Write a validation report. Returns row counts per sheet."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(output_path))
    try:
        fmt = _make_formats(wb)
        summary_ws = wb.add_worksheet("Summary")
        elements_ws = wb.add_worksheet("Element Details")
        issues_ws = wb.add_worksheet("Issues Log")

        _write_summary(summary_ws, fmt, files)
        element_rows = _write_elements(elements_ws, fmt, files)
        issue_rows = _write_issues(issues_ws, fmt, files)
    finally:
        wb.close()

    return {"summary": len(files), "elements": element_rows, "issues": issue_rows}
