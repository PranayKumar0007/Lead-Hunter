# Lead Hunter 🚀

An end-to-end AI-powered outbound pipeline — from finding local businesses on Google Maps to automatically following up until they book a call.

```
Google Maps → Email Discovery → AI Cold Email → Zoho Send
                                                    ↓
                          Auto Follow-Up: Day 3 → 7 → 14 → 21 (Closing)
```

---

## Pipeline Overview

### Part 1 — Prospecting (`main.py`)
| Step | Module | What it does |
|---|---|---|
| 1 | `lead_tracker.py` | Load known domains — skip already-contacted leads |
| 2 | `maps_fetcher.py` | Find fresh businesses via Google Maps API |
| 3 | `email_finder.py` | Discover emails: website scrape → Snov.io → pattern |
| 4 | `company_researcher.py` | Scrape homepage + GPT analysis for personalization |
| 5 | `ai_outreach.py` | Write SMYKM cold email via GPT-4o-mini |
| 6 | `email_sender.py` | Send via Zoho SMTP (dry-run by default) |
| 7 | `lead_tracker.py` | Save results to `output/lead_db.json` |
| 8 | `report.py` | Export `output/leads.csv` + print summary |

### Part 2 — Automated Follow-Up (`followup_runner.py`)
Runs automatically every morning at 9 AM via Windows Task Scheduler.

| Step | Day | Tone |
|---|---|---|
| Initial cold email | Day 0 | SMYKM personalized pitch |
| Follow-up 1 | Day 3 | Gentle bump — "Did this land?" |
| Follow-up 2 | Day 7 | Value-add — industry insight + result |
| Follow-up 3 | Day 14 | Last try — honest, direct |
| Closing | Day 21 | Book a call — calendar link embedded |

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys (see below)
```

---

## API Keys Required

| Key | Where to get it | Used for |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/) — enable *Places API* | Finding businesses by location |
| `SNOV_CLIENT_ID` + `SNOV_CLIENT_SECRET` | [Snov.io → Settings → API](https://app.snov.io/api-setting) | Email discovery (paid, 50 free credits) |
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | Cold email + follow-up generation (GPT-4o-mini) |
| `ZOHO_EMAIL` + `ZOHO_APP_PASSWORD` | [Zoho Mail → Settings → App Passwords](https://accounts.zoho.in/security) | Sending emails via SMTP |
| `APOLLO_API_KEY` | [Apollo.io → Settings → API](https://app.apollo.io/#/settings/integrations/api) | Optional secondary email enrichment |

> **Never commit your `.env` file.** It's already in `.gitignore`.

---

## Usage

### Run the Prospecting Pipeline

```bash
# Dry run (safe — review output/leads.csv before sending)
python main.py

# Prospect fresh leads AND run follow-up pass in one command
python main.py --run-followups
```

> To actually send cold emails, set `ACTUALLY_SEND = True` in `main.py` after reviewing the CSV.

### Run Follow-Ups Manually

```bash
# Dry run — see what would be sent today
python followup_runner.py

# Live send
python followup_runner.py --send
```

### Manage Your Lead Database

```bash
# Show all leads
python tracker_cli.py

# Show leads due for follow-up TODAY
python tracker_cli.py --due

# Filter by status
python tracker_cli.py --status follow_up_1

# Mark outcomes manually
python tracker_cli.py --mark acme.com replied
python tracker_cli.py --mark acme.com booked
python tracker_cli.py --mark acme.com dead

# Lifetime stats
python tracker_cli.py --summary
```

### Lead Statuses

```
pending → sent → follow_up_1 → follow_up_2 → follow_up_3 → closing
                                                               ↓
                                              replied → booked → closed
                                              dead
```

---

## Configuration (`.env`)

```env
# Search
SEARCH_QUERIES=digital marketing agencies
SEARCH_LOCATIONS=Hyderabad,Bangalore,Mumbai,Delhi
SEARCH_RADIUS_METERS=15000
MAX_LEADS=20

# Follow-up timing (produces Day 3 / 7 / 14 / 21 offsets)
FOLLOWUP_1_DELAY_DAYS=3
FOLLOWUP_2_DELAY_DAYS=4
FOLLOWUP_3_DELAY_DAYS=7
CLOSING_DELAY_DAYS=7

# Calendar link embedded in Day 21 closing email
CALENDAR_LINK=https://calendly.com/yourname/15min

# Safety switches (set to True only after dry-run review)
ACTUALLY_SEND=False
FOLLOWUP_SEND=False
```

---

## Windows Task Scheduler

`followup_runner.py` is registered to run automatically at **9:00 AM daily**.  
If the PC was asleep or off at 9 AM, it runs immediately on wake/boot (*StartWhenAvailable* enabled).

To verify the task:
```
Task Scheduler → Task Scheduler Library → "LeadHunter Daily Follow-Up"
```

Logs are written to `output/followup_runner.log`.

---

## Project Structure

```
lead-hunter/
├── main.py                  # Prospecting pipeline orchestrator
├── followup_runner.py       # Daily follow-up scheduler
├── followup_runner.bat      # Task Scheduler entry point
├── follow_up_writer.py      # AI follow-up email generator (4 templates)
├── maps_fetcher.py          # Google Maps lead discovery
├── email_finder.py          # Email discovery waterfall
├── company_researcher.py    # Website scrape + GPT analysis
├── ai_outreach.py           # SMYKM cold email generator
├── email_sender.py          # Zoho SMTP sender
├── lead_tracker.py          # Persistent lead DB (lead_db.json)
├── tracker_cli.py           # CLI to view/manage lead DB
├── service_personalizer.py  # Industry-aware pitch selector
├── snov_service.py          # Snov.io API wrapper
├── snov_tracker.py          # Snov.io credit usage tracker
├── report.py                # CSV export + run summary
└── output/
    ├── lead_db.json         # Persistent lead database
    ├── leads.csv            # Latest run export
    └── followup_runner.log  # Daily follow-up run log
```
