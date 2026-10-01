"""Acquire a guest WB browser session on the host for the local Django stack.

Wildberries currently rejects the same browser fingerprint inside Docker.
The helper only serves a Unix socket in this checkout and accepts no URLs.
"""

import json
import os
import socketserver
import subprocess
import time
import uuid
from pathlib import Path

from camoufox.sync_api import Camoufox


SOCKET = Path(__file__).resolve().parents[1] / ".wb_browser.sock"


def browser_session():
    with Camoufox(headless=True, humanize=True, locale="ru-RU", os="windows") as browser:
        page = browser.new_page()
        page.goto("https://www.wildberries.ru/", wait_until="domcontentloaded", timeout=60000)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            cookies = {cookie["name"]: cookie["value"] for cookie in page.context.cookies()}
            if cookies.get("x_wbaas_token") and cookies.get("_wbauid"):
                return {
                    "token": cookies["x_wbaas_token"],
                    "wbauid": cookies["_wbauid"],
                    "user_agent": page.evaluate("() => navigator.userAgent"),
                    "deviceid": f"site_{uuid.uuid4().hex}",
                }
            time.sleep(1)
    raise RuntimeError("WB did not issue a complete browser session")


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            request = json.loads(self.rfile.readline(1024))
            if request != {"action": "session"}:
                raise ValueError("Unsupported request")
            response = browser_session()
        except Exception as error:
            response = {"error": type(error).__name__}
        self.wfile.write((json.dumps(response) + "\n").encode())


if __name__ == "__main__":
    SOCKET.unlink(missing_ok=True)
    with socketserver.UnixStreamServer(str(SOCKET), Handler) as server:
        os.chmod(SOCKET, 0o600)
        subprocess.run(["setfacl", "-m", "u:10001:rw", str(SOCKET)], check=True)
        try:
            server.serve_forever()
        finally:
            SOCKET.unlink(missing_ok=True)
