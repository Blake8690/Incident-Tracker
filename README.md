# Incident Tracker 🚨

An automated system that monitors Swedish police events and sends email
notifications to registered users, based on their municipality (kommun).

**Live site:** _add URL once launched_

## About the project

Incident Tracker lets anyone in Sweden — from central Stockholm to small
towns in Skåne or Umeå — sign up with their kommun and get notified by
email when a relevant police-reported incident happens nearby. No app,
no login, no real-time push notifications — just a clean summary when
something is actually worth knowing about.

## How it works

1. A user signs up on the website with their name, email, and kommun.
2. A GitHub Action runs `send_email.py` every 5 minutes.
3. The script fetches new events from the [Swedish Police API](https://polisen.se/api/events).
4. Relevant, recent crimes (last 24h) are matched against each user's
   kommun and sent via email.

## Features

- National coverage — all 290 Swedish kommuner, not just Stockholm
- Duplicate-safe signups (unique email constraint)
- Filters out irrelevant/administrative police reports (training,
  press briefings, controls) and only sends genuine crime-related events
- Single, correctly-parsed timestamp per event (Swedish local time, no
  duplicate/garbled time strings)
- District-aware matching for major cities (Stockholm, Göteborg, Malmö,
  Uppsala, Linköping, Örebro, and other larger kommuner) — catches events
  reported by neighborhood name (e.g. "Skarpnäck") instead of kommun name
- Tracks already-sent events so no one gets the same alert twice
- Simple, dependency-light backend — no third-party auth or database
  service required

## Tech Stack

- Python 3.9 (Flask, SQLite)
- Vanilla HTML / CSS / JavaScript (no frontend framework)
- GitHub Actions (scheduling)
- Gmail SMTP

## Project structure

```
Indicent-Tracker/
├── backend/
│   ├── app.py              # Flask API — registration + SQLite
│   ├── requirements.txt
│   └── incident_tracker.db # created automatically on first run
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   └── kommuner.js          # all 290 Swedish kommuner
├── send_email.py            # runs via GitHub Actions every 5 minutes
├── skickade.json            # tracks already-sent events
├── .github/workflows/run.yml
└── README.md
```

## Setup

1. Host `backend/app.py` somewhere persistent (Render, Railway, Fly.io —
   all have free tiers). Running it only locally means GitHub Actions
   can't reach it.
2. Add these as GitHub Secrets:
   - `API_URL` — your hosted backend URL
   - `EMAIL_SENDER` — the sending Gmail address
   - `EMAIL_PASSWORD` — a Gmail App Password (Google Account → Security → App passwords)
3. Update `API_URL` in `frontend/script.js` to point to the hosted backend.
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

- Move from SQLite to a hosted Postgres instance for reliability across
  deploys
- Add an unsubscribe/settings page for users to update or remove their
  kommun
- Rate-limit signups and add basic bot protection
- Expand district-to-kommun mapping to more mid-sized cities (currently
  covers ~20 of the largest kommuner; smaller kommuner are matched
  directly by name since police reports use the kommun name there)

## Status

In development — backend rebuilt on Flask/SQLite, frontend rebuilt in
vanilla HTML/CSS/JS. Not yet launched publicly.