# ChurchOS (CDMS) — Church Digital Management System

> Africa-first multi-tenant SaaS for church governance,
> financial management, and member administration.



![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)




![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)




![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)




![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)




![Railway](https://img.shields.io/badge/Railway-0B0D0E?style=flat&logo=railway&logoColor=white)




![Vercel](https://img.shields.io/badge/Vercel-000000?style=flat&logo=vercel&logoColor=white)



## Why ChurchOS?

Generic software ignores African church structures. ChurchOS is built
for the **Bishop → Overseer → Pastor → Leader → Member** hierarchy
and integrates directly with M-Pesa and Flutterwave — the payment
rails African churches actually use.

## Tech Stack

| Layer    | Technology |
|----------|-----------|
| Backend  | Python 3.11, Flask 3.0, SQLAlchemy, Flask-JWT-Extended |
| Database | PostgreSQL (Railway) / SQLite (dev) |
| Frontend | React 18, React Router 6, Recharts, Axios |
| Auth     | JWT access + refresh tokens, RBAC (5 roles) |
| Deploy   | Railway (backend) + Vercel (frontend) |
| Payments | M-Pesa STK Push, Flutterwave |
| PWA      | Service Worker, Web App Manifest |

## Features

- Multi-church tenancy — 30-day free trial per church
- Member registry with `CHR-XXXXXX` auto-IDs
- Tithes and offerings ledger (KES) with M-Pesa references
- Attendance tracking by service type and date
- RBAC: admin / pastor / secretary / treasurer / viewer
- Real-time dashboard — KPI cards, income vs expenses chart
- Audit log — every financial action timestamped and attributed
- PWA — installable on Android, offline-capable

## Local Development

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask run --port 5000

# Frontend
cd frontend
npm install && npm start
```

## Deployment

- **Backend** → Railway (connect repo, set env vars, deploy)
- **Frontend** → Vercel (import repo, set REACT_APP_API_URL)
- Pay Railway via M-Pesa GlobalPay Visa card

## Environment Variables

| Variable                | Required    | Notes                        |
|-------------------------|-------------|------------------------------|
| SECRET_KEY              | Yes         | Flask session signing        |
| JWT_SECRET_KEY          | Yes         | Must differ from SECRET_KEY  |
| DATABASE_URL            | Yes         | Railway PostgreSQL URL       |
| FRONTEND_URL            | Yes         | Vercel app URL               |
| MPESA_CONSUMER_KEY      | M-Pesa      | Daraja API credentials       |
| MPESA_CONSUMER_SECRET   | M-Pesa      |                              |
| FLW_SECRET_KEY          | Flutterwave |                              |
| FLW_SECRET_HASH         | Flutterwave | Webhook signature hash       |

## Security

- Login rate-limited: 5 requests per minute per IP
- JWT blocklist — logout revokes tokens immediately
- Refresh token rotation — stolen tokens expire after one use
- CORS locked to FRONTEND_URL env var only
- Multi-tenant isolation — every query filtered by church_id
- Webhook signature verification for M-Pesa and Flutterwave

---
*Built by James Koero · Kisumu, Kenya · 2026*
