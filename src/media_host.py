"""Serve a few local files at a temporary public HTTPS URL, for Instagram to fetch.

The Instagram publishing API only takes media by URL. A local HTTP server serves a
fresh folder holding just the files of one post, and a Cloudflare quick tunnel
(tools/cloudflared.exe, no account) exposes it as https://<random>.trycloudflare.com
for the few minutes the upload takes. Nothing else on the machine is reachable.

    with public_files([path1, path2]) as urls:
        ...  # urls[i] is the public URL of path i
"""

import contextlib
import functools
import http.server
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CLOUDFLARED = ROOT / "tools" / "cloudflared.exe"
TUNNEL_TIMEOUT = 90  # seconds to get a public URL that answers


class HostError(RuntimeError):
    pass


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@contextlib.contextmanager
def public_files(paths: list[Path | str]):
    """Yield public URLs for `paths` (same order); everything is torn down afterwards."""
    if not CLOUDFLARED.exists():
        raise HostError(f"missing {CLOUDFLARED}")
    folder = Path(tempfile.mkdtemp(prefix="kavar_pub_"))
    # random names: the URL can't be guessed and old files are never served
    names = []
    for p in paths:
        p = Path(p)
        name = f"{uuid.uuid4().hex}{p.suffix.lower()}"
        shutil.copy(p, folder / name)
        names.append(name)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
                                             functools.partial(_QuietHandler, directory=str(folder)))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    tunnel = subprocess.Popen(
        [str(CLOUDFLARED), "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        base = _tunnel_url(tunnel)
        urls = [f"{base}/{n}" for n in names]
        _wait_reachable(urls[0])
        yield urls
    finally:
        tunnel.terminate()
        try:
            tunnel.wait(10)
        except subprocess.TimeoutExpired:
            tunnel.kill()
        server.shutdown()
        shutil.rmtree(folder, ignore_errors=True)


def _tunnel_url(tunnel: subprocess.Popen) -> str:
    found: list[str] = []

    def read():
        for line in tunnel.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not found:
                found.append(m.group(0))

    threading.Thread(target=read, daemon=True).start()
    t0 = time.time()
    while not found:
        if tunnel.poll() is not None:
            raise HostError("cloudflared exited before giving a URL")
        if time.time() - t0 > TUNNEL_TIMEOUT:
            raise HostError("cloudflared gave no URL in time")
        time.sleep(0.5)
    return found[0]


def _wait_reachable(url: str) -> None:
    """The quick tunnel's DNS takes a few seconds to answer after the URL is printed."""
    t0 = time.time()
    while time.time() - t0 < TUNNEL_TIMEOUT:
        try:
            if requests.head(url, timeout=10).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(3)
    raise HostError(f"public URL never answered: {url}")


if __name__ == "__main__":
    import sys

    with public_files(sys.argv[1:]) as urls:
        for u in urls:
            r = requests.get(u, timeout=20)
            print(r.status_code, r.headers.get("content-type"), len(r.content), u)
