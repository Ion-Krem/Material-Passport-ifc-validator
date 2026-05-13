"""pywebview desktop GUI for IFC Material Passport Validator.

Flow:
  1. Window opens on a landing screen (Select Folder / Select Files buttons).
  2. js_api bridge methods call pywebview's native file dialog.
  3. Validation runs in a background thread while the loading screen is shown.
  4. The dashboard SPA is rendered to a tempfile and loaded via load_url().
  5. "New Validation" in the sidebar returns to the landing screen.

We use load_url(file:///tempfile) rather than load_html() because the latter
triggers "System.ArgumentException: Class not registered" on the WebView2 COM
bridge for large HTML payloads.
"""
import html
import json
import sys
import tempfile
import threading
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

from reporters import app_html, excel_report, html_report
from validator import batch


_TEMPLATES_DIR = Path(__file__).parent / "reporters" / "templates"


def _read_template(name: str) -> str:
    return (_TEMPLATES_DIR / name).read_text(encoding="utf-8")


def _loading_html(files: list[Path]) -> str:
    total = len(files)
    return """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Validating…</title>
<style>
  html, body { height: 100%; margin: 0; }
  body { display: flex; align-items: center; justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #111827; color: #f3f4f6; }
  .box { text-align: center; width: 540px; max-width: 90%; padding: 0 24px; }
  .title { font-size: 18px; font-weight: 600; margin-bottom: 6px; }
  .sub { font-size: 13px; color: #9ca3af; margin-bottom: 28px; }
  .progress-track {
    height: 10px;
    background: #1f2937;
    border-radius: 5px;
    overflow: hidden;
    margin-bottom: 14px;
  }
  .progress-fill {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, #2563eb 0%, #0d9488 100%);
    transition: width 0.25s ease-out;
    border-radius: 5px;
  }
  .progress-text { font-size: 13px; color: #d1d5db; margin-bottom: 4px; font-weight: 500; }
  .progress-current { font-size: 12px; color: #6b7280; word-break: break-all; min-height: 18px; }
</style></head>
<body>
  <div class="box">
    <div class="title">Validating IFC files…</div>
    <div class="sub">Processing __TOTAL__ file(s) in parallel.</div>
    <div class="progress-track"><div class="progress-fill" id="progress-fill"></div></div>
    <div class="progress-text" id="progress-text">0 / __TOTAL__ files processed</div>
    <div class="progress-current" id="progress-current">Starting…</div>
  </div>
<script>
window.updateProgress = function(done, total, filename) {
  var pct = total > 0 ? Math.round(done / total * 100) : 0;
  var fill = document.getElementById('progress-fill');
  var text = document.getElementById('progress-text');
  var cur = document.getElementById('progress-current');
  if (fill) fill.style.width = pct + '%';
  if (text) text.textContent = done + ' / ' + total + ' files processed (' + pct + '%)';
  if (cur) cur.textContent = 'Last: ' + filename;
};
</script>
</body></html>
""".replace("__TOTAL__", str(total))


def _error_html(message: str) -> str:
    return f"""
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Error</title>
<style>
  html, body {{ height: 100%; margin: 0; }}
  body {{ display: flex; align-items: center; justify-content: center;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #111827; color: #f3f4f6; }}
  .box {{ text-align: center; max-width: 520px; padding: 0 24px; }}
  .title {{ font-size: 18px; font-weight: 600; margin-bottom: 8px; color: #fca5a5; }}
  .msg {{ font-size: 13px; color: #9ca3af; margin-bottom: 24px; }}
  button {{ font: inherit; font-size: 13px; padding: 10px 18px; border-radius: 6px;
    cursor: pointer; border: none; background: #2563eb; color: white; }}
</style></head>
<body>
  <div class="box">
    <div class="title">⚠ {html.escape(message)}</div>
    <button onclick="window.pywebview.api.new_validation()">← Back</button>
  </div>
</body></html>
"""


def _write_temp_html(content: str) -> Path:
    fd = tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", prefix="ifc_mp_", delete=False, encoding="utf-8"
    )
    fd.write(content)
    fd.close()
    return Path(fd.name)


def _write_reports(results: list[dict], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = output_dir / f"ifc_mp_validation_{timestamp}.xlsx"
    html_path = output_dir / f"ifc_mp_validation_{timestamp}.html"
    excel_report.write_report(results, xlsx_path)
    html_report.write_report(results, html_path)
    return html_path


def _determine_output_dir(files: list[Path], explicit: Path | None) -> Path:
    if explicit:
        return explicit
    parents = {f.parent for f in files}
    base = next(iter(parents)) if len(parents) == 1 else Path.cwd()
    return base / "output"


class GUIBridge:
    """Exposed to JavaScript via webview.create_window(js_api=...)."""

    def __init__(self, explicit_output_dir: Path | None):
        self.window = None
        self.explicit_output_dir = explicit_output_dir
        self.tempfiles: list[Path] = []
        self.results: list[dict] = []
        self.last_output_dir: Path | None = None
        self._lock = threading.Lock()

    def attach(self, window) -> None:
        self.window = window

    def pick_folder(self) -> None:
        import webview
        result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return
        folder = Path(result[0])
        files = sorted(folder.glob("*.ifc"))
        if not files:
            self._load(_error_html(f"No .ifc files found in {folder.name}"))
            return
        self._start_validation(files)

    def pick_files(self) -> None:
        import webview
        result = self.window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=True,
            file_types=("IFC Files (*.ifc)", "All files (*.*)"),
        )
        if not result:
            return
        files = [Path(p) for p in result]
        files = [f for f in files if f.is_file()]
        if not files:
            self._load(_error_html("No valid files selected"))
            return
        self._start_validation(files)

    def new_validation(self) -> None:
        self._load(_read_template("landing.html"))

    def export_excel(self) -> str | None:
        """Open save dialog and write Excel report. Returns saved path or None."""
        import webview
        if not self.results:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_dir = str(self.last_output_dir or Path.home())
        result = self.window.create_file_dialog(
            webview.SAVE_DIALOG,
            directory=default_dir,
            save_filename=f"ifc_mp_validation_{timestamp}.xlsx",
            file_types=("Excel Workbook (*.xlsx)",),
        )
        if not result:
            return None
        path = Path(result) if isinstance(result, str) else Path(result[0])
        if path.suffix.lower() != ".xlsx":
            path = path.with_suffix(".xlsx")
        excel_report.write_report(self.results, path)
        return str(path)

    def open_external(self, url: str) -> None:
        webbrowser.open(url)

    def exit_app(self) -> None:
        try:
            self.window.destroy()
        except Exception:
            pass

    def _load(self, content: str) -> None:
        path = _write_temp_html(content)
        with self._lock:
            self.tempfiles.append(path)
        self.window.load_url(path.as_uri())

    def _start_validation(self, files: list[Path]) -> None:
        output_dir = _determine_output_dir(files, self.explicit_output_dir)
        self.last_output_dir = output_dir
        self._load(_loading_html(files))
        threading.Thread(
            target=self._validate_and_render,
            args=(files, output_dir),
            daemon=True,
        ).start()

    def _progress(self, done: int, total: int, filename: str) -> None:
        try:
            script = (
                f"if (window.updateProgress) "
                f"window.updateProgress({done}, {total}, {json.dumps(filename)});"
            )
            self.window.evaluate_js(script)
        except Exception:
            pass

    def _validate_and_render(self, files: list[Path], output_dir: Path) -> None:
        try:
            results = batch.run_batch(
                files, show_progress=False, progress_callback=self._progress
            )
            self.results = results
            spa_html = app_html.render(results, output_dir)
            try:
                self._load(spa_html)
            except Exception as e:
                sys.stderr.write(f"GUI load_url failed: {type(e).__name__}: {e}\n")
                # Fallback: write the standalone report so the user has something
                html_path = _write_reports(results, output_dir)
                webbrowser.open(html_path.as_uri())
                try:
                    self.window.destroy()
                except Exception:
                    pass
        except Exception:
            traceback.print_exc()
            try:
                self._load(_error_html("Validation failed — see console for details"))
            except Exception:
                pass


def _try_gui(explicit_output_dir: Path | None) -> None:
    import webview

    bridge = GUIBridge(explicit_output_dir)
    landing_path = _write_temp_html(_read_template("landing.html"))
    bridge.tempfiles.append(landing_path)

    window = webview.create_window(
        title="IFC Material Passport Validator",
        url=landing_path.as_uri(),
        width=1280,
        height=820,
        resizable=True,
        js_api=bridge,
    )
    bridge.attach(window)

    try:
        webview.start(gui="edgechromium")
    finally:
        for p in list(bridge.tempfiles):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass


def launch(output_dir: Path | None = None) -> None:
    try:
        _try_gui(output_dir)
    except Exception as e:
        sys.stderr.write(
            f"GUI launch failed ({type(e).__name__}: {e}). "
            f"You can still use --file or --folder for CLI mode.\n"
        )
