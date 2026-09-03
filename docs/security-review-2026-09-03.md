# Security Review — 3 September 2026

## Scope

This was a safe, non-destructive application assessment. It covered route access control, CSRF handling, open redirects, output escaping, security headers, session configuration, uploads, and dependency consistency. It did not include denial-of-service testing, password guessing against the public EC2 server, or intrusive external scanning.

## Result

No critical vulnerability was found in the reviewed application paths. The live
EC2 header check also confirmed the configured browser protections are being
served. One high-priority deployment gap remains: the current public URL uses
plain HTTP rather than HTTPS. Do not use real staff passwords on that URL;
network traffic and session cookies can be exposed before TLS is enabled.

## Confirmed controls

- Protected pages redirect anonymous visitors to login.
- State-changing POST requests require a per-session CSRF token.
- Post-login `next` values accept only local paths, preventing external open redirects.
- Jinja auto-escaping protects rendered article titles and content from basic reflected/stored XSS payloads.
- Content Security Policy disallows inline scripts and third-party script execution.
- `nosniff`, frame protection, referrer policy, permissions policy, and production HSTS headers are configured.
- Session cookies are HttpOnly, SameSite=Lax, and can be marked Secure in production.
- Login, registration, and reset requests are rate limited.
- Uploads have size limits, filename normalisation, format verification, server-generated filenames, access checks, and forced attachment downloads.
- Direct `python app.py` no longer enables debug mode outside development.

## Required production checklist

1. Use a unique, long `SECRET_KEY` in the EC2 `.env` file.
2. Buy or attach a domain, issue a TLS certificate, redirect HTTP to HTTPS, then set `SESSION_COOKIE_SECURE=true`.
3. Confirm the browser shows a secure HTTPS connection before inviting real users.
4. Keep `.env`, backups, databases, and uploaded files outside Git.
5. Update dependencies periodically and run `pip check` plus the security tests before releases.
6. Restrict EC2 security-group access to ports 80/443 and SSH only from trusted IP addresses.
7. Test backup restore periodically, not just backup creation.

## Automated checks

```powershell
python -m unittest tests.test_security
```

The tests verify anonymous access protection, security headers, missing-CSRF rejection, open-redirect rejection, and template escaping.

## Dependency check

`pip check` completed without broken installed-package relationships. A full
advisory scan could not be completed in this local session because installing
`pip-audit` timed out. Before a public release, run:

```powershell
pip install pip-audit
pip-audit -r requirements.txt
```
