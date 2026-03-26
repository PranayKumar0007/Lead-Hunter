# Lead Hunter

An automated lead generation pipeline that finds local service businesses, discovers their contact emails, researches their websites, and sends personalized cold emails — all powered by AI.

## How It Works

1. **Find Businesses** — Searches Google Maps for businesses matching your niche and location
2. **Find Emails** — Uses Snov.io to discover the best contact email for each business
3. **Research** — Scrapes each business's website and uses GPT to extract personalization angles
4. **Generate Email** — Writes a personalized cold email using the SMYKM (Show Me You Know Me) framework
5. **Send** — Delivers emails via Zoho SMTP (dry-run by default for safety)
6. **Report** — Saves results to CSV and prints a summary

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env
```

## Usage

```bash
# Run the full pipeline (dry-run mode by default)
python main.py

# Review output/leads.csv, then send pending emails
python send_dry_run.py
```

## API Keys Needed

- Google Maps API
- Snov.io (Client ID + Secret)
- OpenAI
- Zoho Mail (Email + App Password)

See `.env.example` for all required variables.
