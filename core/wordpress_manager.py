from __future__ import annotations

import time
from collections.abc import Callable

from core.config import RuntimeConfig
from core.errors import SiteLoadError, UpdateFlowError
from core.models import UpdateOutcome, UpdateState


class WordPressManager:
    def __init__(
        self,
        driver,
        config: RuntimeConfig,
        sleeper: Callable[[float], None] | None = time.sleep,
    ) -> None:
        self.driver = driver
        self.config = config
        self.sleeper = sleeper if callable(sleeper) else time.sleep

    def _wp_loaded_marker(self) -> bool:
        return bool(
            self.driver.execute_script(
                r"""
/* WP_AUTOMATION_LOAD_MARKER_V2 */
const urlOk = /\/wp-admin(?:\/|$)/i.test(location.pathname) || /wp-admin/i.test(location.href);
const menu = document.querySelector('#adminmenu, #wpadminbar, .wp-admin');
const welcome = Array.from(document.querySelectorAll('h1,h2,.welcome-panel')).some((el) => /welcome to wordpress/i.test(el.innerText || ''));
return Boolean(urlOk && (menu || welcome));
"""
            )
        )

    def _wait_for_loaded(self, timeout: int) -> bool:
        deadline = time.monotonic() + max(1, timeout)
        while time.monotonic() < deadline:
            if self._wp_loaded_marker():
                return True
            self.sleeper(min(1.0, max(0.1, timeout / 20)))
        return False

    def _wait_document_ready(self, timeout: int) -> bool:
        deadline = time.monotonic() + max(1, timeout)
        while time.monotonic() < deadline:
            try:
                if self.driver.execute_script("return document.readyState") == "complete":
                    return True
            except Exception:
                pass
            self.sleeper(min(1.0, max(0.1, timeout / 20)))
        return False

    def _wait_for_admin_page(self, page: str, timeout: int) -> bool:
        deadline = time.monotonic() + max(1, timeout)
        while time.monotonic() < deadline:
            try:
                if self.driver.execute_script(
                    r"""
/* WP_AUTOMATION_ADMIN_PAGE_READY_V4 */
const page = String(arguments[0] || '').toLowerCase();
const path = String(location.pathname || '').toLowerCase();
const isDashboard = page === 'index.php' && /\/wp-admin\/?$/.test(path);
return document.readyState === 'complete' && (isDashboard || path.endsWith('/' + page));
""",
                    page,
                ):
                    return True
            except Exception:
                pass
            self.sleeper(0.5)
        return False

    def open_admin_page(self, page: str) -> None:
        dashboard_opened = self.driver.execute_script(
            r"""
/* WP_AUTOMATION_DASHBOARD_NAV_V4 */
const links = Array.from(document.querySelectorAll('#adminmenu a[href]'));
const link = links.find((candidate) => {
  const href = candidate.href || candidate.getAttribute('href') || '';
  return /\/wp-admin\/(?:index\.php)?(?:$|[?#])/i.test(href);
});
if (link) {
  link.click();
  return true;
}
const adminRoot = location.href.match(/^(.*?\/wp-admin)(?:\/|$)/i)?.[1];
if (!adminRoot) return false;
location.href = `${adminRoot}/index.php`;
return true;
"""
        )
        if not dashboard_opened or not self._wait_for_admin_page(
            "index.php", self.config.first_load_timeout
        ):
            raise SiteLoadError("无法打开 WordPress 后台 Dashboard 页面")

        updates_opened = self.driver.execute_script(
            r"""
/* WP_AUTOMATION_UPDATES_NAV_V4 */
const page = arguments[0];
const links = Array.from(document.querySelectorAll('#adminmenu a[href]'));
const link = links.find((candidate) => {
  const href = candidate.href || candidate.getAttribute('href') || '';
  return href.includes('/wp-admin/' + page) || href.endsWith(page) || href.includes(page);
});
if (link) {
  link.click();
  return true;
}
const adminRoot = location.href.match(/^(.*?\/wp-admin)(?:\/|$)/i)?.[1];
if (!adminRoot) return false;
location.href = `${adminRoot}/${page}`;
return true;
""",
            page,
        )
        if not updates_opened or not self._wait_for_admin_page(
            page, self.config.first_load_timeout
        ):
            raise SiteLoadError(f"WordPress 后台页面在等待时间内未加载完成：{page}")

    def wait_until_loaded(self, domain: str, manual_prompt=None) -> None:
        if self._wait_for_loaded(self.config.first_load_timeout):
            return
        if manual_prompt and manual_prompt(domain, self.config.manual_prompt_timeout):
            if self._wait_for_loaded(self.config.retry_load_timeout):
                return
        raise SiteLoadError(f"{domain} WordPress 后台在等待时间内未加载成功")

    def read_update_state(self) -> UpdateState:
        payload = self.driver.execute_script(
            r"""
/* WP_AUTOMATION_UPDATE_STATE_V2 */
const pluginForm = document.querySelector("form[name='upgrade-plugins']");
const themeForm = document.querySelector("form[name='upgrade-themes']");
const names = (form) => form ? Array.from(form.querySelectorAll("input[type='checkbox'][name='checked[]']"))
  .map((box) => box.closest('tr,li,.plugin-card,.theme')?.innerText?.split('\n').map((x) => x.trim()).find(Boolean) || '')
  .filter(Boolean) : [];
const coreForm = Array.from(document.querySelectorAll('form')).find((form) => {
  const action = (form.getAttribute('action') || '').toLowerCase();
  return action.includes('do-core-upgrade') && !action.includes('do-core-reinstall');
});
return {
  plugin_names: names(pluginForm),
  theme_names: names(themeForm),
  has_core_update: Boolean(coreForm && coreForm.querySelector('[type="submit"][name="upgrade"]')),
  reinstall_controls_ignored: true
};
"""
        ) or {}
        return UpdateState(
            plugin_names=list(payload.get("plugin_names") or []),
            theme_names=list(payload.get("theme_names") or []),
            has_core_update=bool(payload.get("has_core_update")),
            reinstall_controls_ignored=bool(payload.get("reinstall_controls_ignored", True)),
        )

    def _updates_badge_count(self) -> int:
        payload = self.driver.execute_script(
            r"""
/* WP_AUTOMATION_UPDATES_BADGE_V1 */
const visible = (el) => {
  if (!el || !el.getBoundingClientRect) return false;
  const style = window.getComputedStyle(el);
  const box = el.getBoundingClientRect();
  return style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
};
const links = Array.from(document.querySelectorAll('#adminmenu a[href*="update-core.php"]')).filter(visible);
const link = links.find((candidate) => /updates|更新/i.test(candidate.innerText || candidate.textContent || '')) || links[0];
if (!link) return {count: 0, text: ''};
const container = link.closest('li') || link;
const badgeSelectors = [
  '.update-plugins',
  '.plugin-count',
  '.update-count',
  '.awaiting-mod',
  '.count',
  '.badge'
];
const badgeText = badgeSelectors
  .flatMap((selector) => Array.from(container.querySelectorAll(selector)))
  .filter(visible)
  .map((el) => el.innerText || el.textContent || '')
  .join(' ');
const text = `${badgeText} ${link.innerText || link.textContent || ''}`;
const numbers = (text.match(/\d+/g) || []).map((item) => parseInt(item, 10)).filter((item) => item > 0);
return {count: numbers.length ? Math.max(...numbers) : 0, text};
"""
        ) or {}
        try:
            return int(payload.get("count") or 0)
        except Exception:
            return 0

    def _has_translation_update(self) -> bool:
        return bool(
            self.driver.execute_script(
                r"""
/* WP_AUTOMATION_TRANSLATION_UPDATE_V1 */
const form = document.querySelector("form[name='upgrade-translations']");
if (!form) return false;
const button = form.querySelector("#upgrade-translations,input[name='upgrade'],button[type='submit']");
return Boolean(button && !button.disabled);
"""
            )
        )

    def _submit_update(self, kind: str) -> None:
        submitted = self.driver.execute_script(
            r"""
/* WP_AUTOMATION_SUBMIT_UPDATE_V2 */
const kind = arguments[0];
if (kind === 'plugins') {
  const form = document.querySelector("form[name='upgrade-plugins']");
  if (!form) return false;
  form.querySelectorAll("input[type='checkbox'][name='checked[]']").forEach((box) => { box.checked = true; });
  const button = form.querySelector("#upgrade-plugins,input[name='upgrade']");
  if (!button) return false;
  button.click();
  return true;
}
if (kind === 'themes') {
  const form = document.querySelector("form[name='upgrade-themes']");
  if (!form) return false;
  form.querySelectorAll("input[type='checkbox'][name='checked[]']").forEach((box) => { box.checked = true; });
  const button = form.querySelector("#upgrade-themes,input[name='upgrade']");
  if (!button) return false;
  button.click();
  return true;
}
if (kind === 'translations') {
  const form = document.querySelector("form[name='upgrade-translations']");
  if (!form) return false;
  const button = form.querySelector("#upgrade-translations,input[name='upgrade'],button[type='submit']");
  if (!button || button.disabled) return false;
  button.click();
  return true;
}
const form = Array.from(document.querySelectorAll('form')).find((candidate) => {
  const action = (candidate.getAttribute('action') || '').toLowerCase();
  return action.includes('do-core-upgrade') && !action.includes('do-core-reinstall');
});
const button = form?.querySelector(
  '[type="submit"][name="upgrade"].button-primary, [type="submit"][name="upgrade"]'
);
if (!button) return false;
button.click();
return true;
""",
            kind,
        )
        if not submitted:
            raise UpdateFlowError(f"未找到可执行的 {kind} 更新操作")

    def _update_completion_marker(self, kind: str) -> bool:
        return bool(
            self.driver.execute_script(
                r"""
/* WP_AUTOMATION_UPDATE_COMPLETE_V4 */
const kind = arguments[0];
const visible = (element) => {
  if (!element || !element.getBoundingClientRect) return false;
  const style = window.getComputedStyle(element);
  const box = element.getBoundingClientRect();
  return style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
};
const content = document.querySelector('#wpbody-content, #wpbody, .wrap') || document.body;
const links = Array.from(content.querySelectorAll('a[href]')).filter(visible);
const text = (link) => (link.innerText || link.textContent || '').trim().toLowerCase();
const linkTargets = new Set(links.map((link) => new URL(link.href, location.href).pathname.toLowerCase()));
const hasTarget = (page) => Array.from(linkTargets).some((path) => path.endsWith('/' + page));
if (kind === 'core') {
  const pageText = (content.innerText || content.textContent || '').replace(/\s+/g, ' ').trim();
  const welcome = /welcome\s+to\s+wordpress|欢迎使用\s*wordpress/i.test(pageText);
  const version = /\b\d+\.\d+(?:\.\d+)?\b/.test(pageText);
  return welcome && version;
}
if (kind === 'plugins') {
  return hasTarget('plugins.php') && hasTarget('update-core.php');
}
if (kind === 'themes') {
  return hasTarget('themes.php') && hasTarget('update-core.php');
}
return links.some((link) => /(?:go to|return to).*(?:wordpress )?updates? page|(?:转到|返回).*更新.*页面/i.test(text(link)));
""",
                kind,
            )
        )

    def _wait_after_update(self, kind: str) -> None:
        deadline = time.monotonic() + max(1, self.config.update_wait_max)
        while time.monotonic() < deadline:
            if self._update_completion_marker(kind):
                return
            self.sleeper(1.5)
        raise UpdateFlowError(f"{kind} 更新在等待时间内未出现完成标志")

    def update_site(self, domain: str) -> UpdateOutcome:
        plugins: list[str] = []
        themes: list[str] = []
        core_updated = False
        clear_update_checks = 0
        required_clear_update_checks = 3

        for _ in range(30):
            self.open_admin_page("update-core.php")
            state = self.read_update_state()

            if state.has_core_update:
                clear_update_checks = 0
                self._submit_update("core")
                core_updated = True
                self._wait_after_update("core")
                continue

            if state.theme_names:
                clear_update_checks = 0
                themes.extend(item for item in state.theme_names if item not in themes)
                self._submit_update("themes")
                self._wait_after_update("themes")
                continue

            if state.plugin_names:
                clear_update_checks = 0
                plugins.extend(item for item in state.plugin_names if item not in plugins)
                self._submit_update("plugins")
                self._wait_after_update("plugins")
                continue

            if self._has_translation_update():
                clear_update_checks = 0
                self._submit_update("translations")
                self._wait_after_update("translations")
                continue

            if self._updates_badge_count() > 0:
                clear_update_checks = 0
                self.sleeper(1.5)
                continue

            clear_update_checks += 1
            if clear_update_checks >= required_clear_update_checks:
                return UpdateOutcome(plugins, themes, core_updated)

            self.sleeper(1.5)

        raise UpdateFlowError(f"{domain} 更新循环超过保护上限")
