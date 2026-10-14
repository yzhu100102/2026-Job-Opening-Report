# 🎨 Daily Design Job Digest

Scrapes product/UX designer job listings from 76 tech companies every morning and emails a digest of **new** roles to the address(es) in the `TO_EMAIL` repo variable.

## Companies covered (76)
- **Hardware, wearables, spatial & autonomy:** 1X, Applied Intuition, Eight Sleep, Logitech, Lucid Motors, Neuralink, Niantic Spatial, Nuro, Oura, Samsara, Sesame, Skydio, Tesla, Verkada, Waymo, Zipline, Zoox
- **Big tech:** Adobe, Amazon, AMD, Apple, Cisco, Google, Intuit, Meta, Microsoft, Netflix, NVIDIA, Salesforce, Samsung
- **AI:** Anthropic, Cursor, Glean, Harvey, OpenAI, Perplexity, Scale AI, Sierra, Suno
- **Consumer & social:** Airbnb, Discord, DoorDash, Duolingo, eBay, Instacart, Lyft, Nextdoor, Pinterest, Reddit, Roblox, Snap, Spotify, Strava, Uber
- **Fintech:** Brex, Chime, Coinbase, Gusto, PayPal, Plaid, Ramp, Robinhood, Stripe
- **Productivity, dev tools & enterprise:** Airtable, Asana, Atlassian, Autodesk, Canva, Databricks, Dropbox, Faire, Figma, Flexport, Notion, Vercel, Workday

To add or remove one, edit [`companies.json`](companies.json) (see [Customise](#customise)).

## Setup (one-time, ~5 minutes)

### 1. Create a new GitHub repo
- Go to github.com → New repository
- Name it `job-tracker` (or anything you like)
- Upload all files from this folder into it

### 2. Get a Gmail App Password
Gmail requires an App Password (not your regular password) for SMTP.

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Under "How you sign in to Google" → enable **2-Step Verification** if not already on
3. Search for **App Passwords** in the search bar
4. Create one: App = "Mail", Device = "Other" → name it "Job Tracker"
5. Copy the 16-character password it gives you

### 3. Add GitHub Secrets
In your GitHub repo:
1. Go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret** and add these two:

| Secret name | Value |
|---|---|
| `GMAIL_USER` | `yuerzhu02@gmail.com` |
| `GMAIL_APP_PASSWORD` | *(the 16-char app password from step 2)* |

### 4. Enable GitHub Actions
- Go to the **Actions** tab in your repo
- If prompted, click **"I understand my workflows, go ahead and enable them"**

### 5. Test it manually
- Go to **Actions → Daily Design Job Digest → Run workflow**
- Check your inbox in ~2 minutes

## Schedule
Runs automatically every day at **9:00 AM Central** by default (adjusts for daylight saving).

Set the recipient and location filter as repo variables under **Settings → Secrets and variables → Actions → Variables**:
- `TO_EMAIL` — who gets the digest (comma-separate multiple addresses)
- `REGION` — `bay-area` or `west-coast`
- `SEND_TIME` / `SEND_TZ` / `SEND_DAYS` — when to send, e.g. `06:30` / `America/Los_Angeles` / `weekdays` (defaults `09:00` / `America/Chicago` / `daily`). A time other than 9:00 AM Central or 6:30 AM Pacific also needs its UTC slots added to the `cron` list in the workflow.

## How the history check works
Each job is emailed only once. Every run loads `seen_jobs.json` from the repo's `seen-jobs` branch, drops any job whose link is already in it, emails the rest, and then saves the link of every job found in that scan back to the branch. Jobs stay remembered while they're still listed and are forgotten after 60 days without appearing in a scan (usually because they were filled), so a job is never re-reported just because a site failed to load for a day.

- No new jobs → no email that day.
- The very first run (or after deleting the `seen-jobs` branch) reports every current match.
- Manual runs with a custom `to_email` are treated as tests: they include every matching job and don't update the history.

## Customise
**Add/remove companies** in `companies.json`. Each entry names the career-site platform (`source`):

| source | Example career URL | Fields |
|---|---|---|
| `greenhouse` | `job-boards.greenhouse.io/verkada` | `"id": "verkada"` |
| `lever` | `jobs.lever.co/spotify` | `"id": "spotify"` |
| `ashby` | `jobs.ashbyhq.com/notion` | `"id": "notion"` |
| `workday` | `nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite` | `"url": "<that URL>"` |
| `eightfold` | `explore.jobs.netflix.net` | `"url"`, `"domain": "netflix.com"` |
| `jibe` | `careers.amd.com` | `"url"` |
| `talentbrew` | `jobs.intuit.com` | `"url"` |
| `amazon` | `amazon.jobs` | — |
| `apple` | `jobs.apple.com` | — |
| `linkedin` | fallback for sites that block scraping | `"query": "product designer Tesla"` |

Test locally without sending email: `python scraper.py --dry-run`

Edit `scraper.py` to:
- Change keywords (look for `KEYWORDS`)
- Adjust filters (look for `EXCLUDE` to block senior/director roles)
