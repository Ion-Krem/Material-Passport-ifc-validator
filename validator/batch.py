"""Parallel batch validation of multiple IFC files."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from os import cpu_count
from pathlib import Path

from tqdm import tqdm

from validator.core import validate_file


def _safe_validate(path: Path) -> dict:
    """Validate a single file, converting unexpected crashes into a load_error result."""
    try:
        return validate_file(path)
    except Exception as e:
        return {
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
            "load_error": f"Unexpected validation error: {type(e).__name__}: {e}",
        }


def _max_workers(requested: int | None) -> int:
    if requested is not None:
        return max(1, requested)
    return min(4, cpu_count() or 1)


def run_batch(
    paths: list[Path],
    max_workers: int | None = None,
    show_progress: bool = True,
    progress_callback=None,
) -> list[dict]:
    """Validate a list of IFC files in parallel. Returns results in input order.

    progress_callback, if given, is called as progress_callback(done, total, filename)
    on the main thread each time a file finishes.
    """
    if not paths:
        return []

    workers = _max_workers(max_workers)
    total = len(paths)

    def _notify(done: int, filename: str) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(done, total, filename)
        except Exception:
            pass

    if len(paths) == 1 or workers == 1:
        results: list[dict] = []
        iterator = paths
        if show_progress:
            iterator = tqdm(paths, desc="Validating", unit="file")
        for p in iterator:
            r = _safe_validate(p)
            results.append(r)
            _notify(len(results), r["filename"])
        return results

    results_by_path: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_safe_validate, p): p for p in paths}
        iterator = as_completed(futures)
        if show_progress:
            iterator = tqdm(iterator, total=len(futures), desc="Validating", unit="file")
        for fut in iterator:
            result = fut.result()
            results_by_path[result["path"]] = result
            _notify(len(results_by_path), result["filename"])

    return [results_by_path[str(p)] for p in paths if str(p) in results_by_path]
