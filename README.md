# NLV Fireflies Dashboard

A static analytics dashboard that tracks how the team uses [Fireflies.ai](https://fireflies.ai) — meetings organized per person, across all time, last 60 days, and last 30 days. The dashboard is published automatically to GitHub Pages.

**Live dashboard:** https://yurikim-nlv.github.io/nlv-fireflies-dashboard/

---

## How it works

`generate.py` is a single Python script that:

1. Calls the Fireflies GraphQL API to fetch all team members (paying seats only)
2. Paginates through all meeting transcripts (50 at a time)
3. Computes per-user meeting counts broken down by time window
4. Renders a self-contained HTML file (`docs/index.html`) with Chart.js bar charts and a summary table
5. Commits and pushes the updated file to GitHub, which serves it via GitHub Pages

No database, no server, no build step — just one script and one HTML file.

---

## Dashboard metrics

| Column | Description |
|---|---|
| Meetings (Last 30 Days) | Meetings organized by this person in the past 30 days |
| Meetings (Last 60 Days) | Meetings organized by this person in the past 60 days |
| Meetings (All Time) | Total meetings organized since the account was created |

Only users with paying Fireflies seats are included. Meeting counts are based on the `organizer_email` field — i.e. who hosted the meeting, not who attended.

---

## Setup

### Prerequisites

- Python 3.10+
- A Fireflies API key (Admin → API)
- Git configured with push access to this repo

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure environment

Create a `.env` file in the project root:

```
FIREFLIES_API_KEY=your_api_key_here
```

`.env` is gitignored and never committed.

### Run

```bash
python generate.py
```

The script prints progress, writes `docs/index.html`, commits, and pushes. A run typically takes 30–60 seconds depending on the number of transcripts.

---

## Scheduling

The dashboard is refreshed on a schedule via Claude Code's scheduled task runner (`fireflies-dashboard-update`). It runs `python generate.py` automatically and skips the commit if there are no changes.

To trigger a manual refresh, just run `python generate.py` directly.

---

## Project structure

```
.
├── generate.py          # Main script — fetch, compute, render, push
├── requirements.txt     # requests, python-dotenv
├── .env                 # API key (gitignored)
├── .gitignore
└── docs/
    └── index.html       # Generated dashboard (served by GitHub Pages)
```

---

## GitHub Pages setup

The repo serves `docs/index.html` via GitHub Pages (Settings → Pages → Source: `master` branch, `/docs` folder). No additional configuration is needed after the initial setup.
