# Security

English4U is a pet project for one shared teacher workspace. These controls address specific risks; they are not a claim of a complete security audit.

## Implemented controls

- Secrets are required environment variables. Real .env, database files and backups are excluded from Git and Docker build contexts.
- Panel and bot use separate database roles with limited grants. PostgreSQL has no published host port.
- Teacher passwords are hashed; teacher creation supports hidden password entry.
- All panel forms, including deletion and logout, require CSRF validation. Logout uses POST.
- Panel login allows five attempts per client/username in five minutes, plus 30 attempts per client in the same window.
- Bot code entry allows five attempts per Telegram user in five minutes. /start and /reset do not erase this limit.
- A code cannot overwrite an existing Telegram binding from another account.
- Cookies use HttpOnly and SameSite=Lax; Secure cookies and a host allowlist are configurable for HTTPS.
- CI scans reachable history for secrets and checks pinned dependencies and regression tests.

## Current boundaries

- Rate limits use bounded process-local memory. Restarts clear them; multiple replicas need shared storage.
- Teachers share one workspace and can manage all its students and vocabulary.
- Access codes are reusable and stored in the database. Treat them as credentials and exclude them from public examples and screenshots.
- The panel's current convenience generator uses Math.random(). Cryptographically secure code generation remains a follow-up; administrators can enter their own strong codes (up to 20 characters).
- MFA, classroom isolation, automatic backups and a complete container/host assessment are not implemented.
- HTTPS, network access restrictions and the correct number of trusted proxy hops are deployment responsibilities.

## Reporting a problem

Do not put credentials, student records, access codes or an exploit against a live deployment into a public issue. Use private vulnerability reporting if available, or contact the repository owner privately.
