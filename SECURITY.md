# Security Policy

## Supported Versions
| Version | Supported |
|---|---|
| 2.x | Yes |
| 1.x and earlier | No |

## Reporting a Vulnerability
Do not open a public GitHub issue for a security problem.

Use GitHub's private reporting: open the **Security** tab of this repository and choose
**Report a vulnerability**. You can also email jmskoero@gmail.com with a description,
steps to reproduce and the likely impact. Expect a first reply within 72 hours.

## What is protected
- Every church's data is kept apart; each request is limited to the signed-in user's church.
- Sessions can be ended: logout, password change, deactivation and role change revoke tokens.
- Sign-in is rate limited and locks after repeated failures.
- Money is never deleted. It is voided, and every change is written to an append-only audit log.
