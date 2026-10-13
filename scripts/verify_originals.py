"""Check the two user's input files have not changed during M0 implementation."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "升学咨询智能体_开发方案与审查.md": "a69f01f4db5f2a2c49a4c89dd92138e10fbc51a129406834bbb2cce2a4aac2f1",
    "Codex_升学智能体_首次开发Prompt.txt": "6db9dd8c2d17ee3c4c261a3eae69f9e258fbe4294dcee6a8726eb05cdf2f05eb",
}

for name, expected in EXPECTED.items():
    actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Changed: {name}")
    print(f"UNCHANGED: {name}")
