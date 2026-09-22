# v1.0.0

First public release of the Hostinger WordPress Maintenance Toolkit.

## Highlights

- Batch discovery of independent WordPress sites in Hostinger hPanel.
- Ordered core, theme, plugin, and translation updates.
- Repeated completion checks before comment cleanup begins.
- Local-only browser profile and Markdown maintenance logs.
- Windows GUI and single-file EXE distribution.

## Included fixes

- Prevent a tab-cleanup exception from turning a completed site into a failure (#1).
- Provide a safe default sleeper when no callback is supplied (#2).
- Submit pending WordPress translation updates (#3).
- Reload the updates page before reading state and starting cleanup (#4).
- Require completion markers and repeated clear checks before leaving the update phase (#5).

## Safety notes

Authentication is manual. No credentials, cookies, sessions, tokens, customer domains, or browser profiles are included. Comment cleanup permanently deletes all comments; back up sites first.
