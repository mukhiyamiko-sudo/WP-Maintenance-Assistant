from __future__ import annotations

import re
import time
from collections.abc import Callable
from urllib.parse import urljoin

from core.config import RuntimeConfig
from core.models import Site


DOMAIN_RE = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b", re.I)
HOSTINGER_BASE_URL = "https://hpanel.hostinger.com"


def hostinger_site_discovery_script() -> str:
    return r"""
/* WP_AUTOMATION_DISCOVERY_V3_DOMAIN_ROW_SAFE */
const targetDomain = '';
const domainRe = /\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b/ig;
const wpAdminTextPattern = /\bwp\s*admin\b|wp-admin|wp_admin|wpadmin|wordpress\s*admin|wordpress\s*administrator|open\s+wordpress|manage\s+wordpress|WordPress\s*管理员|WordPress\s*管理/i;
const controlSelector = 'a,button,[role="button"],[tabindex]';
const blockedDomains = new Set(['node.js', 'hostinger.com', 'www.hostinger.com', 'hpanel.hostinger.com', 'cloudflare.com', 'www.cloudflare.com']);
const blockedSuffixes = ['.hostinger.com', '.cloudflare.com', '.cloudflare.net', '.cloudflarestatus.com', '.google.com', '.facebook.com', '.youtube.com'];

const visible = (el) => {
  if (!el || !el.getBoundingClientRect) return false;
  const style = window.getComputedStyle(el);
  const box = el.getBoundingClientRect();
  return style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
};
const enabled = (el) => !el.disabled && el.getAttribute('aria-disabled') !== 'true';
const textOf = (el) => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
const attr = (el, name) => (el.getAttribute(name) || '').toLowerCase();
const attrsOf = (el) => {
  const names = ['data-testid', 'data-test', 'data-qa', 'aria-label', 'title', 'id', 'class', 'role'];
  const result = {};
  for (const name of names) result[name] = el.getAttribute(name) || '';
  return result;
};
const normalizeDomain = (domain) => String(domain || '').toLowerCase().replace(/^www\./, '');
const isDomainAllowed = (domain) => {
  const normalized = normalizeDomain(domain);
  return Boolean(normalized) &&
    !blockedDomains.has(normalized) &&
    !blockedSuffixes.some((suffix) => normalized.endsWith(suffix));
};
const domainsIn = (text) => Array.from(new Set((String(text || '').match(domainRe) || []).map(normalizeDomain).filter(isDomainAllowed)));
const controlData = (el) => [
  textOf(el), attr(el, 'id'), attr(el, 'class'), attr(el, 'href'), attr(el, 'aria-label'),
  attr(el, 'title'), attr(el, 'data-testid'), attr(el, 'data-test'), attr(el, 'data-qa'),
  (el.innerHTML || '').toLowerCase()
].join(' ');
const isWpAdminControl = (el) => wpAdminTextPattern.test(controlData(el)) && !/dashboard\s+builder|control\s+panel|billing|invoice|delete/i.test(controlData(el));
const controlsOf = (row) => Array.from(row.querySelectorAll(controlSelector))
  .filter((el) => visible(el) && enabled(el))
  .map((el) => ({label: textOf(el), href: el.getAttribute('href') || '', attributes: attrsOf(el)}));
const wpControlsOf = (row) => Array.from(row.querySelectorAll(controlSelector))
  .filter((el) => visible(el) && enabled(el) && isWpAdminControl(el));
const domainElementCandidates = () => Array.from(document.querySelectorAll('body *'))
  .filter(visible)
  .map((el) => {
    const text = textOf(el);
    const domains = domainsIn(text);
    const box = el.getBoundingClientRect();
    return {el, text, domains, box};
  })
  .filter((item) => item.domains.length === 1 && item.text.length <= 180 && item.box.width <= 900);
const findSmallestWebsiteRow = (domainEl, domain) => {
  const normalized = normalizeDomain(domain);
  const candidates = [];
  let node = domainEl;
  for (let depth = 0; node && depth < 12; depth += 1, node = node.parentElement) {
    if (!visible(node)) continue;
    const text = textOf(node);
    const rowDomains = domainsIn(text);
    if (!rowDomains.includes(normalized)) continue;
    if (!wpControlsOf(node).length) continue;
    const box = node.getBoundingClientRect();
    if (text.length > 2200 || box.height > 320) continue;
    candidates.push({node, text, box, score: text.length + box.height * 8 + box.width * 0.05});
  }
  if (!candidates.length) return null;
  candidates.sort((a, b) => a.score - b.score);
  return candidates[0].node;
};

const rows = [];
const seen = new Set();
for (const item of domainElementCandidates()) {
  const domain = item.domains[0];
  if (seen.has(domain)) continue;
  const row = findSmallestWebsiteRow(item.el, domain);
  if (!row) continue;
  const wpControls = wpControlsOf(row);
  if (!wpControls.length) continue;
  seen.add(domain);
  rows.push({
    domain,
    text: textOf(row).slice(0, 1000),
    controls: controlsOf(row),
    wp_control_count: wpControls.length
  });
}

const bodyText = document.body ? textOf(document.body) : '';
const allControls = Array.from(document.querySelectorAll('a,button,[role="button"]')).filter(visible)
  .map((el) => ({label: textOf(el), href: el.getAttribute('href') || '', attributes: attrsOf(el)}))
  .filter((item) => item.label || item.href);
const wp_controls = allControls
  .map((item) => [item.label, item.href, Object.values(item.attributes || {}).join(' ')].join(' ').slice(0, 260))
  .filter((line) => wpAdminTextPattern.test(line))
  .slice(0, 80);
const loading = /loading|skeleton|progress|spinner|加载中/i.test(bodyText);
const securityChallenge = /正在验证您是否是真人|验证您是否是真人|checking if|just a moment|cloudflare|security service|human verification|verify you are human/i.test(bodyText) ||
  /just a moment|checking/i.test(document.title || '');
const noSites = /no websites|no sites|暂无网站|没有网站/i.test(bodyText);
const allDomains = Array.from(new Set(domainsIn(bodyText + ' ' + Array.from(document.querySelectorAll('a')).map((a) => `${a.href} ${textOf(a)}`).join(' '))));
return {
  rows,
  diagnostics: {
    url: location.href,
    title: document.title,
    domains: allDomains,
    row_count: rows.length,
    controls: allControls.slice(0, 120),
    wp_controls,
    preview: bodyText.slice(0, 1000),
    ready: !securityChallenge && !loading && (rows.length > 0 || noSites || wp_controls.length > 0),
    no_sites: noSites,
    security_challenge: securityChallenge,
    domain_fallback_allowed: false
  }
};
"""


def next_page_script() -> str:
    return r"""
/* WP_AUTOMATION_NEXT_PAGE_V2 */
const visible = (el) => {
  const style = window.getComputedStyle(el);
  const box = el.getBoundingClientRect();
  return style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
};
const disabled = (el) => el.disabled || el.getAttribute('aria-disabled') === 'true' || (el.className || '').toString().toLowerCase().includes('disabled');
const dataOf = (el) => [el.getAttribute('aria-label'), el.getAttribute('title'), el.getAttribute('data-testid'), el.getAttribute('data-test'), el.className, el.innerText].filter(Boolean).join(' ').toLowerCase();
const candidates = Array.from(document.querySelectorAll('button,a,[role="button"]')).filter((el) => visible(el) && !disabled(el));
const next = candidates.find((el) => /next|下一页|下一頁|chevron-right|arrow-right|pagination-next|›|»/.test(dataOf(el)));
if (!next) return false;
next.click();
return true;
"""


def open_wordpress_admin_script() -> str:
    return r"""
/* WP_AUTOMATION_OPEN_ADMIN_V3_DOMAIN_ROW_SAFE */
const targetDomain = String(arguments[0] || '').toLowerCase().replace(/^www\./, '');
const domainRe = /\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b/ig;
const wpAdminTextPattern = /\bwp\s*admin\b|wp-admin|wp_admin|wpadmin|wordpress\s*admin|wordpress\s*administrator|open\s+wordpress|manage\s+wordpress|WordPress\s*管理员|WordPress\s*管理/i;
const controlSelector = 'a,button,[role="button"],[tabindex]';
const blockedDomains = new Set(['node.js', 'hostinger.com', 'www.hostinger.com', 'hpanel.hostinger.com', 'cloudflare.com', 'www.cloudflare.com']);
const blockedSuffixes = ['.hostinger.com', '.cloudflare.com', '.cloudflare.net', '.cloudflarestatus.com', '.google.com', '.facebook.com', '.youtube.com'];

const visible = (el) => {
  if (!el || !el.getBoundingClientRect) return false;
  const style = window.getComputedStyle(el);
  const box = el.getBoundingClientRect();
  return style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
};
const enabled = (el) => !el.disabled && el.getAttribute('aria-disabled') !== 'true';
const textOf = (el) => (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
const dataOf = (el) => [
  textOf(el), el.getAttribute('href'), el.getAttribute('aria-label'), el.getAttribute('title'),
  el.getAttribute('data-testid'), el.getAttribute('data-test'), el.getAttribute('data-qa'), el.getAttribute('class')
].filter(Boolean).join(' ').toLowerCase();
const normalizeDomain = (domain) => String(domain || '').toLowerCase().replace(/^www\./, '');
const isDomainAllowed = (domain) => {
  const normalized = normalizeDomain(domain);
  return Boolean(normalized) &&
    !blockedDomains.has(normalized) &&
    !blockedSuffixes.some((suffix) => normalized.endsWith(suffix));
};
const domainsIn = (text) => Array.from(new Set((String(text || '').match(domainRe) || []).map(normalizeDomain).filter(isDomainAllowed)));
const scoreControl = (el) => {
  const data = dataOf(el);
  let score = 0;
  if (data.includes('wp-admin')) score += 100;
  if (wpAdminTextPattern.test(data)) score += 90;
  if (data.includes('wordpress')) score += 60;
  if (data.includes('admin')) score += 40;
  if (data.includes('管理员') || data.includes('管理')) score += 40;
  if (data.includes('dashboard builder') || data.includes('control panel') || data.includes('billing') || data.includes('invoice') || data.includes('delete')) score -= 120;
  return score;
};
const wpControlsOf = (row) => Array.from(row.querySelectorAll(controlSelector))
  .filter((el) => visible(el) && enabled(el))
  .map((el) => ({el, score: scoreControl(el)}))
  .filter((item) => item.score > 0)
  .sort((a, b) => b.score - a.score);
const domainItems = Array.from(document.querySelectorAll('body *'))
  .filter(visible)
  .map((el) => {
    const text = textOf(el);
    const domains = domainsIn(text);
    const box = el.getBoundingClientRect();
    return {el, text, domains, box};
  })
  .filter((item) => item.domains.includes(targetDomain) && item.domains.length === 1 && item.text.length <= 180 && item.box.width <= 900);
const rowCandidates = [];
for (const item of domainItems) {
  let node = item.el;
  for (let depth = 0; node && depth < 12; depth += 1, node = node.parentElement) {
    if (!visible(node)) continue;
    const text = textOf(node);
    const rowDomains = domainsIn(text);
    if (!rowDomains.includes(targetDomain)) continue;
    const controls = wpControlsOf(node);
    if (!controls.length) continue;
    const box = node.getBoundingClientRect();
    if (text.length > 2200 || box.height > 320) continue;
    rowCandidates.push({node, controls, text, box, score: text.length + box.height * 8 + box.width * 0.05});
  }
}
if (!rowCandidates.length) return {opened: false, reason: 'domain row not found'};
rowCandidates.sort((a, b) => a.score - b.score);
const row = rowCandidates[0];
const chosen = row.controls[0].el;
chosen.scrollIntoView({block: 'center', inline: 'center'});
const link = chosen.matches('a[href]') ? chosen : chosen.closest('a[href]') || chosen.querySelector('a[href]');
const href = link ? (link.href || link.getAttribute('href') || '') : '';
return {
  opened: true,
  reason: 'target row found',
  href,
  label: textOf(chosen).slice(0, 120),
  row_text: row.text.slice(0, 260),
  score: row.controls[0].score,
  element: chosen
};
"""


def _normalize_domain(domain: str) -> str:
    return str(domain or "").strip().lower().removeprefix("www.")


def _is_customer_domain(domain: str) -> bool:
    normalized = _normalize_domain(domain)
    blocked_exact = frozenset(
        {
            "cloudflare.com",
            "www.cloudflare.com",
            "hostinger.com",
            "www.hostinger.com",
            "hpanel.hostinger.com",
        }
    )
    blocked_suffixes = (
        ".hostinger.com",
        ".google.com",
        ".facebook.com",
        ".youtube.com",
        ".cloudflare.com",
        ".cloudflare.net",
        ".cloudflarestatus.com",
    )
    return bool(normalized) and normalized not in blocked_exact and not any(
        normalized.endswith(suffix) for suffix in blocked_suffixes
    )


def _first_control(controls: list[dict]) -> dict | None:
    scored: list[tuple[int, dict]] = []
    for control in controls or []:
        attributes = control.get("attributes") or {}
        haystack = " ".join(
            str(v or "").lower()
            for v in [
                control.get("href"),
                control.get("label"),
                attributes.get("data-testid"),
                attributes.get("aria-label"),
                attributes.get("title"),
                attributes.get("class"),
                attributes.get("id"),
            ]
        )
        score = 0
        if "wp-admin" in haystack:
            score += 100
        if "wp admin" in haystack or "wpadmin" in haystack or "wordpress" in haystack:
            score += 80
        if "admin" in haystack:
            score += 30
        if "dashboard builder" in haystack or "control panel" in haystack:
            score -= 120
        if score > 0:
            scored.append((score, control))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def _safe_control_href_for_domain(control: dict | None, domain: str) -> str:
    if not control:
        return ""
    href = str(control.get("href") or "").strip()
    if not href:
        return ""
    normalized = _normalize_domain(domain)
    href_lower = href.lower()
    href_domains = {_normalize_domain(match.group(0)) for match in DOMAIN_RE.finditer(href_lower)}
    customer_domains = {item for item in href_domains if _is_customer_domain(item)}
    if customer_domains and normalized not in customer_domains:
        return ""
    if normalized in href_lower or normalized.replace(".", "-") in href_lower:
        return urljoin(HOSTINGER_BASE_URL, href)
    if customer_domains and normalized in customer_domains:
        return urljoin(HOSTINGER_BASE_URL, href)
    return ""


def extract_sites_from_discovery(payload: dict) -> list[Site]:
    sites: list[Site] = []
    seen: set[str] = set()
    for row in payload.get("rows") or []:
        domain = _normalize_domain(str(row.get("domain") or "").strip())
        if not _is_customer_domain(domain) or domain in seen:
            continue
        control = _first_control(row.get("controls") or [])
        if control is None:
            continue
        href = _safe_control_href_for_domain(control, domain)
        sites.append(Site(domain=domain, wp_admin_url=href))
        seen.add(domain)
    return sites


class HostingerManager:
    time = time

    def __init__(
        self,
        driver,
        config: RuntimeConfig,
        diagnostic_sink: Callable[[dict], None] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.driver = driver
        self.config = config
        self.diagnostic_sink = diagnostic_sink
        self.sleeper = sleeper

    def ensure_list_ready(self) -> None:
        current_url = str(getattr(self.driver, "current_url", "") or "").lower()
        if "hpanel.hostinger.com" not in current_url:
            raise RuntimeError("当前页面不是 Hostinger hPanel 网站列表页")

    def _switch_to_hostinger_list_tab(self) -> None:
        for handle in list(self.driver.window_handles):
            self.driver.switch_to.window(handle)
            current_url = str(getattr(self.driver, "current_url", "") or "").lower()
            if "hpanel.hostinger.com" in current_url and "/websites" in current_url:
                return
        for handle in list(self.driver.window_handles):
            self.driver.switch_to.window(handle)
            current_url = str(getattr(self.driver, "current_url", "") or "").lower()
            if "hpanel.hostinger.com" in current_url:
                return
        raise RuntimeError("未找到 Hostinger 网站列表标签页，请先回到 Hostinger 网站列表页")

    def scan_all_pages(self) -> list[Site]:
        self.ensure_list_ready()
        collected: list[Site] = []
        seen_domains: set[str] = set()
        seen_signatures: set[str] = set()
        for _ in range(12):
            payload = self._wait_for_page_payload(self.config.first_load_timeout)
            details = payload.get("diagnostics") or {}
            sites = extract_sites_from_discovery(payload)
            if self.diagnostic_sink:
                self.diagnostic_sink(details)
            for site in sites:
                if site.domain not in seen_domains:
                    collected.append(site)
                    seen_domains.add(site.domain)
            signature = ",".join(site.domain for site in sites)
            if signature in seen_signatures:
                break
            seen_signatures.add(signature)
            moved = bool(self.driver.execute_script(next_page_script()))
            if not moved:
                break
            self.sleeper(1.0)
        return collected

    def open_wordpress_admin(self, site: Site) -> str:
        self._switch_to_hostinger_list_tab()
        before = set(self.driver.window_handles)
        target = self.driver.execute_script(open_wordpress_admin_script(), site.domain)
        href = str((target or {}).get("href") or "")
        element = (target or {}).get("element")

        if href:
            self.driver.execute_script("window.open(arguments[0], '_blank');", href)
            new_handles = self._wait_for_new_handle(before, self.config.retry_load_timeout)
        else:
            new_handles = []

        if not new_handles and element is not None:
            try:
                if hasattr(element, "click"):
                    element.click()
                else:
                    self.driver.execute_script("if (arguments[0]) { arguments[0].click(); return true; } return false;", element)
            except Exception:
                self.driver.execute_script("if (arguments[0]) { arguments[0].click(); return true; } return false;", element)
            new_handles = self._wait_for_new_handle(before, self.config.retry_load_timeout)

        if not new_handles and site.wp_admin_url:
            self.driver.execute_script("window.open(arguments[0], '_blank');", site.wp_admin_url)
            new_handles = self._wait_for_new_handle(before, self.config.retry_load_timeout)

        if not new_handles:
            reason = str((target or {}).get("reason") or "no new browser tab")
            raise RuntimeError(f"站点 {site.domain} 未打开 WordPress Tab: {reason}")

        handle = next(iter(new_handles))
        self.driver.switch_to.window(handle)
        return handle

    def _wait_for_page_payload(self, timeout_seconds: int) -> dict:
        deadline = self.time.monotonic() + timeout_seconds
        last_payload: dict = {}
        while self.time.monotonic() < deadline:
            payload = self.driver.execute_script(hostinger_site_discovery_script()) or {}
            last_payload = payload
            diagnostics = payload.get("diagnostics") or {}
            if diagnostics.get("ready") and (payload.get("rows") or diagnostics.get("no_sites")):
                return payload
            if self.diagnostic_sink:
                self.diagnostic_sink(diagnostics)
            self.sleeper(0.5)
        return last_payload

    def _wait_for_new_handle(self, before: set[str], timeout_seconds: int) -> set[str]:
        deadline = self.time.monotonic() + timeout_seconds
        while self.time.monotonic() < deadline:
            new_handles = set(self.driver.window_handles) - before
            if new_handles:
                return new_handles
            self.sleeper(0.5)
        return set()
