import requests
import json
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
TO_EMAIL = "yuerzhu02@gmail.com"
KEYWORDS = ["product designer", "ux designer", "interaction designer", "ui designer"]
EXPERIENCE_TITLES = ["product designer", "ux designer", "interaction designer",
                     "designer ii", "designer 2", "mid-level designer", "senior designer"]
EXCLUDE = ["principal", "director", "head of", "vp ", "staff designer", "lead designer"]

# Companies and their Greenhouse / Lever / custom API endpoints
COMPANIES = [
    # Greenhouse-based
    {"name": "Airbnb",      "board": "greenhouse", "id": "airbnb"},
    {"name": "Figma",       "board": "greenhouse", "id": "figma"},
    {"name": "Notion",      "board": "greenhouse", "id": "notionhq"},
    {"name": "Duolingo",    "board": "greenhouse", "id": "duolingo"},
    {"name": "Stripe",      "board": "greenhouse", "id": "stripe"},
    {"name": "Lyft",        "board": "greenhouse", "id": "lyft"},
    {"name": "Dropbox",     "board": "greenhouse", "id": "dropbox"},
    {"name": "Pinterest",   "board": "greenhouse", "id": "pinterest"},
    {"name": "Robinhood",   "board": "greenhouse", "id": "robinhood"},
    {"name": "Waymo",       "board": "greenhouse", "id": "waymo"},
    {"name": "Rivian",      "board": "greenhouse", "id": "rivian"},
    # Lever-based
    {"name": "Netflix",     "board": "lever",      "id": "netflix"},
    {"name": "Spotify",     "board": "lever",      "id": "spotify"},
    {"name": "Snap",        "board": "lever",      "id": "snap"},
    {"name": "Twitch",      "board": "lever",      "id": "twitch"},
    {"name": "Airtable",    "board": "lever",      "id": "airtable"},
    # Custom APIs
    {"name": "Apple",       "board": "apple",      "id": "apple"},
    {"name": "Google",      "board": "google",     "id": "google"},
    {"name": "Meta",        "board": "meta",       "id": "meta"},
    {"name": "Microsoft",   "board": "microsoft",  "id": "microsoft"},
    {"name": "Amazon",      "board": "amazon",     "id": "amazon"},
    {"name": "Samsung",     "board": "greenhouse", "id": "samsungresearch"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0)"}

# ── Scrapers ──────────────────────────────────────────────────────────────────

def fetch_greenhouse(company_id):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs?content=true"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json().get("jobs", [])
    except Exception as e:
        print(f"  Greenhouse error for {company_id}: {e}")
        return []

def fetch_lever(company_id):
    url = f"https://api.lever.co/v0/postings/{company_id}?mode=json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  Lever error for {company_id}: {e}")
        return []

def fetch_apple():
    url = "https://jobs.apple.com/api/role/search"
    params = {"query": "product designer", "filters": {"postingpostLocation": []}, "page": 1}
    try:
        r = requests.post(url, json=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = []
        for j in data.get("searchResults", []):
            jobs.append({
                "title": j.get("postingTitle", ""),
                "location": j.get("postingLocation", ""),
                "url": f"https://jobs.apple.com/en-us/details/{j.get('positionId', '')}",
                "company": "Apple"
            })
        return jobs
    except Exception as e:
        print(f"  Apple error: {e}")
        return []

def fetch_google():
    url = "https://careers.google.com/api/jobs/jobs-v1/search/"
    params = {"q": "UX designer", "location": "", "jlo": "en_US", "page_size": 50}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = []
        for j in data.get("jobs", []):
            jobs.append({
                "title": j.get("title", ""),
                "location": ", ".join(j.get("locations", [])),
                "url": f"https://careers.google.com/jobs/results/{j.get('id', '').split('/')[-1]}",
                "company": "Google"
            })
        return jobs
    except Exception as e:
        print(f"  Google error: {e}")
        return []

def fetch_meta():
    url = "https://www.metacareers.com/jobs"
    # Meta uses GraphQL; fall back to a known stable endpoint
    gql_url = "https://www.metacareers.com/graphql"
    payload = {
        "operationName": "JobSearchResultsQuery",
        "variables": {"search_input": {"q": "product designer", "divisions": [], "offices": [], "roles": [], "leadership_levels": []}},
        "doc_id": "7615760095146396"
    }
    try:
        r = requests.post(gql_url, json=payload, headers={**HEADERS, "Content-Type": "application/json"}, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = []
        results = data.get("data", {}).get("job_search", {}).get("results", [])
        for j in results:
            jobs.append({
                "title": j.get("title", ""),
                "location": j.get("locations", [""])[0] if j.get("locations") else "",
                "url": f"https://www.metacareers.com/jobs/{j.get('id', '')}",
                "company": "Meta"
            })
        return jobs
    except Exception as e:
        print(f"  Meta error: {e}")
        return []

def fetch_microsoft():
    url = "https://gcsservices.careers.microsoft.com/search/api/v1/search"
    params = {"q": "product designer", "l": "en_us", "pg": 1, "pgSz": 50, "o": "Relevance", "flt": True}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = []
        for j in data.get("operationResult", {}).get("result", {}).get("jobs", []):
            jobs.append({
                "title": j.get("title", ""),
                "location": j.get("primaryLocation", ""),
                "url": f"https://careers.microsoft.com/us/en/job/{j.get('jobId', '')}",
                "company": "Microsoft"
            })
        return jobs
    except Exception as e:
        print(f"  Microsoft error: {e}")
        return []

def fetch_amazon():
    url = "https://www.amazon.jobs/en/search.json"
    params = {"query": "product designer UX", "normalized_country_code[]": "USA", "result_limit": 50}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        jobs = []
        for j in data.get("jobs", []):
            jobs.append({
                "title": j.get("title", ""),
                "location": j.get("location", ""),
                "url": f"https://www.amazon.jobs{j.get('job_path', '')}",
                "company": "Amazon"
            })
        return jobs
    except Exception as e:
        print(f"  Amazon error: {e}")
        return []

# ── Normalise & filter ────────────────────────────────────────────────────────

def normalise_greenhouse(raw, company_name):
    out = []
    for j in raw:
        title = j.get("title", "")
        loc_list = j.get("offices", [])
        location = loc_list[0].get("name", "") if loc_list else ""
        url = j.get("absolute_url", "")
        out.append({"title": title, "location": location, "url": url, "company": company_name})
    return out

def normalise_lever(raw, company_name):
    out = []
    for j in raw:
        title = j.get("text", "")
        location = j.get("categories", {}).get("location", "")
        url = j.get("hostedUrl", "")
        out.append({"title": title, "location": location, "url": url, "company": company_name})
    return out

def is_relevant(job):
    title = job["title"].lower()
    # Must contain a keyword
    if not any(k in title for k in KEYWORDS):
        return False
    # Exclude senior/director/etc unless it's Designer II which is fine
    if any(ex in title for ex in EXCLUDE):
        return False
    return True

# ── Email ─────────────────────────────────────────────────────────────────────

def build_email(jobs_by_company):
    total = sum(len(v) for v in jobs_by_company.values())
    date_str = datetime.now().strftime("%B %d, %Y")

    html = f"""
<html><body style="font-family:sans-serif;color:#222;max-width:700px;margin:auto;padding:24px">
<h2 style="color:#1a1a1a">🎨 Weekly Design Job Digest — {date_str}</h2>
<p style="color:#555">{total} relevant roles found across {len(jobs_by_company)} companies.
Filtered for: Product Designer, UX Designer, Interaction Designer (1–5 yrs level).</p>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0">
"""
    for company, jobs in sorted(jobs_by_company.items()):
        if not jobs:
            continue
        html += f'<h3 style="color:#0066cc;margin-bottom:6px">{company} <span style="font-size:13px;color:#888">({len(jobs)} roles)</span></h3><ul style="margin:0 0 20px 0;padding-left:20px">'
        for j in jobs:
            loc = f" — {j['location']}" if j.get("location") else ""
            html += f'<li style="margin-bottom:6px"><a href="{j["url"]}" style="color:#0066cc;text-decoration:none"><b>{j["title"]}</b></a><span style="color:#888;font-size:13px">{loc}</span></li>'
        html += "</ul>"

    html += """
<hr style="border:none;border-top:1px solid #eee;margin:20px 0">
<p style="color:#aaa;font-size:12px">You're receiving this because you set up a weekly job digest.
Roles are scraped from public career pages and filtered by title keyword.</p>
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

        filtered = [j for j in raw_jobs if is_relevant(j)]
        print(f"  → {len(filtered)} relevant roles")
        if filtered:
            jobs_by_company[company["name"]] = filtered

    if jobs_by_company:
        html = build_email(jobs_by_company)
        send_email(html)
    else:
        print("No relevant jobs found this week.")

if __name__ == "__main__":
    main()
