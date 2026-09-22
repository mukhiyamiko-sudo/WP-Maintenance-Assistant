from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path


def runtime_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RuntimeConfig:
    debug_port: int = 9222
    first_load_timeout: int = 60
    retry_load_timeout: int = 60
    manual_prompt_timeout: int = 180
    auto_scan_delay_seconds: int = 8
    update_wait_min: int = 30
    update_wait_max: int = 60
    log_dir: Path = field(default_factory=lambda: runtime_base_dir() / "logs")
    chrome_profile_dir: Path = field(default_factory=lambda: runtime_base_dir() / "chrome_profile")

    def __post_init__(self) -> None:
        if self.debug_port <= 0:
            raise ValueError("debug_port must be positive")
        if not 30 <= self.update_wait_min <= 60 or not 30 <= self.update_wait_max <= 60:
            raise ValueError("update wait must stay within 30-60 seconds")
        if self.update_wait_min > self.update_wait_max:
            raise ValueError("update_wait_min cannot exceed update_wait_max")
        if not 5 <= self.auto_scan_delay_seconds <= 10:
            raise ValueError("auto_scan_delay_seconds must stay within 5-10 seconds")
