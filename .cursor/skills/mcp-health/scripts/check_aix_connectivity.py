#!/usr/bin/env python3
"""Check AIX Manager CLI connectivity for Teams, SharePoint, and Google Docs."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AIX_SERVICES: list[dict[str, Any]] = [
    {
        "name": "Microsoft Teams",
        "type": "AIX CLI",
        "cli": "teams",
        "telemetry_tool": "teams",
        "auth_cli": "teams",
        "auth_args": ["--agent", "auth", "status"],
        "probe_args": ["--agent", "chat", "list", "--limit", "1"],
        "auth_field": "usable",
    },
    {
        "name": "SharePoint",
        "type": "AIX CLI",
        "cli": "udoc",
        "telemetry_tool": "udoc",
        "auth_cli": "teams",
        "auth_args": ["--agent", "auth", "status"],
        "probe_args": [
            "--agent",
            "search",
            "documents",
            "--query",
            "report",
            "--limit",
            "1",
            "--provider",
            "microsoft",
        ],
        "auth_field": "usable",
        "notes": "SharePoint/OneDrive via udoc; MS Graph token shared with Teams/Outlook",
    },
    {
        "name": "Google Docs",
        "type": "AIX CLI",
        "cli": "gdrive",
        "telemetry_tool": "gdrive",
        "auth_cli": "gdrive",
        "auth_args": ["--agent", "auth", "status"],
        "probe_args": ["--agent", "search", "recent", "--limit", "1"],
        "auth_field": "authenticated",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--aix-root",
        default=str(Path.home() / ".aix"),
        help="Path to ~/.aix (default: %(default)s)",
    )
    parser.add_argument(
        "--skip-probe",
        action="store_true",
        help="Check auth status only; skip live API probes",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser.parse_args()


def resolve_cli(aix_bin: Path, name: str) -> Path | None:
    for candidate in (aix_bin / f"{name}.exe", aix_bin / name):
        if candidate.is_file():
            return candidate
    return None


def run_json_cli(cli: Path, args: list[str], timeout: int = 60) -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = subprocess.run(
            [str(cli), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return None, "probe timed out"
    except OSError as exc:
        return None, str(exc)

    stdout = (result.stdout or "").strip()
    if not stdout:
        return None, (result.stderr or "empty response").strip() or f"exit {result.returncode}"

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None, stdout[:200]

    if result.returncode != 0 and payload.get("status") != "success":
        err = payload.get("error") or payload.get("message") or f"exit {result.returncode}"
        return payload, str(err)

    return payload, None


def auth_ok(payload: dict[str, Any] | None, field: str) -> bool:
    if not payload or payload.get("status") != "success":
        return False
    data = payload.get("data") or {}
    return bool(data.get(field))


def scan_telemetry(aix_root: Path) -> dict[str, dict[str, Any]]:
    usage: dict[str, dict[str, Any]] = {}
    events_file = aix_root / "telemetry" / "events.ndjson"
    if not events_file.is_file():
        return usage

    for line in events_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        tool = event.get("tool")
        if tool not in {"teams", "gdrive", "udoc"}:
            continue
        if not event.get("success"):
            continue
        command = str(event.get("command") or "")
        if command.startswith("auth"):
            continue

        ts_raw = event.get("ts")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        except ValueError:
            continue

        prev = usage.get(tool)
        if prev is None or ts > prev["last_used_dt"]:
            usage[tool] = {
                "last_used_dt": ts,
                "last_used": ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "last_command": command or "(startup)",
            }

    return usage


def check_aix_platform(aix_root: Path) -> dict[str, Any]:
    aix_bin = aix_root / "bin"
    aix_cli = resolve_cli(aix_bin, "aix")
    path_parts = [
        part.lower()
        for part in __import__("os").environ.get("PATH", "").split(";")
        if part
    ]
    return {
        "installed": aix_bin.is_dir(),
        "bin_on_path": any(str(aix_bin).lower() in part for part in path_parts),
        "aix_cli": str(aix_cli) if aix_cli else None,
    }


def evaluate_service(
    service: dict[str, Any],
    aix_bin: Path,
    telemetry: dict[str, dict[str, Any]],
    skip_probe: bool,
) -> dict[str, Any]:
    cli = resolve_cli(aix_bin, service["cli"])
    auth_cli = resolve_cli(aix_bin, service["auth_cli"])
    telemetry_hit = telemetry.get(service["telemetry_tool"])

    row: dict[str, Any] = {
        "name": service["name"],
        "type": service["type"],
        "cli": service["cli"],
        "health": "Unknown",
        "auth": "Unknown",
        "connectivity": "Not tested" if skip_probe else "Unknown",
        "last_used": telemetry_hit["last_used"] if telemetry_hit else "Never",
        "account": "",
        "notes": service.get("notes", ""),
    }

    if cli is None or auth_cli is None:
        row["health"] = "Not Installed"
        row["auth"] = "CLI missing"
        row["connectivity"] = "N/A"
        row["notes"] = (row["notes"] + " Run AIX Manager or `aix setup`.").strip()
        return row

    auth_payload, auth_err = run_json_cli(auth_cli, service["auth_args"], timeout=30)
    if auth_ok(auth_payload, service["auth_field"]):
        row["auth"] = "Authenticated"
        data = (auth_payload or {}).get("data") or {}
        row["account"] = str(data.get("email") or data.get("user") or "")
    else:
        row["auth"] = "Needs Auth"
        row["health"] = "Needs Auth"
        row["connectivity"] = "Blocked"
        if auth_err:
            row["notes"] = (row["notes"] + f" {auth_err}").strip()
        row["notes"] = (row["notes"] + " Re-sign in via AIX Manager → Auth.").strip()
        return row

    if skip_probe:
        row["health"] = "Authenticated"
        row["connectivity"] = "Skipped"
        return row

    probe_payload, probe_err = run_json_cli(cli, service["probe_args"], timeout=90)
    if probe_payload and probe_payload.get("status") == "success":
        row["health"] = "Healthy"
        row["connectivity"] = "OK"
    else:
        row["health"] = "Degraded"
        row["connectivity"] = "Probe failed"
        row["notes"] = (row["notes"] + f" {probe_err or 'live probe failed'}").strip()

    return row


def main() -> int:
    args = parse_args()
    aix_root = Path(args.aix_root)
    aix_bin = aix_root / "bin"
    platform = check_aix_platform(aix_root)
    telemetry = scan_telemetry(aix_root)

    services = [
        evaluate_service(service, aix_bin, telemetry, args.skip_probe)
        for service in AIX_SERVICES
    ]

    healthy = sum(
        1 for s in services if s["health"] in ("Healthy", "Authenticated")
    )
    payload = {
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "aix_platform": platform,
        "services": services,
        "summary": {
            "healthy": healthy,
            "total": len(services),
            "needs_attention": [
                s["name"]
                for s in services
                if s["health"] not in ("Healthy", "Authenticated")
            ],
        },
    }

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
