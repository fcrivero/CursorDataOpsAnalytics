"""Fetch live Jira data, print chat markdown audit, write Excel workbook."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def main() -> None:
    py = sys.executable
    subprocess.check_call([py, str(SCRIPTS / "skrull_fetch_checks.py")])
    subprocess.check_call([py, str(SCRIPTS / "generate_report.py")])


if __name__ == "__main__":
    main()
