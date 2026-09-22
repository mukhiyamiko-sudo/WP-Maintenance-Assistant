from __future__ import annotations

import os
import subprocess
from pathlib import Path

from core.config import RuntimeConfig


def chrome_candidates() -> list[Path]:
    roots = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")]
    return [Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe" for root in roots if root]


def find_chrome_exe() -> Path | None:
    return next((path for path in chrome_candidates() if path.exists()), None)


def build_chrome_args(chrome: Path, config: RuntimeConfig, url: str) -> list[str]:
    return [
        str(chrome),
        f"--remote-debugging-port={config.debug_port}",
        f"--user-data-dir={config.chrome_profile_dir}",
        "--profile-directory=Default",
        "--new-window",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]


def launch_chrome_for_hostinger(config: RuntimeConfig, url: str) -> None:
    chrome = find_chrome_exe()
    if chrome is None:
        raise FileNotFoundError("Google Chrome was not found.")
    config.chrome_profile_dir.mkdir(parents=True, exist_ok=True)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(build_chrome_args(chrome, config, url), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
