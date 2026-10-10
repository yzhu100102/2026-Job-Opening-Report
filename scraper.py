import requests
import smtplib
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
TO_EMAIL = "yuerzhu02@gmail.com"

EXCLUDE = ["principal", "director", "head of", "vp ", "senior", "staff", "lead designer"]

SPECIALIZATION_KEYWORDS = [
    "wearable", "wearables",
    "hardware", "physical product",
    "mapping", "maps platform", "navigation system", "gps",
    "smartwatch", "watch face", "watch app",
    "handheld device", "handheld product",
    "spatial computing", "augmented reality", "mixed reality",
    "embedded system", "sensor design",
    "device design", "form factor",
    "outdoor product", "field device"
]

# Reduced to 10 searches to stay within free tier rate limits
# Each search covers multiple companies via the query
SEARCHES = [
    "product designer at Apple OR Google OR Meta in California OR Seattle OR remote",
    "UX designer at Microsoft OR Amazon OR Adobe in Seattle OR California OR remote",
    "product designer at Airbnb OR Lyft OR Uber in San Francisco OR remote",
    "product designer at Figma OR Notion OR Airtable in San Francisco OR remote",
    "product designer at Snap OR Pinterest OR Robinhood in California OR remote",
    "product designer at Spotify OR Netflix OR Twitch in California OR remote",
    "product designer at Waymo OR Rivian OR Coinbase in California OR remote",
    "UX designer at Stripe OR Dropbox OR Canva in San Francisco OR remote",
    "product designer at Samsung OR Duolingo OR Atlassian in California OR remote",
    "interaction designer OR UX designer hardware wearable mapping in California OR Seattle OR remote",
]

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HEADERS = {
    "X-RapidAPI-Key": os.environ.get("RAPIDAPI_KEY", ""),
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
}

KEYWORDS = ["product designer", "ux designer", "interaction designer", "ui designer"]

# ── Helpers ───────────────────────────────────────────────────────────────────

def format_date(date_str):
    if not date_str:
        return "Date unknown"
    try:
        dt = datetime.fromtimestamp(int(date_str), tz=timezone.utc)
        days_ago = (datetime.now(timezone.utc) - dt).days
        if days_ago == 0:   return "Posted today"
        if days_ago == 1:   return "Posted yesterday"
        if days_ago <= 7:   return f"Posted {days_ago} days ago"
        return f"Posted {dt.strftime('%b %d, %Y')} ({days_ago}d ago)"
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            days_ago = (datetime.now(timezone.utc) - dt).days
            if days_ago == 0:   return "Posted today"
            if days_ago == 1:   return "Posted yesterday"
            if days_ago <= 7:   return f"Posted {days_ago} days ago"
            return f"Posted {dt.strftime('%b %d, %Y')} ({days_ago}d ago)"
        except ValueError:
            continue
    return "Date unknown"

def is_specialized(job):
    text = (job.get("description", "") + " " + job.get("title", "")).lower()
    return any(kw in text for kw in SPECIALIZATION_KEYWORDS)

def is_relevant(title):
    t = title.lower()
    if not any(k in t for k in KEYWORDS):
        return False
    if any(ex in t for ex in EXCLUDE):
        return False
    return True

# ── JSearch fetcher ───────────────────────────────────────────────────────────

def run_search(query):
    try:
        r = requests.get(
            JSEARCH_URL,
            headers=JSEARCH_HEADERS,
            params={
                "query": query,
                "num_pages": "1",
                "date_posted": "month",
                "country": "us",
            },
            timeout=30
        )
        if r.status_code == 429:
            print(f"  Rate limited, waiting 10s...")
            time.sleep(10)
            r = requests.get(JSEARCH_URL, headers=JSEARCH_HEADERS,
                params={"query": query, "num_pages": "1", "date_posted": "month", "country": "us"},
                timeout=30)
        if r.status_code != 200:
            print(f"  Error {r.status_code}: {r.text[:100]}")
            return []
        return r.json().get("data", [])
    except Exception as e:
        print(f"  Exception: {e}")
        return []

def normalise(raw):
    out = []
    for j in raw:
        location_parts = []
        if j.get("job_city"):    location_parts.append(j["job_city"])
        if j.get("job_state"):   location_parts.append(j["job_state"])
        location = ", ".join(location_parts) if location_parts else (
            "Remote" if j.get("job_is_remote") else "")

        out.append({
            "title": j.get("job_title", ""),
            "company": j.get("employer_name", ""),
            "location": location,
            "url": j.get("job_apply_link") or j.get("job_google_link", ""),
            "posted_at": str(j.get("job_posted_at_timestamp", "")),
            "description": j.get("job_description", "")
        })
    return out

# ── Email ─────────────────────────────────────────────────────────────────────

def build_email(jobs_by_company):
    all_jobs = [j for jobs in jobs_by_company.values() for j in jobs]
    total = len(all_jobs)
    starred_count = sum(1 for j in all_jobs if j.get("starred"))
    date_str = datetime.now().strftime("%B %d, %Y")

    html = f"""
<html><body style="font-family:sans-serif;color:#222;max-width:700px;margin:auto;padding:24px">
<h2 style="color:#1a1a1a">🎨 Weekly Design Job Digest — {date_str}</h2>
<p style="color:#555">{total} roles found · <b>⭐ {starred_count} match your specializations</b></p>
<p style="color:#888;font-size:13px">Filtered for: Product/UX/Interaction Designer · West Coast + Remote · Mid-level · ⭐ = wearable / hardware / mapping / GPS / spatial</p>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0">
"""
    for company, jobs in sorted(jobs_by_company.items()):
        if not jobs:
            continue
        jobs_sorted = sorted(jobs, key=lambda j: (not j.get("starred"), j["title"].lower()))
        starred_in_co = sum(1 for j in jobs_sorted if j.get("starred"))
        star_note = f" · ⭐ {starred_in_co}" if starred_in_co else ""
        html += f'<h3 style="color:#0066cc;margin-bottom:6px">{company} <span style="font-size:13px;color:#888">({len(jobs)} roles{star_note})</span></h3>'
        html += '<ul style="margin:0 0 20px 0;padding-left:20px">'
        for j in jobs_sorted:
            star = "⭐ " if j.get("starred") else ""
            loc = f" · {j['location']}" if j.get("location") else ""
            date = f" · <span style='color:#aaa'>{format_date(j.get('posted_at',''))}</span>"
            html += f'<li style="margin-bottom:8px"><a href="{j["url"]}" style="color:#0066cc;text-decoration:none"><b>{star}{j["title"]}</b></a><span style="color:#888;font-size:13px">{loc}{date}</span></li>'
        html += "</ul>"

    html += """
<hr style="border:none;border-top:1px solid #eee;margin:20px 0">
<p style="color:#aaa;font-size:12px">⭐ = wearable, hardware, mapping, GPS, smartwatch, spatial computing, handheld device, outdoor product.<br>
Scraped weekly via JSearch · Runs every Monday at 9 AM CST.</p>
</body></html>"""
    return html

def send_email(html_body):
    from_email = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎨 Weekly Design Jobs — {datetime.now().strftime('%b %d')}"
    msg["From"] = from_email
    msg["To"] = TO_EMAIL
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, app_password)
        server.sendmail(from_email, TO_EMAIL, msg.as_string())
    print(f"✅ Email sent to {TO_EMAIL}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    all_jobs = []
    seen_urls = set()

    for i, query in enumerate(SEARCHES):
        print(f"Search {i+1}/{len(SEARCHES)}: {query[:60]}...")
        raw = run_search(query)
        jobs = normalise(raw)

        for j in jobs:
            if j["url"] in seen_urls:
                continue
            if not is_relevant(j["title"]):
                continue
            seen_urls.add(j["url"])
            j["starred"] = is_specialized(j)
            all_jobs.append(j)

        print(f"  → {len(jobs)} results, {len(all_jobs)} total unique relevant so far")
        time.sleep(3)  # Be polite to the API between requests

    # Group by company
    jobs_by_company = {}
    for j in all_jobs:
        company = j["company"]
        if company not in jobs_by_company:
            jobs_by_company[company] = []
        jobs_by_company[company].append(j)

    print(f"\nTotal: {len(all_jobs)} roles across {len(jobs_by_company)} companies")

    if jobs_by_company:
        html = build_email(jobs_by_company)
        send_email(html)
    else:
        print("No relevant jobs found this week.")

if __name__ == "__main__":
    main()
