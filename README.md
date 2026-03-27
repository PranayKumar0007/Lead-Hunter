# Lead Hunter

An automated lead generation pipeline that finds local service businesses, discovers their contact emails, researches their websites, and sends personalized cold emails — all powered by AI.

## 🚀 New Features: Persistent Lead Tracking

Lead Hunter now includes a robust **Lead Tracking System** that automatically deduplicates businesses and manages outreach states across multiple runs:

- **Smart Deduplication:** Never email the same company twice. The pipeline checks existing leads before fetching new ones.
- **Status Management:** Leads are naturally tracked as `pending`, `sent`, `follow_up`, or `skipped`.
- **CLI Management Tool:** Easily view your database and manually update lead statuses right from the command line.

## How It Works

1. **Check Tracking DB** — Loads known domains to prevent re-processing past leads.
2. **Find Businesses** — Searches Google Maps for **fresh** businesses matching your niche and location.
3. **Find Emails** — Uses Snov.io to discover the best contact email for each business.
4. **Research** — Scrapes each business's website and uses AI to extract personalization angles.
5. **Generate Email** — Writes a personalized cold email using the SMYKM (Show Me You Know Me) framework.
6. **Send** — Delivers emails via Zoho SMTP (dry-run by default for safety).
7. **Track & Report** — Saves results to the persistent DB, outputs a CSV report, and prints a final all-time track summary.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env
```

## Usage

### Run the Pipeline

```bash
# Run the full pipeline (dry-run mode by default)
python main.py
```
*Note: To actually send emails, switch `ACTUALLY_SEND = True` inside `main.py` after reviewing the output.*

### Manage Leads (Tracker CLI)

You can view and manage your leads database using the included CLI tool:

```bash
# Show all leads and all stats
python tracker_cli.py

# Filter by a specific status (pending, sent, follow_up, skipped)
python tracker_cli.py --status follow_up

# Manually update a lead's status
python tracker_cli.py --update domain.com sent

# Print stats summary only
python tracker_cli.py --summary
```

## API Keys Needed

- Google Maps API
- Snov.io (Client ID + Secret)
- OpenAI
- Zoho Mail (Email + App Password)

See `.env.example` for all required variables.
