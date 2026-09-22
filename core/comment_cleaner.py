from __future__ import annotations

import time
from collections.abc import Callable

from core.config import RuntimeConfig
from core.errors import CommentFlowError
from core.wordpress_manager import WordPressManager


class CommentCleaner:
    def __init__(self, driver, config: RuntimeConfig, sleeper: Callable[[float], None] | None = None):
        self.driver = driver
        self.config = config
        self.sleeper = sleeper or time.sleep

    def _count(self, _stage: str) -> int:
        return int(self.driver.execute_script("return document.querySelectorAll('#the-comment-list tr[id^=\"comment-\"], table.comments tr[id^=\"comment-\"]').length;") or 0)

    def _apply(self, action: str) -> None:
        ok = self.driver.execute_script("""
const action = arguments[0];
const rows = Array.from(document.querySelectorAll('#the-comment-list tr[id^="comment-"], table.comments tr[id^="comment-"]'));
rows.forEach(row => { const box = row.querySelector('input[type="checkbox"]'); if (box) box.checked = true; });
const select = document.querySelector('select[name="action"]');
const apply = document.querySelector('#doaction');
if (!select || !apply) return false;
select.value = action; apply.click(); return true;
""", action)
        if not ok:
            raise CommentFlowError(f"Unable to apply comment action: {action}")

    def _open_comments_page(self) -> None:
        WordPressManager(self.driver, self.config, sleeper=self.sleeper).open_admin_page("edit-comments.php")

    def _open_trash(self) -> bool:
        opened = bool(self.driver.execute_script("""
const link = Array.from(document.querySelectorAll('a[href*="comment_status=trash"]')).find(item => !item.closest('[aria-hidden="true"]'));
if (!link) return false; link.click(); return true;
"""))
        if opened:
            WordPressManager(self.driver, self.config, sleeper=self.sleeper)._wait_document_ready(self.config.first_load_timeout)
        return opened

    def _clear_stage(self, stage: str, action: str) -> int:
        deleted = 0
        for _ in range(100):
            count = self._count(stage)
            if not count:
                return deleted
            self._apply(action)
            deleted += count
            self.sleeper(0.2)
        raise CommentFlowError(f"Comment stage {stage} did not converge")

    def clear_all(self) -> int:
        self._open_comments_page()
        deleted = self._clear_stage("visible", "trash")
        if self._open_trash():
            deleted += self._clear_stage("trash", "delete")
        return deleted
