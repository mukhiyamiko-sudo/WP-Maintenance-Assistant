from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from core.browser_manager_patch import apply_safe_close_tab_patch
    from core.maintenance_pipeline_patch import apply_safe_pipeline_close_patch

    apply_safe_close_tab_patch()
    apply_safe_pipeline_close_patch()

    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        from cli.main import main as cli_main

        return cli_main(args)

    from gui.main_window import main as gui_main

    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
