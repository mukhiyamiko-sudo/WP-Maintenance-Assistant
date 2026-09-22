class AutomationError(Exception):
    """Base exception for expected automation failures."""


class LoginRequiredError(AutomationError):
    """Raised when manual Hostinger login is incomplete."""


class BrowserConnectionError(AutomationError):
    """Raised when the Chrome DevTools session is unavailable."""


class SiteNavigationError(AutomationError):
    """Raised when a site cannot expose a WordPress entry."""


class SiteLoadError(AutomationError):
    """Raised when WordPress admin does not become usable."""


class UpdateFlowError(AutomationError):
    """Raised when WordPress updates do not converge."""


class CommentFlowError(AutomationError):
    """Raised when comment cleanup cannot converge."""
