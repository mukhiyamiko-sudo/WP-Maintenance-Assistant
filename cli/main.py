from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.app_service import AutomationService
from core.config import RuntimeConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hostinger WordPress Maintenance Toolkit")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--scan", action="store_true", help="scan sites after manual Hostinger login")
    group.add_argument("--run-selected", nargs="+", metavar="DOMAIN", help="maintain selected domains")
    parser.add_argument("--debug-port", type=int, default=9222)
    parser.add_argument("--log-dir", type=Path, default=Path("logs"))
    return parser


def main(argv: list[str] | None = None, service_factory=AutomationService) -> int:
    args = build_parser().parse_args(argv)
    service = service_factory(RuntimeConfig(debug_port=args.debug_port, log_dir=args.log_dir))
    try:
        service.connect()
        sites = service.confirm_login_and_scan(lambda: True)
        if args.scan:
            print(f"Found {len(sites)} WordPress sites")
            for site in sites:
                print(f"- {site.domain}")
            return 0
        wanted = {domain.lower() for domain in args.run_selected}
        for site in sites:
            site.selected = site.domain.lower() in wanted
        summary = service.run_selected(sites, manual_prompt=lambda _domain, _seconds: False)
        print(f"Complete: {summary.success_count} successful, {summary.failure_count} failed")
        return 0 if not summary.failure_count else 1
    except Exception as exc:
        print(f"Task failed: {exc}", file=sys.stderr)
        return 2
