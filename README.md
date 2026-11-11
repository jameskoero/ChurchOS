# ChurchOS (CDMS) — Church Digital Management System

> Africa-first multi-tenant SaaS for church governance, financial management,
> and member administration.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?style=flat&logo=postgresql&logoColor=white)](https://neon.tech)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/jameskoero/ChurchOS/actions/workflows/ci.yml/badge.svg)](https://github.com/jameskoero/ChurchOS/actions)

**Backend:** `https://churchos-yitr.onrender.com` | **Frontend:** `https://churchos-app.vercel.app`
**Version:** v2.5.0 | **Maintainer:** [James Koero](https://linkedin.com/in/jameskoero) · Kisumu, Kenya

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Research Questions](#2-research-questions)
3. [Methodology and Design Decisions](#3-methodology-and-design-decisions)
4. [System Architecture](#4-system-architecture)
5. [Tech Stack](#5-tech-stack)
6. [Features](#6-features)
7. [Data Models](#7-data-models)
8. [API Reference](#8-api-reference)
9. [Local Development](#9-local-development)
10. [Deployment](#10-deployment)
11. [Environment Variables](#11-environment-variables)
12. [Security](#12-security)
13. [Roadmap](#13-roadmap)
14. [Changelog](#14-changelog)
15. [Author](#15-author)

---

## 1. Problem Statement

African churches are among the most active social institutions on the continent,
yet most still run on paper ledgers, WhatsApp groups, and verbal attendance rolls.
A mid-sized church in Kisumu with 300 members and weekly tithes above KES 50,000
has no reliable way to reconcile M-Pesa STK push confirmations against its offering
records, track attendance over time, or produce a clean monthly financial report.

Generic SaaS tools like Planning Center or Breeze are designed for American church
structures. They assume credit cards, flat membership hierarchies, and US dollar
pricing. They have no awareness of the Bishop → Overseer → Pastor → Leader → Member
governance chain that defines most Pentecostal and evangelical denominations in
East and Central Africa. They have no M-Pesa integration.

ChurchOS is a direct answer to that gap.

---

## 2. Research Questions

- What does a church actually need to manage? → Members, Attendance, Finance, Events
- What hierarchy does African Pentecostal governance follow? → 5-tier RBAC
- How should money move through the system? → M-Pesa as first-class citizen
- What happens when the internet is unstable? → Installable PWA; offline attendance is on the roadmap
- How should multi-tenancy be enforced? → church_id filter at ORM layer

---

## 3. Methodology and Design Decisions

**Why Flask, not Django?** Flask gives more control for a single-developer project
targeting rapid iteration. The application is small enough to reason about every route.

**Why React, not server-rendered templates?** Real-time charts, responsive mobile layout,
and PWA offline behaviour all require a React SPA. Deployed independently on Vercel
so the API and UI can be updated separately.

**Why Render + Neon?** Neon PostgreSQL is free and durable with no expiry — critical
for a church depending on years of financial records. Render deploys Docker containers
reliably and auto-deploys on every push. Billing via M-Pesa GlobalPay Visa.

**Why JWT with refresh token rotation?** Access tokens expire in 8 hours. Refresh
tokens rotate on every use — if a token is used twice, both are immediately revoked,
preventing stolen token replay without forcing frequent re-login.

**Why CHR-XXXXXX for member IDs?** Sequential per-church namespace. The prefix is
fixed so it does not encode the church name — members who transfer keep their
identity without ambiguity.

---

## 4. System Architecture

```
Client (React 18 PWA) ── HTTPS / JWT ──► Flask API (Render)
                                               │
                             .─────────────────+────────────.
                             │                 │              │
                        PostgreSQL       M-Pesa Daraja   Flutterwave
                        (Neon)           STK Push API    Webhooks
```

Eight Blueprint modules: auth · members · attendance · finance · events · users · dashboard · churches.
Every SQLAlchemy query filtered by church_id at the ORM layer.

---

## 5. Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask 3.0, SQLAlchemy, Flask-JWT-Extended, Flask-Bcrypt |
| Database | PostgreSQL via Neon (prod) / SQLite (dev) |
| Frontend | React 18, React Router 6, Recharts, Axios |
| Auth | JWT access + refresh tokens, RBAC (5 roles) |
| Payments | M-Pesa Daraja STK Push, Flutterwave (routes built; credentials needed) |
| Deploy | Render (backend Docker) + Neon (DB) + Vercel (frontend) |
| PWA | Web App Manifest (ChurchOS, installable on Android) |
| CI/CD | GitHub Actions |

---

## 6. Features

- **Multi-church tenancy** — 30-day free trial per church, full data isolation via church_id
- **Member registry** — CHR-XXXXXX auto-IDs, full CRUD, search by name/ID/phone, pagination
- **Attendance tracking** — by service type and date, Sunday trend charts
- **Financial ledger** — KES transactions, M-Pesa references, income vs expenses charts
- **M-Pesa STK Push** — trigger payment request to member's phone (Daraja credentials required)
- **Events management** — services, conferences, outreaches with upcoming filter
- **Real-time dashboard** — KPI cards, income vs expenses (6 mo.), gender split, upcoming events
- **RBAC (5 roles)** — admin / pastor / secretary / treasurer / viewer
- **Churches management** — register churches with county, sub-county, denomination, size, paybill
- **47 Kenyan counties** — all constitutional counties in dropdowns (Members + Churches forms)
- **Denomination registry** — 17 denominations including Ministry of Repentance and Holiness
- **PWA** — installable on Android (offline attendance is on the roadmap)
- **Audit trail** — every create, edit, verify and void is recorded in an append-only log; money is voided, never deleted; a second person verifies

---

## 7. Data Models

All models carry `church_id` FK. Every query filtered on this field.

| Model | Key columns |
|---|---|
| Church | id, name, county, sub_county, denomination, size, member_prefix, subscription_plan, trial_ends_at, is_active |
| User | id, church_id, username, email, password_hash, role, is_active |
| Member | id, church_id, member_id (CHR-XXXXXX), full_name, phone, gender |
| Attendance | id, church_id, member_id, service_type, service_date |
| Finance | id, church_id, type, category, amount_kes, mpesa_ref, description |
| Event | id, church_id, title, event_type, start_datetime |

---

## 8. API Reference

Base URL: `https://churchos-yitr.onrender.com`
All endpoints require `Authorization: Bearer <access_token>` except `/api/auth/login`
and `/api/churches/constants`.

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/auth/login | Obtain access + refresh tokens |
| POST | /api/auth/refresh | Rotate refresh token |
| POST | /api/auth/logout | Revoke token |
| GET | /api/auth/me | Current user profile |
| GET/POST | /api/members/ | List or create members |
| GET/PUT/DELETE | /api/members/:id | Read, update, delete |
| GET | /api/members/stats/summary | Member statistics |
| GET/POST | /api/attendance/ | List or record attendance |
| GET | /api/attendance/service-types | Available service types |
| GET/POST | /api/finance/ | Ledger or record transaction |
| GET | /api/finance/summary | Income vs expense summary |
| POST | /api/finance/mpesa/stk | Trigger M-Pesa STK Push |
| GET/POST | /api/events/ | List or create events |
| GET | /api/events/upcoming | Upcoming events |
| GET/POST | /api/users/ | List or create users |
| PUT/DELETE | /api/users/:id | Update or delete user |
| GET | /api/dashboard/stats | Aggregate KPIs + chart data |
| GET | /api/churches/constants | Counties, denominations, sizes (public) |
| GET/POST | /api/churches/ | List or register churches (admin) |
| GET/PUT/DELETE | /api/churches/:id | Read, update, delete church (admin) |
| GET | /api/health | Health check |
| POST | /api/finance/:id/verify | Second person verifies a transaction (admin, treasurer) |
| GET | /api/finance/audit | Append-only change log (admin) |
| GET | /api/members/:id/export | One member's data, for a data-access request |
| POST | /api/members/:id/erase | Erase a member's personal details (admin) |
| POST | /api/payments/mpesa/stk | Send an M-Pesa payment prompt (admin, treasurer) |
| GET | /api/payments/requests, /api/payments/requests/:id | Payment prompts and their status |
| GET | /api/payments/inbox | Paybill payments waiting for a member |
| POST | /api/payments/inbox/:id/match, /api/payments/inbox/:id/ignore | Match or ignore a Paybill payment |
| POST | /api/payments/mpesa/callback/:secret | Safaricom prompt result (called by Safaricom) |
| POST | /api/payments/mpesa/c2b/:secret/confirmation | Safaricom Paybill payment (called by Safaricom) |
| GET | /api/insights/care, /giving, /forecast, /summary | Explainable insights from your own records |

---

## 9. Local Development

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask run --port 5000

# Frontend
cd frontend
npm install
echo "REACT_APP_API_URL=http://localhost:5000" > .env.local
npm start
```

First admin: set `ADMIN_BOOTSTRAP_PASSWORD` (12+ characters) before the first start. The admin is created once; the app never resets a password.

---

## 10. Deployment

**Database → Neon**
Create a project at neon.tech. Copy the pooled connection string as `DATABASE_URL`.

**Backend → Render**
New → Blueprint → select `jameskoero/ChurchOS` → Render reads `render.yaml` →
fill env vars → auto-deploys on every push to main.

**Frontend → Vercel**
Import repo → Root Directory: `frontend` → set `REACT_APP_API_URL` → auto-deploys.

---

## 11. Environment Variables

| Variable | Required | Description |
|---|---|---|
| SECRET_KEY | Yes | Flask session signing |
| JWT_SECRET_KEY | Yes | Must differ from SECRET_KEY |
| DATABASE_URL | Yes | Neon PostgreSQL pooled connection URL |
| FRONTEND_URL | Yes | Vercel URL for CORS (comma-separated for multiple) |
| MPESA_CONSUMER_KEY | M-Pesa | Daraja API consumer key |
| MPESA_CONSUMER_SECRET | M-Pesa | Daraja API consumer secret |
| FLW_SECRET_KEY | Flutterwave | Dashboard secret key |
| FLW_SECRET_HASH | Flutterwave | Webhook verification hash |

---

## 12. Security

- Login rate-limited (10 requests/min per address) and locked for 15 minutes after 5 failed attempts
- JWT blocklist — logout actually revokes tokens
- Refresh token rotation — stolen tokens expire after one use
- CORS supports comma-separated FRONTEND_URL (multi-origin)
- Multi-tenant isolation: every route reads and writes through church-scoped helpers (backend/tenancy.py), covered by two-church tests
- M-Pesa callbacks are unsigned by Safaricom, so they are protected by a secret in the callback address, an optional IP allowlist, and matching against requests this app made itself
- Passwords: Flask-Bcrypt (cost factor 12)
- First admin created once from ADMIN_BOOTSTRAP_PASSWORD; startup never resets a password

---

## 13. Roadmap

### v2.5.0 — Current
- [x] Church separation on every route, platform-owner role
- [x] Revocable sessions, rotating refresh tokens, login limits and lockout
- [x] Money integrity: second-person verify, void instead of delete, append-only audit log
- [x] Member privacy: consent, sensitive-field redaction, export and erase
- [x] M-Pesa prompts, Paybill callbacks and matching inbox (sandbox-ready)
- [x] Explainable insights: care list, giving flags, forecast, plain-language summary
- [x] Cobalt portfolio-style interface
- [ ] Offline attendance with sync
- [ ] SMS via Africa's Talking
- [ ] Billing for churches (M-Pesa subscriptions) and plan limits

### v2.0.0
- [x] Multi-church tenancy, 30-day trial
- [x] Member registry (CHR-XXXXXX)
- [x] Attendance, Finance, Events modules
- [x] JWT RBAC (5 roles), M-Pesa STK Push route, Flutterwave route
- [x] PWA, Render + Neon + Vercel deployment
- [x] NullPool for Neon serverless stability
- [x] 47 Kenyan counties + 17 denominations (Members & Churches forms)
- [x] Churches page — county, sub-county, denomination, size, paybill fields
- [x] Migosi Main Altar seeded (Kisumu, Ministry of Repentance and Holiness)
- [x] Multi-origin CORS support
- [x] Admin created once from an environment variable (v2.1.0)

### v2.1.0
- [ ] SMS via Africa's Talking API
- [ ] PDF financial reports (monthly, annual)
- [ ] Email password reset
- [ ] M-Pesa Daraja live integration (activate with credentials)

### v3.0.0
- [ ] Branch-level sub-accounts
- [ ] Cross-branch reporting for Overseers and Bishops
- [ ] React Native mobile app

---

## 14. Changelog

### v2.5.0 — 2026-11-11
- Church separation, platform owner, revocable sessions, login limits
- Money integrity: second-person verify, void not delete, audit log
- Member consent, redaction, export and erase
- M-Pesa prompts and Paybill inbox
- Explainable insights and the new cobalt interface
- Dependency security updates (Flask, Werkzeug, Jinja2, Flask-CORS, python-dotenv, marshmallow)

### v2.0.0 — 2026-06-08
- Rebranded from CMDMS to ChurchOS
- Deployed on Render + Neon + Vercel
- Member IDs updated from MRH-XXXXXX to CHR-XXXXXX
- Added Flutterwave alongside M-Pesa
- JWT refresh token rotation, rate limiting, webhook verification
- Fixed config dict missing from config.py (root cause of 500 errors)
- Added NullPool for Neon serverless connection stability
- Fixed wsgi.py config_name resolution
- Fixed api.js syntax error (zAuthorization typo) that blocked all Vercel builds
- Added 47 Kenyan counties + 17 denominations (backend constants + frontend)
- Added /api/churches full CRUD blueprint with public /constants endpoint
- Churches page: county, sub-county, denomination, size, M-Pesa paybill/till fields
- Added Ministry of Repentance and Holiness to denominations list
- Seeded Migosi Main Altar (Kisumu, Ministry of Repentance and Holiness)
- ESLint CI errors fixed (Finance.js unused vars + all pages eslint-disable)
- DISABLE_ESLINT_PLUGIN added to frontend/.env.production
- CORS updated to support comma-separated multi-origin FRONTEND_URL
- Admin password always synced on startup via _seed()
- PWA manifest restored: manifest link, logo192/512 icons, white splash background
- Backend URL hardcoded as fallback in api.js (no env var dependency)

---

## 15. Author

James Koero · ML Engineer · Kisumu, Kenya

[LinkedIn](https://linkedin.com/in/jameskoero) ·
[Nyando Flood AI](https://github.com/jameskoero/nyando-flood-ai) ·
[AfriSalaries](https://github.com/jameskoero/afrisalaries) ·
[Loan Risk](https://github.com/jameskoero/loan-risk-assessment)

---

*Built by James Koero · Kisumu, Kenya · 2026 · MIT License*
