# Incident Tracker 🚨

An automated system that monitors Swedish police events and sends email
notifications to registered users, based on their municipality (kommun).

**Live site:** [incidenttracker.se](https://incidenttracker.se)

## About the project

Incident Tracker lets anyone in Sweden — from central Stockholm to small
towns in Skåne or Umeå — sign up with their kommun and get notified by
email when a relevant police-reported incident happens nearby. No app,
no login. Each subscriber picks how they want it:

- **Live** — an email within minutes of the police publishing something
- **Daily summary** — one email per day at a time they choose (00:00–23:30)

## How it works

1. A user signs up with name, email, kommun and delivery mode (live or
   daily summary + time).
2. A GitHub Action runs `send_email.py` every 5 minutes.
3. The script fetches events from the [Swedish Police API](https://polisen.se/api/events)
   and keeps only relevant event types (burglary, assault, robbery,
   shootings, fires…) from the last 24h.
4. Live users get new events for their kommun right away; summary users
   get everything since their last summary once their chosen time passes.
5. Every email links to a personal page (`manage.html?token=…`) where the
   user can change kommun, delivery mode and time, or unsubscribe.

## Features

- National coverage — all 290 Swedish kommuner, not just Stockholm
- Live alerts or a daily summary at a time of the user's choosing
- Mobile-friendly HTML emails with a link to the police report
- Self-service manage/unsubscribe page via a secret per-user link
  (no login), plus "email me my link" from the website
- Duplicate-safe signups (unique email constraint)
- Filters on the police event *type* rather than free-text keywords, so
  traffic controls, automatic fire alarms and the police's own
  summaries are left out
- Exact kommun matching (whole words), so e.g. "Ale" no longer matches
  "talesperson"
- Single, correctly-parsed timestamp per event (Swedish local time, no
  duplicate/garbled time strings)
- District-aware matching for major cities (Stockholm, Göteborg, Malmö,
  Uppsala, Linköping, Örebro, and other larger kommuner) — catches events
  reported by neighborhood name (e.g. "Skarpnäck") instead of kommun name
- Tracks already-sent events per user so no one gets the same alert twice
- Simple, dependency-light backend — no third-party auth or database
  service required

## Tech Stack

- Python 3.11 (Flask, PostgreSQL)
- Vanilla HTML / CSS / JavaScript (no frontend framework)
- GitHub Actions (scheduling)
- Gmail SMTP

## Project structure

```
Incident-Tracker/
├── backend/
│   ├── app.py              # Flask API — signup, manage, worker endpoints
│   └── requirements.txt
├── frontend/
│   ├── index.html           # landing page
│   ├── manage.html          # change settings / unsubscribe (token link)
│   ├── style.css
│   ├── script.js            # interactions, multi-step signup
│   ├── map.js               # 3D dot map of Sweden in the hero
│   ├── logo.svg
│   └── kommuner.js          # all 290 Swedish kommuner
├── send_email.py            # runs via GitHub Actions every 5 minutes
├── .github/workflows/run.yml
└── README.md
```

## Setup

1. Host `backend/app.py` somewhere persistent (Render, Railway, Fly.io —
   all have free tiers). Running it only locally means GitHub Actions
   can't reach it.
   Environment variables on the backend:
   - `DATABASE_URL` — Postgres connection string
   - `WORKER_TOKEN` — a long random secret (e.g. `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
2. Add these as GitHub Secrets:
   - `API_URL` — your hosted backend URL
   - `WORKER_TOKEN` — the same secret as on the backend
   - `EMAIL_SENDER` — the sending Gmail address
   - `EMAIL_PASSWORD` — a Gmail App Password (Google Account → Security → App passwords)
3. Update `API_URL` in `frontend/script.js` and `frontend/manage.html` to point to the hosted backend.
4. Deploy `frontend/` to any static host (Netlify, Vercel, GitHub Pages).

## What I learned

Migrating this project away from Firebase gave me a better understanding of:

- Designing a minimal REST API with Flask and SQLite
- Handling validation and duplicate-prevention without a managed database
- Separating frontend, backend, and a scheduled worker into clean,
  independently deployable pieces
- Securing secrets properly (removing a hardcoded Gmail app password
  that had been committed to the repo)

## Future improvements

- Web Push notifications (PWA) as an alternative to email
- Rate-limit signups and add basic bot protection
- Expand district-to-kommun mapping to more mid-sized cities (currently
  covers ~20 of the largest kommuner; smaller kommuner are matched
  directly by name since police reports use the kommun name there)

## Status

Live at [incidenttracker.se](https://incidenttracker.se), backend hosted
on Render (Postgres), frontend on Netlify.
