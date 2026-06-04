# ChurchOS (CDMS) — Church Digital Management System

> Africa-first multi-tenant SaaS for church governance, financial management,
> and member administration.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Railway-4169E1?style=flat&logo=postgresql&logoColor=white)](https://railway.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/jameskoero/ChurchOS/actions/workflows/ci.yml/badge.svg)](https://github.com/jameskoero/ChurchOS/actions)

**Backend:** `https://churchos-production-91e8.up.railway.app` | **Frontend:** `https://churchos.vercel.app`
**Version:** v2.0.0 | **Maintainer:** [James Koero](https://linkedin.com/in/jameskoero) · Kisumu, Kenya

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
- What happens when the internet is unstable? → PWA with offline service worker
- How should multi-tenancy be enforced? → church_id filter at ORM layer

---

## 3. Methodology and Design Decisions

**Why Flask, not Django?** Flask gives more control for a single-developer project
targeting rapid iteration. The application is small enough to reason about every route.

**Why React, not server-rendered templates?** Real-time charts, responsive mobile layout,
and PWA offline behaviour all require a React SPA. Deployed independently on Vercel
so the API and UI can be updated separately.

**Why Railway for the backend?** Render's free PostgreSQL expires after 90 days — a
serious risk for a church depending on years of financial records. Railway persists
indefinitely and accepts M-Pesa GlobalPay Visa for billing.

**Why JWT with refresh token rotation?** Access tokens expire in 8 hours. Refresh
tokens rotate on every use — if a token is used twice, both are immediately revoked,
preventing stolen token replay without forcing frequent re-login.

**Why CHR-XXXXXX for member IDs?** Sequential per-church namespace. The prefix is
fixed so it does not encode the church name — members who transfer keep their
identity without ambiguity.

---

## 4. System Architecture

```
Client (React 18 PWA) ── HTTPS / JWT ──► Flask API (Railway)
                                               │
                             ┌─────────────────┼──────────────┐
                             │                 │              │
                        PostgreSQL       M-Pesa Daraja   Flutterwave
                        (Railway)        STK Push API    Webhooks
```

Seven Blueprint modules: auth · members · attendance · finance · events · users · dashboard.
Every SQLAlchemy query filtered by church_id at the ORM layer.

---

## 5. Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask 3.0, SQLAlchemy, Flask-JWT-Extended |
| Database | PostgreSQL via Neon (prod) / SQLite (dev) |
| Frontend | React 18, React Router 6, Recharts, Axios |
| Auth | JWT access + refresh tokens, RBAC (5 roles) |
| Payments | M-Pesa Daraja STK Push, Flutterwave |
| Deploy | Render (backend) + Neon (DB) + Vercel (frontend) |
| PWA | Service Worker, Web App Manifest |
| CI/CD | GitHub Actions |

---

## 6. Features

- **Multi-church tenancy** — 30-day free trial per church, full data isolation
- **Member registry** — CHR-XXXXXX auto-IDs, full CRUD, search, pagination
- **Attendance tracking** — by service type and date, trend charts
- **Financial ledger** — KES transactions, M-Pesa references, audit log
- **M-Pesa STK Push** — trigger payment request to member's phone
- **Events management** — services, conferences, outreaches
- **Real-time dashboard** — KPI cards, income vs expenses, Recharts
- **RBAC (5 roles)** — admin / pastor / secretary / treasurer / viewer
- **Audit log** — every financial action timestamped and attributed
- **PWA** — installable on Android, offline-capable

---

## 7. Data Models

All models carry `church_id` FK. Every query filtered on this field.

| Model | Key columns |
|---|---|
| Church | id, name, subscription_plan, trial_ends_at |
| User | id, church_id, username, password_hash, role |
| Member | id, church_id, member_id (CHR-XXXXXX), full_name, phone |
| Attendance | id, church_id, member_id, service_type, service_date |
| Finance | id, church_id, type, category, amount_kes, mpesa_ref |
| Event | id, church_id, title, event_type, start_datetime |

---

## 8. API Reference

Base URL: `https://churchos-production-91e8.up.railway.app`
All endpoints require `Authorization: Bearer <access_token>` except `/api/auth/login`.

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/auth/login | Obtain access + refresh tokens |
| POST | /api/auth/refresh | Rotate refresh token |
| POST | /api/auth/logout | Revoke token |
| GET/POST | /api/members | List or create members |
| GET/PUT/DELETE | /api/members/:id | Read, update, delete |
| GET/POST | /api/attendance | List or record attendance |
| GET/POST | /api/finance | Ledger or record transaction |
| POST | /api/finance/mpesa/stk | Trigger M-Pesa STK Push |
| GET/POST | /api/events | List or create events |
| GET | /api/dashboard | Aggregate KPIs + chart data |

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

Default credentials (dev only): `admin` / `Admin@2026`

---

## 10. Deployment

**Backend → Railway**
Connect repo → set env vars → Railway reads `railway.toml` → auto-deploys on push to main.
Accepts M-Pesa GlobalPay Visa for billing.

**Frontend → Vercel**
Import repo → root directory: `frontend` → set `REACT_APP_API_URL` → auto-deploys.

---

## 11. Environment Variables

| Variable | Required | Description |
|---|---|---|
| SECRET_KEY | Yes | Flask session signing |
| JWT_SECRET_KEY | Yes | Must differ from SECRET_KEY |
| DATABASE_URL | Yes | Neon PostgreSQL connection URL |
| FRONTEND_URL | Yes | Vercel URL for CORS |
| MPESA_CONSUMER_KEY | M-Pesa | Daraja API credentials |
| MPESA_CONSUMER_SECRET | M-Pesa | Daraja API credentials |
| FLW_SECRET_KEY | Flutterwave | Dashboard secret key |
| FLW_SECRET_HASH | Flutterwave | Webhook verification hash |

---

## 12. Security

- Login rate-limited: 5 requests/min per IP
- JWT blocklist — logout actually revokes tokens
- Refresh token rotation — stolen tokens expire after one use
- CORS locked to FRONTEND_URL only
- Multi-tenant isolation — church_id on every ORM query
- Webhook HMAC signature verification (M-Pesa + Flutterwave)
- Passwords: Werkzeug PBKDF2-SHA256 with random salt

---

## 13. Roadmap

### v2.0.0 — Current
- [x] Multi-church tenancy, 30-day trial
- [x] Member registry (CHR-XXXXXX)
- [x] Attendance, Finance, Events modules
- [x] JWT RBAC (5 roles), M-Pesa STK Push, Flutterwave
- [x] PWA, Railway + Vercel deployment

### v1.1.0
- [ ] SMS via Africa's Talking API
- [ ] PDF financial reports (monthly, annual)
- [ ] Email password reset

### v2.0.0
- [ ] Branch-level sub-accounts
- [ ] Cross-branch reporting for Overseers and Bishops
- [ ] React Native mobile app

---

## 14. Changelog

### v2.0.0 — 2026-05-27
- Rebranded from CMDMS (Carwash Main Altar) to ChurchOS
- Deployed on Render + Neon + Vercel + Vercel
- Member IDs updated from MRH-XXXXXX to CHR-XXXXXX
- Added Flutterwave alongside M-Pesa
- JWT refresh token rotation, rate limiting, webhook verification
- Fixed CI/CD workflow for Railway + Vercel

---

## 15. Author

James Koero · ML Engineer · Kisumu, Kenya

[LinkedIn](https://linkedin.com/in/jameskoero) ·
[Nyando Flood AI](https://github.com/jameskoero/nyando-flood-ai) ·
[AfriSalaries](https://github.com/jameskoero/afrisalaries) ·
[Loan Risk](https://github.com/jameskoero/loan-risk-assessment)

---

*Built by James Koero · Kisumu, Kenya · 2026 · MIT License*
