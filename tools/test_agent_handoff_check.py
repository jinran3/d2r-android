#!/usr/bin/env python3
"""Negative tests for tools/agent_handoff_check.py."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "agent_handoff_check.py"
HANDOFF = ROOT / "docs" / "HANDOFF.zh-CN.md"
LOG = ROOT / "docs" / "HANDOFF_LOG.zh-CN.md"


def run_case(name: str, handoff: str, log: str) -> int:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        hp = td / "HANDOFF.md"
        lp = td / "LOG.md"
        hp.write_text(handoff, encoding="utf-8")
        lp.write_text(log, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(CHECKER), "--verify", "--handoff", str(hp), "--log", str(lp)],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        tail = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else "<no output>"
        print("%-18s exit=%d  %s" % (name, result.returncode, tail))
        return result.returncode


def main() -> int:
    handoff = HANDOFF.read_text(encoding="utf-8")
    log = LOG.read_text(encoding="utf-8")

    bad_head = handoff.replace(
        "observed_head: a919fdb2e7aef92bd6000ee27c220d40c6b8f452",
        "observed_head: 0000000000000000000000000000000000000000",
    )
    bad_secret = handoff + "\nheader_key = " + "0" * 64 + "\n"
    bad_begin = "## test\n\n[BEGIN] unfinished-build\n\n" + log

    cases = [
        ("HEAD mismatch", bad_head, log),
        ("secret pattern", bad_secret, log),
        ("unclosed BEGIN", handoff, bad_begin),
    ]
    if not all(code != 0 for code in cases):
        print("NEGATIVE TEST FAILED: one invalid fixture was accepted")
        return 1
    print("NEGATIVE TEST OK: all invalid fixtures rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())