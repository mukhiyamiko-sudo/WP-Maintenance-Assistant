from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from urllib.request import urlopen

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from core.chrome_launcher import launch_chrome_for_hostinger
from core.config import RuntimeConfig, runtime_base_dir
from core.errors import BrowserConnectionError

HOSTINGER_HOME_URL = "https://hpanel.hostinger.com/"


class BrowserManager:
    def __init__(
        self,
        config: RuntimeConfig,
        driver=None,
        driver_factory=None,
        options_factory=Options,
        chrome_launcher=launch_chrome_for_hostinger,
        sleeper: Callable[[float], None] = time.sleep,
        debug_port_checker=None,
        driver_path: str | None = None,
        driver_paths: list[str] | None = None,
    ):
        self.config = config
        self.driver = driver
        self.driver_factory = driver_factory
        self.options_factory = options_factory
        self.chrome_launcher = chrome_launcher
        self.sleeper = sleeper or time.sleep
        self.debug_port_checker = debug_port_checker or debug_port_ready
        self.driver_paths = driver_paths or ([driver_path] if driver_path else default_chromedriver_paths())
        self.hostinger_handle = None
        self.automation_handles: set[str] = set()

    def connect(self):
        if self.driver is not None:
            self.hostinger_handle = getattr(self.driver, "current_window_handle", None)
            return self.driver
        try:
            if not self.debug_port_checker(self.config):
                self.chrome_launcher(self.config, HOSTINGER_HOME_URL)
            self.driver = self._connect_with_retry(20)
            self.hostinger_handle = getattr(self.driver, "current_window_handle", None)
            return self.driver
        except Exception as exc:
            raise BrowserConnectionError(f"Unable to connect to Chrome on 127.0.0.1:{self.config.debug_port}: {exc}") from exc

    def _connect_with_retry(self, attempts: int):
        last_error = None
        for _ in range(attempts):
            try:
                if self.debug_port_checker(self.config):
                    return self._connect_existing()
            except Exception as exc:
                last_error = exc
            self.sleeper(0.5)
        raise last_error or BrowserConnectionError("Chrome DevTools port did not become ready")

    def _connect_existing(self):
        options = self.options_factory()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.config.debug_port}")
        if self.driver_factory:
            driver = self.driver_factory(options)
        else:
            existing = next((path for path in self.driver_paths if Path(path).exists()), None)
            driver = webdriver.Chrome(service=Service(existing) if existing else Service(), options=options)
        driver.set_page_load_timeout(self.config.first_load_timeout)
        return driver

    def is_connected(self) -> bool:
        return bool(self.driver and getattr(self.driver, "session_id", None))

    def open_site_tab(self, url: str) -> str:
        if not self.driver:
            raise BrowserConnectionError("Chrome is not connected")
        before = set(self.driver.window_handles)
        self.driver.execute_script("window.open(arguments[0], '_blank');", url)
        handle = next(iter(set(self.driver.window_handles) - before), None)
        if not handle:
            raise BrowserConnectionError("WordPress tab did not open")
        self.automation_handles.add(handle)
        self.driver.switch_to.window(handle)
        return handle

    def close_tab(self, handle: str) -> None:
        if self.driver and handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            self.driver.close()
        self.automation_handles.discard(handle)
        self.restore_hostinger_tab()

    def restore_hostinger_tab(self) -> None:
        if self.driver and self.hostinger_handle in getattr(self.driver, "window_handles", []):
            self.driver.switch_to.window(self.hostinger_handle)

    def close_automation_tabs(self) -> None:
        for handle in list(self.automation_handles):
            self.close_tab(handle)


def debug_port_ready(config: RuntimeConfig) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{config.debug_port}/json/version", timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


def default_chromedriver_paths() -> list[str]:
    base = runtime_base_dir()
    candidates = [base / "chromedriver.exe", Path.cwd() / "chromedriver.exe"]
    return [str(path) for path in dict.fromkeys(candidates) if path.exists()]


def default_chromedriver_path() -> str | None:
    return next(iter(default_chromedriver_paths()), None)
