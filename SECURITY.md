# Security Policy

MedMinder stores personal medication records. Even though it is not a
formally HIPAA-covered system, the project's [mission](specs/mission.md)
treats that data with the same care as protected health information.

## Reporting a vulnerability

If you believe you have found a security vulnerability in MedMinder,
**please do not open a public GitHub issue.**

Instead, email the maintainer with:

- A description of the vulnerability.
- The repository version (commit SHA) where you observed it.
- Steps to reproduce, including any proof-of-concept code.
- Your assessment of impact.

Preferred channel: open a private report via the repository's GitHub
Security Advisories
(<https://github.com/jeskritt/med-minder/security/advisories/new>).
This keeps the report private until a fix is coordinated.

Email fallback: <jeskritt@gmail.com>. Use the GitHub channel when
possible — email is unencrypted in transit unless you arrange S/MIME
or PGP out of band.

You should expect:

- An acknowledgement within 7 days.
- A first-pass assessment within 30 days.
- Coordinated disclosure once a fix is available.

## Scope

In scope for vulnerability reports:

- The MedMinder backend (`backend/`) — authentication, session
  handling, input validation, SQL injection, server-side request
  forgery, denial of service, etc.
- The MedMinder frontend (`frontend/`) — XSS, CSRF, insecure storage
  of session state, content security policy bypasses.
- The deployment configuration (`docker-compose.yml`,
  `docs/deployment.md`) — leaked secrets in defaults, insecure
  configuration recommendations.
- The admin CLI (`medminder-admin`) — privilege escalation,
  credential leakage, backup file exposure.

Out of scope:

- Vulnerabilities in third-party services (Vercel, Cloudflare,
  Koyeb, Supabase) — report those directly to the relevant vendor.
- Self-XSS that requires the victim to paste attacker-controlled
  content into devtools.
- Theoretical issues without a concrete exploit path.
- Findings against versions older than the current `main`.

## Security stance

The project's binding rules around security are documented in
[`specs/mission.md`](specs/mission.md) under "Engineering principles."
The most relevant points:

- Treat medication records like PHI.
- Encrypt in transit; minimize what is collected and logged.
- Prefer revocable session-based auth over long-lived tokens.
- Hash credentials with Argon2id; hash session tokens with SHA-256.
- Keep secrets out of the repository.
- Apply least privilege to database roles and deployment credentials.
- When security and convenience conflict, security wins.

New surface area (endpoints, fields, dependencies, third-party calls)
requires explicit threat consideration in the relevant ADR or PR
description, per the [roadmap's exit criteria](specs/roadmap.md).

## Supported versions

The project is in active development. Only the current `main` branch
receives security fixes. There are no LTS or backport branches.
