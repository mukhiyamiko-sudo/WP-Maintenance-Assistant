from __future__ import annotations

from collections.abc import Iterable

from core.models import Site


def resolve_action_sites(sites: Iterable[Site], highlighted_domains: Iterable[str] = ()) -> list[Site]:
    sites = list(sites)
    selected = [site for site in sites if site.selected]
    if selected:
        return selected
    highlighted = set(highlighted_domains)
    if highlighted:
        return [site for site in sites if site.domain in highlighted]
    return sites if len(sites) == 1 else []
