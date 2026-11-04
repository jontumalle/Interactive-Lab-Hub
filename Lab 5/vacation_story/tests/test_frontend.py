"""One fixture-driven collection-to-reader check in an installed Chromium.

Run independently with pytest; no JS packages, model, voice or live API required.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import signal
import shutil
import subprocess
import threading

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_frontend_collection_through_story(tmp_path):
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if Path("/usr/lib/chromium/chromium").is_file():
        chromium = "/usr/lib/chromium/chromium"  # Avoid distro launcher extensions.
    if not chromium:
        pytest.skip("Chromium is not installed; run the manual frontend checklist")

    class Fixtures(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                html = (ROOT / "vacation_story/templates/index.html").read_text()
                html = html.replace("{{ url_for('static', filename='app.css') }}", "/vacation_story/static/app.css")
                html = html.replace("{{ url_for('static', filename='app.js') }}", "/vacation_story/static/app.js")
                html = html.replace("{{ url_for('static', filename='uploads.js') }}", "/vacation_story/static/uploads.js")
                html = html.replace("{{ url_for('static', filename='journal.js') }}", "/vacation_story/static/journal.js")
                html = html.replace("{{ url_for('static', filename='vendor/leaflet/leaflet.js') }}", "/vacation_story/static/vendor/leaflet/leaflet.js")
                html = html.replace("{{ url_for('static', filename='vendor/leaflet/leaflet.css') }}", "/vacation_story/static/vendor/leaflet/leaflet.css")
                html = html.replace("{{ url_for('static', filename='photo-clusters.js') }}", "/vacation_story/static/photo-clusters.js")
                html = html.replace("<head>", '<head><script src="/tests/fixtures/frontend-bootstrap.js"></script>')
                html = html.replace("</head>", '<script src="/tests/fixtures/frontend-runner.js" defer></script></head>')
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())
            else:
                super().do_GET()

        def log_message(self, *_args):
            pass

    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Fixtures, directory=str(ROOT)))
    except PermissionError:
        pytest.skip("Localhost sockets unavailable in sandbox; rerun frontend check with local server permissions")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        browser = subprocess.Popen([
            chromium, "--headless", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--no-first-run", "--disable-background-networking",
            "--disable-extensions", "--no-default-browser-check",
            f"--user-data-dir={tmp_path / 'chromium'}", "--virtual-time-budget=10000",
            "--dump-dom", f"http://127.0.0.1:{server.server_port}/",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = browser.communicate(timeout=55)
        except subprocess.TimeoutExpired:
            # Only this test's browser process group is terminated.
            os.killpg(browser.pid, signal.SIGKILL)
            browser.communicate()
            raise
        assert browser.returncode == 0, stderr[-3000:]
        result = stdout.split('<pre id="test-result">')[-1].split("</pre>")[0]
        assert result.startswith("PASS:"), result[-5000:]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
