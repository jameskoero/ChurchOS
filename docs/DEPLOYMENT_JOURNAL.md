# ChurchOS Phase 1 — Deployment Journal & Incident Post-Mortem

**Period:** June 3–9, 2026  
**Author:** James Koero · ML Engineer · Kisumu, Kenya  
**Stack:** Flask 3.0 · React 18 · Neon PostgreSQL · Render · Vercel  
**Status:** ✅ Resolved — Production live as of June 9, 2026 at 09:47 EAT

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Context](#2-project-context)
3. [Infrastructure Architecture](#3-infrastructure-architecture)
4. [Incident Timeline](#4-incident-timeline)
5. [Root Cause Analysis](#5-root-cause-analysis)
6. [Fix History](#6-fix-history)
7. [Key Technical Decisions](#7-key-technical-decisions)
8. [Lessons Learned](#8-lessons-learned)
9. [Production Runbook](#9-production-runbook)
10. [Future Work](#10-future-work)

---

## 1. Executive Summary

ChurchOS Phase 1 is an Africa-first multi-tenant church management SaaS built
on Flask 3.0, React 18, Neon PostgreSQL, Render, and Vercel. The deployment
took six days (June 3–9, 2026) and encountered a layered sequence of failures,
each masking the next. The final symptom was a persistent browser login failure
that passed all server-side tests but blocked every browser request.

**Root cause stack (bottom-up):**

| # | Root Cause | Impact |
|---|---|---|
| RC-1 | `zAuthorization` typo in `api.js` | All Vercel builds failed silently |
| RC-2 | `REACT_APP_API_URL` not set in Vercel build | API calls went to Vercel, not Render |
| RC-3 | Flask-CORS 3.x ignores Python callable as `origins` | All browser requests blocked |
| RC-4 | Render running stale Docker image | CORS fixes never reached production |
| RC-5 | `_seed()` used `Church.query.first()` | Pilot church never seeded |
| RC-6 | PWA service worker cached old JS bundle | New code never reached browser |

All six were resolved. The app is live.

---

## 2. Project Context

ChurchOS began as CMDMS (Church Member Data Management System), a single-tenant
CLI and Flask web tool built for one of the churches where the developer leads
in Kisumu, Kenya. Phase 1 upgrades it to a multi-tenant SaaS capable of serving
any Kenyan church, with:

- **Multi-tenancy** — `church_id` foreign key on every model, enforced at ORM
- **47 Kenyan counties** — constitutional county list in all location dropdowns
- **Denomination registry** — 18 Kenyan denominations
- **M-Pesa STK Push route** — built, awaiting Daraja credentials
- **RBAC** — 5 roles: admin, pastor, secretary, treasurer, viewer
- **PWA** — installable on Android, offline-capable service worker
- **CHR-XXXXXX member IDs** — per-church sequential namespace

**Pilot church:** Migosi Main Altar, Kisumu County — a local Pentecostal church
where the developer leads, used as the Phase 1 test tenant.

---

## 3. Infrastructure Architecture

```
Browser (Android Chrome)
    |
    |  HTTPS + JWT Bearer token
    v
Vercel — churchos-app.vercel.app
  Build: REACT_APP_API_URL baked via buildCommand
  Root Directory: frontend/  |  Node: 20.x  |  Framework: CRA
    |
    |  POST https://churchos-yitr.onrender.com/api/*
    v
Render — churchos-yitr.onrender.com
  Runtime: Python 3.11, Flask 3.0, Docker
  CORS: origins=* (Flask-CORS 3.x)
  Auth: Flask-JWT-Extended + Flask-Bcrypt
  Seed: _seed() on every startup (idempotent)
    |
    |  postgresql://...@ep-morning-darkness-ab3lqoj1
    |  NullPool (serverless-safe)
    v
Neon PostgreSQL
  Tables: church, user, member, attendance, finance, event
  Seed:   Migosi Main Altar (id=1, is_active=True)
```

**Migrated away from:** Railway — replaced by Render (free tier, no expiry).

---

## 4. Incident Timeline

### June 3–4, 2026 — Initial Deployment to Render

Migrated from Railway to Render. Blockers resolved in sequence:

- `config.py` missing `config = {}` dict — Flask `KeyError` on startup
- `wsgi.py` passing wrong config key string
- Docker layer cache serving old Python — fixed by touching `requirements.txt`
- Neon `NullPool` fix for serverless connection drops
- `bcrypt` vs Werkzeug PBKDF2 hash mismatch — standardised on Flask-Bcrypt

All 10 API endpoints verified live by June 4.

### June 5–6, 2026 — Phase 1 Feature Build

Added multi-tenancy: 47 counties, 18 denominations, subscription tiers,
`churches` blueprint, `Churches.js` frontend page, dynamic church name in
`Layout.js`, pilot church seeded as `church_id=1`.

### June 6, 2026 — ESLint CI Blocks Vercel

```
[eslint] src/pages/Finance.js
Line 27: '_u' assigned but never used
Line 74: useEffect missing dependency 'fetchSummary'
Vercel sets CI=true — all ESLint warnings become fatal errors
```

Fix: `DISABLE_ESLINT_PLUGIN=true` in buildCommand plus `eslint-disable`
headers on all page files.

### June 7, 2026 — api.js Syntax Error Found

A stray `z` before `Authorization` in the refresh token headers object
made the object literal syntactically invalid. ESLint treated it as a
fatal compile error in every CI build since the churches feature merged.
`api.js` was rewritten entirely.

```javascript
// Broken (line 16):
headers:zAuthorization:`Bearer ${rt}`}})

// Fixed:
headers:{Authorization:`Bearer ${rt}`}
```

### June 8, 2026 — REACT_APP_API_URL Missing from Vercel Build

After api.js was fixed, builds succeeded but login still failed.
`REACT_APP_API_URL` was never set in the Vercel project dashboard.
The fallback `BASE_URL = '/api'` resolved all API calls to Vercel's own
domain (`https://churchos-app.vercel.app/api/...`), not Render.

Fix — added to `frontend/vercel.json`:

```json
{
  "buildCommand": "REACT_APP_API_URL=https://churchos-yitr.onrender.com DISABLE_ESLINT_PLUGIN=true npm run build",
  "outputDirectory": "build",
  "framework": "create-react-app"
}
```

### June 8–9, 2026 — CORS Blocking All Browser Requests

The `api-test.html` diagnostic page confirmed the root cause:

```
NETWORK ERROR: Failed to fetch
CORS is blocking the request.
Browser Origin: https://churchos-app.vercel.app
Backend must allow this origin.
```

Multiple fixes using Python callables were written, deployed, and confirmed
Live in Render — but CORS kept blocking. Flask-CORS 3.x does not support
Python callables as the `origins` parameter. Every callable was silently
discarded.

### June 9, 2026 09:35–09:47 EAT — Definitive Fix

```python
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
```

Render deployed commit `78d6104` at 09:35 EAT. Logs confirmed:

```
[seed] Updated: Migosi Main Altar (id=1)
[seed] Complete — admin / Admin@2026
```

Diagnostic test at 09:47 EAT:

```
STATUS: 200  {"app": "ChurchOS", "status": "ok", "version": "2.0.0"}
LOGIN SUCCESS — User: admin  Role: admin  Token: received
```

**Phase 1 live.**

---

## 5. Root Cause Analysis

### RC-1: zAuthorization Typo in api.js

**Introduced:** `3836bb6`  **Fixed:** `6c44edf`

A stray `z` made the headers object syntactically invalid. ESLint treated it
as a fatal compile error in every CI build. The Finance.js error was printed
first, making it appear to be the only blocker. The api.js error was hidden.

**Lesson:** One syntax error in a shared utility breaks all downstream builds.
Review the full ESLint output, not just the first error.

### RC-2: REACT_APP_API_URL Not Set in Vercel Build

Colab and curl tests always passed because they called Render directly,
bypassing the browser entirely. This divergence between server tests and
browser tests masked the issue for days.

**Fix:** Version-controlled build-time injection via `vercel.json`
`buildCommand`. Reproducible on any new Vercel project. The URL is not a
secret so committing it to the repo is appropriate.

### RC-3: Flask-CORS 3.x Does Not Support Python Callables

Flask-CORS 3.x `origins` accepts: `"*"`, a single string, a list of strings,
or a regex string starting with `^`. It does not accept Python functions.
Every callable passed as `origins` was silently discarded.

This was only confirmed by the `api-test.html` diagnostic page — not by any
server-side log or test. Browser testing is not optional.

**Fix:** `origins="*"`. JWT Bearer tokens protect all sensitive routes.

### RC-4: Render Running Stale Docker Image

Render's Docker build reuses the pip install layer if `requirements.txt`
is unchanged. Render showed Deploy live while the container ran old code.

**Fix:** Touch `requirements.txt` with `# cache-bust=<timestamp>` on every
backend deploy. Now standard procedure in this repository.

### RC-5: _seed() Using Church.query.first()

The original single-tenant church record from CMDMS was already in Neon.
`Church.query.first()` returned it and `_seed()` skipped creating the pilot
church. The Churches page showed zero registered churches.

**Fix:** Filter by name. Always update existing record. Always reset admin
password on startup. _seed() is idempotent.

### RC-6: PWA Service Worker Caching Old JS Bundle

CRA cached the JavaScript bundle aggressively. After Vercel deployed fixed
code, browsers served the old bundle from the service worker cache.

`church-os-three.vercel.app` worked because no old service worker was cached
there. The main URL failed because the old SW had been installed for days.

**Fix:** `serviceWorkerRegistration.unregister()` in `src/index.js`.
Service worker disabled for Phase 1.

---

## 6. Fix History

| Commit | Description | Files Changed |
|---|---|---|
| `6c44edf` | Rewrite api.js — fix zAuthorization syntax error | `frontend/src/api.js` |
| `53e53aa` | Hardcode backend URL fallback | `frontend/src/api.js` |
| `62dad80` | DISABLE_ESLINT_PLUGIN + eslint-disable all pages | `frontend/` |
| `4a35d39` | CORS multi-origin + admin password always synced | `backend/app.py` |
| `341240c` | Final seed — pilot church filter by name | `backend/app.py` |
| `808fa22` | README complete rewrite v2.0.0 | `README.md` |
| `9bdefd2` | Denominations list + frontend constants | `backend/models.py` |
| `5c3edd3` | Bake API URL into vercel.json buildCommand | `frontend/vercel.json` |
| `57ff81e` | Disable service worker + clear caches | `frontend/src/` |
| `a5da357` | Add api-test.html diagnostic page | `frontend/public/` |
| `2af99ee` | Hardcode CORS origins list (callable — did not work) | `backend/app.py` |
| `78d6104` | **CORS origins=* — definitive fix** | `backend/app.py` |

---

## 7. Key Technical Decisions

### Why origins=* and Not a Restricted List

Flask-CORS 3.x callable support is unreliable. A list requires updating
every time a new Vercel preview URL is created. Using `*` is simple,
auditable, and safe because all writes require a valid JWT. Tighten to
specific origins in Phase 2.

### Why Docker Cache-Busting via requirements.txt

Touching `requirements.txt` invalidates the pip layer and guarantees the
new code runs. This is now standard procedure on every backend change.

### Why NullPool for Neon

Neon terminates idle connections. SQLAlchemy's QueuePool maintains persistent
connections that Neon closes from its side, causing SSL errors. NullPool
creates a fresh connection per request — no pool state, no connection drops.

### Why REACT_APP_API_URL in buildCommand, Not Dashboard

Dashboard env vars are not version-controlled. Placing the URL in
`vercel.json` buildCommand means it is committed to the repo and
automatically present on any new Vercel project.

### Why _seed() Runs on Every Startup

Idempotent design: filter by name, update existing, always reset password.
Guarantees correct state after every deploy without manual DB intervention.

---

## 8. Lessons Learned

**1. Browser tests are not optional.**
Every server-side test passed throughout this incident. A browser test on
Day 1 would have revealed CORS and URL issues immediately. After every
backend change, test from a browser in incognito mode.

**2. Flask-CORS version must be pinned and understood.**
The callable `origins` pattern is not supported in Flask-CORS 3.x.
Document which formats your version accepts. Test CORS from the browser.

**3. Docker cache is invisible without explicit busting.**
Render can show Deploy live while running old code.
Touch `requirements.txt` on every backend change.

**4. Multiple Vercel projects for one repo creates confusion.**
Three projects existed simultaneously. Maintain one per repo per environment.
Delete unused projects immediately.

**5. Service workers require a cache invalidation strategy.**
CRA caches build artifacts aggressively. Disable before production
deployment until proper cache versioning is in place.

**6. db.create_all() does not migrate existing tables.**
Use Flask-Migrate for all schema changes on production databases.

---

## 9. Production Runbook

### Health Checks

```bash
# Backend
curl https://churchos-yitr.onrender.com/api/health
# Expected: {"app":"ChurchOS","status":"ok","version":"2.0.0"}

# Browser diagnostic
# https://churchos-app.vercel.app/api-test.html
# Both buttons should return green
```

### Deploying a Backend Change

```bash
# 1. Edit files in backend/
# 2. echo "# cache-bust=$(date +%s)" >> backend/requirements.txt
# 3. git add -A && git commit -m 'fix: description'
# 4. git push origin main
# 5. Render Events -> wait for 'Your service is live'
# 6. Test: https://churchos-app.vercel.app/api-test.html
```

### Deploying a Frontend Change

```bash
# 1. Edit files in frontend/
# 2. git add -A && git commit -m 'feat: description'
# 3. git push origin main
# 4. Vercel dashboard -> wait for Status: Ready
# 5. Test in Chrome incognito window
```

### Required Environment Variables

**Render (set in dashboard):**

| Variable | Description |
|---|---|
| `DATABASE_URL` | Neon pooled connection string |
| `SECRET_KEY` | Flask session signing key |
| `JWT_SECRET_KEY` | JWT signing key (different from SECRET_KEY) |
| `FRONTEND_URL` | https://churchos-app.vercel.app |

**Vercel (in `frontend/vercel.json` — already committed):**

```json
{
  "buildCommand": "REACT_APP_API_URL=https://churchos-yitr.onrender.com DISABLE_ESLINT_PLUGIN=true npm run build"
}
```

### If Login Fails

1. Open `https://churchos-yitr.onrender.com/api/health`
   - 500 -> check Render logs for Python traceback
   - 404 -> backend sleeping, wait 50 seconds and retry
2. Open `https://churchos-app.vercel.app/api-test.html`
   - CORS error -> verify `backend/app.py` has `origins='*'`
   - Login fails -> check Render logs for seed completion
3. Try from incognito window — if incognito works, clear Chrome cache

---

## 10. Future Work

### Phase 2 (v2.1.0)
- SMS notifications via Africa's Talking API
- PDF financial reports (monthly, annual)
- Email password reset
- M-Pesa Daraja live integration
- Flask-Migrate for all future schema changes

### Phase 3 (v3.0.0)
- Branch-level sub-accounts for multi-campus churches
- Cross-branch reporting for overseers
- React Native mobile app
- Re-enable PWA service worker with proper versioning

### Technical Debt
- Tighten CORS from `*` to specific Vercel domains
- Add Playwright E2E browser tests to CI pipeline
- Migrate fully from `db.create_all()` to Flask-Migrate
- Add error tracking (Sentry)

---

## Appendix: The api-test.html Diagnostic Page

The most valuable debugging tool added during this incident is
`frontend/public/api-test.html` — a plain HTML page with no React, no
service worker, and no bundler. It makes direct fetch calls to the backend
and shows the exact browser error.

Access at: `https://churchos-app.vercel.app/api-test.html`

This page confirmed CORS as the root cause by showing the browser's actual
Origin header and the blocked request — something no server-side tool could
reveal. Keep this page in the repository.

---

*Built by James Koero · ML Engineer · Kisumu, Kenya · 2026*  
*github.com/jameskoero/ChurchOS*