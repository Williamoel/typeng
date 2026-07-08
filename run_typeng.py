"""typeng desktop launcher.

This entry point works from source and from a PyInstaller bundle. It starts the
local Flask server, opens the default browser, and keeps user data next to the
executable in packaged mode.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


HOST = "127.0.0.1"
PREFERRED_PORT = 5000
SERVER_READY_TIMEOUT_SECONDS = 30.0


def app_home() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def pick_port() -> int:
    for candidate in (PREFERRED_PORT, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind((HOST, candidate))
                return int(probe.getsockname()[1])
        except OSError:
            continue
    raise RuntimeError("No free local port available for typeng.")


def wait_until_ready(url: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return True
        except OSError:
            time.sleep(0.25)
    return False


def open_browser_when_ready(url: str) -> None:
    if wait_until_ready(url, SERVER_READY_TIMEOUT_SECONDS):
        webbrowser.open(url)
    else:
        print(f"typeng did not respond in time; open {url} manually.")


def main() -> None:
    home = app_home()
    os.environ.setdefault("TYPENG_HOME", str(home))
    (home / "data").mkdir(parents=True, exist_ok=True)
    (home / "resources" / "wordnet").mkdir(parents=True, exist_ok=True)
    (home / "resources" / "wiktionary").mkdir(parents=True, exist_ok=True)

    from app import app  # noqa: E402

    port = pick_port()
    url = f"http://{HOST}:{port}/"

    print("typeng is starting...")
    print(f"Data folder: {home / 'data'}")
    print(f"Open this address if the browser does not open automatically: {url}")
    print("Close this window or press Ctrl+C to stop typeng.")

    # Record the chosen URL so tooling (and users) can find the app even when
    # port 5000 was taken and we fell back to another port.
    try:
        (home / "data" / "server_url.txt").write_text(url, encoding="utf-8")
    except OSError:
        pass

    threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    app.run(host=HOST, port=port, debug=False, use_reloader=False, threaded=False)


if __name__ == "__main__":
    main()
