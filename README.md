# CMDMS V2 — Carwash Main Altar Digital Management System

**Ministry of Repentance and Holiness · Migosi Region, Kisumu, Kenya**

> Digital management system v2 for Ministry of Repentance & Holiness. React dashboard + Node.js API for membership, tithes, and events.

![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=flat&logo=javascript&logoColor=black)
![Node.js](https://img.shields.io/badge/Node.js-339933?style=flat&logo=node.js&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=flat&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white)

A full-stack enterprise church management system with a **React** dashboard and **Node.js** API, deployed on **Render** with **PostgreSQL**. Manages membership records, tithes & offerings, attendance, and church events for the Ministry of Repentance & Holiness (Carwash Main Altar) in Kisumu, Kenya.

---

## 🏛️ CMDMS — Executive Summary

CMDMS is a multi-tenant SaaS platform designed to digitize church operations in Africa by providing a centralized system for governance, financial management, and member administration.

The platform enables churches to:

- Receive and track donations via **M-Pesa**
- Manage members, leaders, and branches
- Maintain financial transparency through role-based access control
- Access real-time analytics and audit logs

Unlike generic business software, CMDMS is purpose-built for African church structures, incorporating hierarchical governance (**Bishop → Overseer → Pastor → Leader → Member**) and integrating directly with mobile money infrastructure.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask 3.0, SQLAlchemy, Flask-JWT-Extended |
| Database | PostgreSQL (Render) / SQLite (dev) |
| Frontend | React 18, React Router 6, Recharts, Axios |
| Auth | JWT (access + refresh tokens), RBAC (5 roles) |
| Deploy | Render (web + DB), GitHub Actions CI/CD |
| PWA | Service Worker, Web App Manifest |

---

## 📁 Project Structure

```
cmdms-v2/
├── backend/
│   ├── app.py              # Flask factory, blueprints
│   ├── models.py           # SQLAlchemy models
│   ├── config.py           # Dev/prod config
│   ├── wsgi.py             # Gunicorn entry
│   ├── Procfile
│   ├── requirements.txt
│   └── routes/
│       ├── auth.py         # Login, refresh, profile
│       ├── members.py      # Member CRUD
│       ├── attendance.py   # Attendance records
│       ├── finance.py      # Transactions, reports
│       ├── events.py       # Event management
│       ├── users.py        # User management (admin)
│       └── dashboard.py    # Aggregate stats
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   └── manifest.json   # PWA manifest
│   └── src/
│       ├── api.js           # Axios + JWT interceptors
│       ├── App.js           # Router + protected routes
│       ├── index.css        # Design system (navy/gold)
│       ├── contexts/
│       │   └── AuthContext.js
│       ├── components/
│       │   └── Layout.js    # Sidebar + topbar
│       └── pages/
│           ├── Login.js
│           ├── Dashboard.js
│           ├── Members.js
│           ├── Attendance.js
│           ├── Finance.js
│           ├── Events.js
│           ├── Users.js
│           └── Profile.js
├── .github/workflows/deploy.yml
├── render.yaml
└── .gitignore
```

---

## 🔐 RBAC — 5 Roles

| Role | Permissions |
|---|---|
| **admin** | Full access, user management, delete records |
| **pastor** | Read/write + reports |
| **secretary** | Members & attendance read/write |
| **treasurer** | Finance management + reports |
| **viewer** | Read-only |

Default admin: `admin` / `Admin@2026` — **change immediately after first login!**

---

## 🚀 Local Development

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
echo "FLASK_ENV=development" > .env
echo "SECRET_KEY=dev-secret-change-me" >> .env
echo "JWT_SECRET_KEY=dev-jwt-secret" >> .env

flask run --port 5000
```

### Frontend
```bash
cd frontend
npm install
npm start       # Runs on http://localhost:3000
```

---

## 🌐 Render Deployment

### First-time setup
1. Push code to `github.com/Jameskoero/cmdms` (main branch)
2. Go to [render.com](https://render.com) → New → Blueprint → select repo
3. Render reads `render.yaml` and creates web service + PostgreSQL DB
4. Set `RENDER_DEPLOY_HOOK_URL` in GitHub Secrets for auto-deploy

### Build the React frontend before deploy
```bash
cd frontend
npm run build
# Copy build/ to backend/static/ OR configure Flask to serve it
```

### Auto-deploy
Every `git push` to `main` → GitHub Actions → Render Deploy Hook → Live in ~2 minutes.

---

## 📊 Features

- **Dashboard** — KPI cards, attendance trend chart, income vs expenses chart, upcoming events
- **Members** — Full CRUD, `MRH-XXXXXX` IDs, search/filter, pagination, export-ready
- **Attendance** — Mark by service type/date, bulk-ready, trend reporting
- **Finance** — Transaction ledger (KES), M-Pesa refs, category charts, annual summary
- **Events** — Create/manage services, conferences, outreaches
- **Users** — Admin panel for team accounts and role assignments
- **PWA** — Installable on Android/iOS, offline-capable
- **JWT Auth** — 8h access tokens, 30d refresh, auto-renewal

---

## 🗄️ Database Models

- `User` — system accounts with RBAC
- `Member` — congregation records with `MRH-XXXXXX` IDs
- `Attendance` — service check-ins
- `Finance` — transactions with `FIN-YYYYMMDD-XXXX` references
- `Event` — church calendar

---

## ⚠️ Render Free Tier Notes

- **PostgreSQL** expires after **90 days** — upgrade plan or recreate before expiry
- **Web service** spins down after **15 minutes** idle — first request may be slow (~30s)
- Use [UptimeRobot](https://uptimerobot.com) (free) to ping every 14 minutes to prevent spin-down

---

## 🏷️ Keywords

`church-management` `react` `nodejs` `javascript` `flask` `postgresql` `membership` `tithes` `events` `kisumu` `kenya` `pwa` `jwt` `rbac` `mpesa` `africa`

---

*Built by James Koero · Kisumu, Kenya · 2026*
