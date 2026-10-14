# 🎨 Daily Design Job Digest

Scrapes product/UX designer job listings from 30+ tech companies every weekday morning and emails a digest to the address in the `TO_EMAIL` repo variable.

## Companies covered
See [`companies.json`](companies.json) — one line per company.

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
Runs automatically every **weekday at 6:30 AM Pacific** (adjusts for daylight saving).

Each job is only emailed once. Already-reported jobs are tracked in `seen_jobs.json` on the `seen-jobs` branch (updated by the workflow); if there's nothing new, no email is sent. Delete that branch to start fresh. Manual runs with a custom `to_email` are treated as tests — they include every matching job and don't update the history.

Set the recipient and location filter as repo variables under **Settings → Secrets and variables → Actions → Variables**:
- `TO_EMAIL` — who gets the digest
- `REGION` — `bay-area` or `west-coast`

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
