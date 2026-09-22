from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from core.errors import LoginRequiredError


class LoginState(Enum):
    WAITING = "waiting"
    DETECTED = "detected"
    CONFIRMED = "confirmed"


@dataclass(frozen=True)
class LoginStatus:
    state: LoginState
    is_logged_in: bool
    reason: str


class LoginGate:
    def __init__(self, driver):
        self.driver = driver
        self.state = LoginState.WAITING

    def detect(self) -> LoginStatus:
        url = str(getattr(self.driver, "current_url", ""))
        title = str(getattr(self.driver, "title", ""))
        data = self.driver.execute_script("""
const text = document.body ? (document.body.innerText || '') : '';
const path = location.pathname || '';
const domainRe = /\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b/ig;
return {
  hostinger_app: /hpanel\.hostinger\.com/i.test(location.hostname),
  websites_marker: /websites|website|网站|站点|domain|域名/i.test(text) || /\/websites/i.test(path),
  domain_count: new Set(text.match(domainRe) || []).size,
  has_login_form: Boolean(document.querySelector('input[type="password"], form[action*="login" i]')),
  logged_out_marker: /\/login|\/auth|\/signin/i.test(path),
  security_challenge: /verify you are human|human verification|cloudflare|just a moment/i.test(text + document.title)
};
""") or {}
        logged_in = bool(data.get("hostinger_app") and data.get("websites_marker") and data.get("domain_count", 0) and not data.get("has_login_form") and not data.get("logged_out_marker") and not data.get("security_challenge"))
        if logged_in:
            self.state = LoginState.DETECTED
            return LoginStatus(self.state, True, "Hostinger website list detected")
        return LoginStatus(LoginState.WAITING, False, f"Waiting for manual login ({url or title or 'unknown'})")

    def confirm_and_validate(self, confirm_callback: Callable[[], bool]) -> None:
        if not confirm_callback():
            raise LoginRequiredError("Manual Hostinger login was not confirmed")
        status = self.detect()
        if not status.is_logged_in:
            raise LoginRequiredError("Login validation failed; keep the Hostinger website list open")
        self.state = LoginState.CONFIRMED
