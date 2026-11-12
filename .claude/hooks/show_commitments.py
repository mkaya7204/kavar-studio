"""SessionStart hook (D-70, user 2026-11-12: "başka oturumda bunu hiç dikkat etmeden ... kendi kafasına göre
yanlış yapmışsın"): every Claude session in this repo starts with the promise list in its context, so a new
session cannot begin work without seeing what was promised and what is still open. Stdout goes into the context."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8")
try:
    text = (ROOT / "COMMITMENTS.md").read_text(encoding="utf-8")
except OSError:
    text = "COMMITMENTS.md is MISSING. It holds every promise made to the user: restore it from git before any work."
print("KAVAR: the promises to the user (COMMITMENTS.md). Start from this list; report its changes at every "
      "'yükle'; a line is done only with a run's evidence; never drop a line without the user's OK.\n")
print(text)
