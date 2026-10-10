import requests
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
TO_EMAIL = "yuerzhu02@gmail.com"
KEYWORDS = ["product designer", "ux designer", "interaction designer", "ui designer"]
EXCLUDE = ["principal", "director", "head of", "vp ", "senior", "staff", "lead designer"]

# Loose west coast matching — just check if any of these appear anywhere in location string
WEST_COAST = [
    "san francisco", "sf,", "sf ", "palo alto", "mountain view", "sunnyvale",
    "santa clara", "cupertino", "menlo park", "redwood city", "san jose",
    "los angeles", "irvine", "san diego", "california", ", ca", " ca ",
    "seattle", "bellevue", "redmond", "kirkland", "washington", ", wa", " wa ",
    "portland", "oregon", ", or", " or ",
    "remote", "united states", ", us", " us,", "usa", "west coast"
]

# ⭐ Tight specialization keywords
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

COMPANIES = [
    {"name": "Airbnb",      "board": "greenhouse", "id": "airbnb"},
    {"name": "Figma",       "board": "greenhouse", "id": "figma"},
    {"name": "Notion",      "board": "greenhouse", "id": "notion"},
    {"name": "Duolingo",    "board": "greenhouse", "id": "duolingo"},
    {"name": "Stripe",      "board": "greenhouse", "id": "stripe"},
    {"name": "Lyft",        "board": "greenhouse", "id": "lyft"},
    {"name": "Dropbox",     "board": "greenhouse", "id": "dropbox"},
    {"name": "Pinterest",   "board": "greenhouse", "id": "pinterest"},
    {"name": "Robinhood",   "board": "greenhouse", "id": "robinhood"},
    {"name": "Waymo",       "board": "greenhouse", "id": "waymo"},
    {"name": "Rivian",      "board": "greenhouse", "id": "rivian"},
    {"name": "Coinbase",    "board": "greenhouse", "id": "coinbase"},
    {"name": "Netflix",     "board": "lever",      "id": "netflix"},
    {"name": "Spotify",     "board": "lever",      "id": "spotify"},
    {"name": "Snap",        "board": "lever",      "id": "snap"},
    {"name": "Twitch",      "board": "lever",      "id": "twitch"},
    {"name": "Airtable",    "board": "lever",      "id": "airtable"},
    {"name": "Apple",       "board": "apple",      "id": "apple"},
    {"name": "Google",      "board": "google",     "id": "google"},
    {"name": "Meta",        "board": "meta",       "id": "meta"},
    {"name": "Microsoft",   "board": "microsoft",  "id": "microsoft"},
    {"name": "Amazon",      "board": "amazon",     "id": "amazon"},
    {"name": "Samsung",     "board": "greenhouse", "id": "samsung-research-america"},
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def format_date(date_str):
    if not date_str:
        return "Date unknown"
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%B %d, %Y"):
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

def is_relevant(job):
    title = job["title"].lower()
    location = job.get("location", "").lower()
    if not any(k in title for k in KEYWORDS):
        return False
    if any(ex in title for ex in EXCLUDE):
        return False
    if not any(place in location for place in WEST_COAST):
        return False
    return True

# ── Scrapers ──────────────────────────────────────────────────────────────────

def fetch_greenhouse(company_id):
    # Try with content first, fall back without
    for url in [
        f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs?content=true",
        f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs",
    ]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json().get("jobs", [])
        except Exception:
            pass
    print(f"  Greenhouse failed for {company_id}")
    return []

def fetch_lever(company_id):
    for url in [
        f"https://api.lever.co/v0/postings/{company_id}?mode=json",
        f"https://jobs.lever.co/{company_id}?format=json",
    ]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
    print(f"  Lever failed for {company_id}")
    return []

def fetch_apple():
    try:
        r = requests.get(
            "https://jobs.apple.com/api/role/search",
            params={"query": "designer", "locale": "en-us"},
            headers=HEADERS, timeout=20
        )
        if r.status_code != 200:
            print(f"  Apple error: {r.status_code}")
            return []
        jobs = []
        for j in r.json().get("searchResults", []):
            jobs.append({
                "title": j.get("postingTitle", ""),
                "location": j.get("postingLocation", ""),
                "url": f"https://jobs.apple.com/en-us/details/{j.get('positionId', '')}",
                "company": "Apple",
                "posted_at": j.get("postingDate", ""),
                "description": j.get("jobSummary", "")
            })
        return jobs
    except Exception as e:
        print(f"  Apple error: {e}")
        return []

def fetch_google():
    try:
        r = requests.get(
            "https://careers.google.com/api/jobs/jobs-v1/search/",
            params={"q": "UX designer product designer", "jlo": "en_US", "page_size": 50, "sort_by": "date"},
            headers=HEADERS, timeout=20
        )
        if r.status_code != 200:
            print(f"  Google error: {r.status_code}")
            return []
        jobs = []
        for j in r.json().get("jobs", []):
            jobs.append({
                "title": j.get("title", ""),
                "location": ", ".join(j.get("locations", [])),
                "url": f"https://careers.google.com/jobs/results/{j.get('id','').split('/')[-1]}",
                "company": "Google",
                "posted_at": j.get("publish_date", ""),
                "description": j.get("description", "")
            })
        return jobs
    except Exception as e:
        print(f"  Google error: {e}")
        return []

def fetch_meta():
    try:
        r = requests.get(
            "https://www.metacareers.com/jobs",
            params={"q": "product designer", "is_leadership": 0},
            headers=HEADERS, timeout=20
        )
        # Meta's public search page — parse job cards from JSON embedded in page
        # Fall back to a known working search URL
        r2 = requests.get(
            "https://www.metacareers.com/careers/jobs/?q=product+designer&divisions[0]=Design",
            headers=HEADERS, timeout=20
        )
        print(f"  Meta status: {r.status_code}")
        return []
    except Exception as e:
        print(f"  Meta error: {e}")
        return []

def fetch_microsoft():
    try:
        r = requests.get(
            "https://jobs.careers.microsoft.com/global/en/search",
            params={"q": "product designer", "lc": "United States", "l": "en_us", "pg": 1, "pgSz": 20},
            headers={**HEADERS, "Accept": "application/json, text/plain, */*"},
            timeout=20,
            verify=True
        )
        if r.status_code != 200:
            print(f"  Microsoft error: {r.status_code}")
            return []
        jobs = []
        for j in r.json().get("operationResult", {}).get("result", {}).get("jobs", []):
            jobs.append({
                "title": j.get("title", ""),
                "location": j.get("primaryLocation", ""),
                "url": f"https://jobs.careers.microsoft.com/global/en/job/{j.get('jobId','')}",
                "company": "Microsoft",
                "posted_at": j.get("postingDate", ""),
                "description": j.get("description", "")
            })
        return jobs
    except Exception as e:
        print(f"  Microsoft error: {e}")
        return []

def fetch_amazon():
    try:
        r = requests.get(
            "https://www.amazon.jobs/en/search.json",
            params={"query": "UX designer product designer", "normalized_country_code[]": "USA",
                    "result_limit": 50, "category[]": "design-ux"},
            headers=HEADERS, timeout=20
        )
        if r.status_code != 200:
            print(f"  Amazon error: {r.status_code}")
            return []
        jobs = []
        for j in r.json().get("jobs", []):
            jobs.append({
                "title": j.get("title", ""),
                "location": j.get("location", ""),
                "url": f"https://www.amazon.jobs{j.get('job_path', '')}",
                "company": "Amazon",
                "posted_at": j.get("posted_date", ""),
                "description": j.get("description", "")
            })
        return jobs
    except Exception as e:
        print(f"  Amazon error: {e}")
        return []

# ── Normalise ─────────────────────────────────────────────────────────────────

def normalise_greenhouse(raw, company_name):
    out = []
    for j in raw:
        loc_list = j.get("offices", [])
        location = loc_list[0].get("name", "") if loc_list else j.get("location", {}).get("name", "")
        out.append({
            "title": j.get("title", ""),
            "location": location,
            "url": j.get("absolute_url", ""),
            "company": company_name,
            "posted_at": j.get("updated_at", ""),
            "description": j.get("content", "") or j.get("metadata", "")
        })
    return out

def normalise_lever(raw, company_name):
    out = []
    for j in raw:
        created_ms = j.get("createdAt", 0)
        posted_at = datetime.utcfromtimestamp(created_ms / 1000).strftime("%Y-%m-%dT%H:%M:%SZ") if created_ms else ""
        loc = j.get("categories", {}).get("location", "") or j.get("workplaceType", "")
        out.append({
            "title": j.get("text", ""),
            "location": loc,
            "url": j.get("hostedUrl", ""),
            "company": company_name,
            "posted_at": posted_at,
            "description": j.get("descriptionPlain", "") or ""
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
Scraped from public career APIs every Monday at 9 AM CST.</p>
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
    jobs_by_company = {}

    for company in COMPANIES:
        print(f"Fetching {company['name']}...")
        raw_jobs = []

        if company["board"] == "greenhouse":
            raw = fetch_greenhouse(company["id"])
            raw_jobs = normalise_greenhouse(raw, company["name"])
        elif company["board"] == "lever":
            raw = fetch_lever(company["id"])
            raw_jobs = normalise_lever(raw, company["name"])
        elif company["board"] == "apple":
            raw_jobs = fetch_apple()
        elif company["board"] == "google":
            raw_jobs = fetch_google()
        elif company["board"] == "meta":
            raw_jobs = fetch_meta()
        elif company["board"] == "microsoft":
            raw_jobs = fetch_microsoft()
        elif company["board"] == "amazon":
            raw_jobs = fetch_amazon()

        for j in raw_jobs:
            j["starred"] = is_specialized(j)

        filtered = [j for j in raw_jobs if is_relevant(j)]
        starred_n = sum(1 for j in filtered if j.get("starred"))
        print(f"  → {len(filtered)} relevant roles ({starred_n} starred)")
        if filtered:
            jobs_by_company[company["name"]] = filtered

    if jobs_by_company:
        html = build_email(jobs_by_company)
        send_email(html)
    else:
        print("No relevant jobs found this week.")

if __name__ == "__main__":
    main()
