# Security Policy

## Supported version

Only the latest GitHub Release is supported with security fixes.

## Reporting a vulnerability

Do not publish passwords, cookies, session data, access tokens, SSO links, private website URLs, or customer domains in a public Issue.

Contact the maintainer through the GitHub profile and request a private reporting channel. Include only the minimum reproducible details until a private channel is established.

## Local data

The app uses a dedicated local Chrome profile to preserve the maintainer's authenticated browser session. Treat the profile directory and Markdown run logs as sensitive operational data. They are excluded from Git and must not be attached to Issues.

## Destructive action warning

The comment-cleanup workflow removes all visible comments and permanently empties the trash. It does not classify spam. Always confirm the selected sites and maintain independent backups.
