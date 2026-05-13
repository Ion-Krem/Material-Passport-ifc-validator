"""IFC Material Passport Validator — CLI entry point."""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from reporters import excel_report, html_report
from validator import batch, core


def pick_folder_dialog() -> Path | None:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title="Select folder containing IFC files")
    root.destroy()
    return Path(folder) if folder else None


def collect_files(file: Path | None, folder: Path | None) -> list[Path]:
    if file:
        if not file.is_file():
            print(f"ERROR: file not found: {file}", file=sys.stderr)
            return []
        return [file]
    if folder:
        if not folder.is_dir():
            print(f"ERROR: folder not found: {folder}", file=sys.stderr)
            return []
        return sorted(folder.glob("*.ifc"))
    return []


def print_file_summary(result: dict) -> None:
    print(f"\n=== {result['filename']} ===")
    if result["load_error"]:
        print(f"  ERROR: failed to open: {result['load_error']}")
        return

    print(f"  Schema:        {result['schema']}")
    print(f"  Element count: {result['element_count']}")
    print(f"  Element types:")
    for type_name, count in sorted(result["type_counts"].items(), key=lambda kv: -kv[1]):
        print(f"    {type_name:<40} {count}")

    issues = result["issues"]

    def count(name: str) -> int:
        return sum(1 for i in issues if i["check"] == name)

    print(f"  Classification check:")
    print(f"    Missing classification:   {count('MISSING_CLASSIFICATION')}")
    print(f"    Invalid format:           {count('INVALID_CLASSIFICATION_FORMAT')}")
    print(f"  Quantity check:")
    print(f"    Missing volume:           {count('MISSING_VOLUME')}")
    print(f"    Zero volume:              {count('ZERO_VOLUME')}")
    print(f"    Missing area:             {count('MISSING_AREA')}")
    print(f"    Missing dimensions:       {count('MISSING_DIMENSIONS')}")
    print(f"  Material check:")
    print(f"    Missing material:         {count('MISSING_MATERIAL')}")
    print(f"    Empty material name:      {count('EMPTY_MATERIAL_NAME')}")
    print(f"    Zero thickness layers:    {count('ZERO_THICKNESS_LAYER')}")
    print(f"  Material picklist check:")
    print(f"    Unknown materials:        {count('UNKNOWN_MATERIAL')}")
    print(f"  Phase check:")
    print(f"    Missing phase:            {count('MISSING_PHASE')}")
    print(f"    Unknown phase value:      {count('UNKNOWN_PHASE_VALUE')}")
    print(f"  Proxy check:")
    print(f"    Proxy elements:           {count('PROXY_ELEMENT')}")
    print(f"  Pset_Madaster check:")
    print(f"    Missing Pset_Madaster:    {count('MISSING_PSET_MADASTER')}")
    print(f"    Missing Product ID:       {count('MISSING_MADASTER_PRODUCT_ID')}")
    print(f"  Totals: {result['error_count']} errors, "
          f"{result['warning_count']} warnings, {result['info_count']} info")


def determine_output_dir(files: list[Path]) -> Path:
    parents = {f.parent for f in files}
    base = next(iter(parents)) if len(parents) == 1 else Path.cwd()
    return base / "output"


def run_cli(files: list[Path], output_dir: Path) -> int:
    print(f"Found {len(files)} IFC file(s).")
    results = batch.run_batch(files)

    for result in results:
        print_file_summary(result)

    failed = sum(1 for r in results if r["load_error"])
    total_elements = sum(r["element_count"] for r in results)
    total_errors = sum(r["error_count"] for r in results)
    total_warnings = sum(r["warning_count"] for r in results)
    total_info = sum(r["info_count"] for r in results)
    print()
    print("=" * 60)
    print(f"Batch summary: {len(results)} file(s) processed, {failed} failed")
    print(f"  Total elements:  {total_elements}")
    print(f"  Total errors:    {total_errors}")
    print(f"  Total warnings:  {total_warnings}")
    print(f"  Total info:      {total_info}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = output_dir / f"ifc_mp_validation_{timestamp}.xlsx"
    html_path = output_dir / f"ifc_mp_validation_{timestamp}.html"
    counts = excel_report.write_report(results, xlsx_path)
    html_report.write_report(results, html_path)

    print(f"\nReports written:")
    print(f"  {xlsx_path}")
    print(f"    Summary:         {counts['summary']} rows")
    print(f"    Element Details: {counts['elements']} rows")
    print(f"    Issues Log:      {counts['issues']} rows")
    print(f"  {html_path}")
    return 0


def run_gui(output_dir: Path | None) -> int:
    from gui import launch
    launch(output_dir)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="IFC Material Passport Validator")
    parser.add_argument("--file", type=Path, help="Single IFC file to validate")
    parser.add_argument("--folder", type=Path, help="Folder of IFC files to validate")
    parser.add_argument("--output", type=Path, help="Output directory for reports")
    parser.add_argument("--no-gui", action="store_true", help="Force CLI mode even with no args")
    args = parser.parse_args()

    args_provided = bool(args.file or args.folder)

    if not args_provided and not args.no_gui:
        return run_gui(args.output)

    if not args_provided:
        folder = pick_folder_dialog()
        if not folder:
            print("No folder selected. Exiting.")
            return 0
        args.folder = folder

    files = collect_files(args.file, args.folder)
    if not files:
        print("No .ifc files found.")
        return 1

    output_dir = args.output or determine_output_dir(files)
    return run_cli(files, output_dir)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
