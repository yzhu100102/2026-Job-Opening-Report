import requests
import smtplib
import os
import time
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

TO_EMAIL = "yuerzhu02@gmail.com"
EXCLUDE = ["principal", "director", "head of", "vp ", "senior", "staff", "lead designer"]
KEYWORDS = ["product designer", "ux designer", "interaction designer", "ui designer"]

SPECIALIZATION_KEYWORDS = [
    "wearable", "wearables", "hardware", "physical product",
    "mapping", "maps platform", "navigation system", "gps",
    "smartwatch", "watch face", "watch app",
    "handheld device", "handheld product",
    "spatial computing", "augmented reality", "mixed reality",
    "embedded system", "sensor design", "device design",
    "form factor", "outdoor product", "field device"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

# ── Greenhouse companies ──────────────────────────────────────────────────────
GREENHOUSE_COMPANIES = [
    ("Airbnb",      "airbnb"),
    ("Figma",       "figma"),
    ("Notion",      "notion"),
    ("Duolingo",    "duolingo"),
    ("Stripe",      "stripe"),
    ("Lyft",        "lyft"),
    ("Dropbox",     "dropbox"),
    ("Pinterest",   "pinterest"),
    ("Robinhood",   "robinhood"),
    ("Waymo",       "waymo"),
    ("Rivian",      "rivian"),
    ("Coinbase",    "coinbase"),
]

# ── Lever companies ───────────────────────────────────────────────────────────
LEVER_COMPANIES = [
    ("Netflix",     "netflix"),
    ("Spotify",     "spotify"),
    ("Snap",        "snap"),
    ("Twitch",      "twitch"),
    ("Airtable",    "airtable"),
]

# ── LinkedIn RSS searches (covers Apple, Google, Meta, Microsoft, Amazon etc) ─
LINKEDIN_SEARCHES = [
    ("Apple",       "product designer Apple",       "San Francisco"),
    ("Apple",       "UX designer Apple",            "Seattle"),
    ("Google",      "product designer Google",      "San Francisco"),
    ("Google",      "UX designer Google",           "Seattle"),
    ("Meta",        "product designer Meta",        "San Francisco"),
    ("Microsoft",   "UX designer Microsoft",        "Seattle"),
    ("Amazon",      "product designer Amazon",      "Seattle"),
    ("Adobe",       "product designer Adobe",       "San Francisco"),
    ("Uber",        "product designer Uber",        "San Francisco"),
    ("Canva",       "product designer Canva",       "remote"),
    ("Samsung",     "UX designer Samsung",          "San Francisco"),
    ("Atlassian",   "product designer Atlassian",   "San Francisco"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def format_date(date_str):
    if not date_str:
        return "Date unknown"
    try:
        dt = datetime.fromtimestamp(int(date_str), tz=timezone.utc)
        days_ago = (datetime.now(timezone.utc) - dt).days
        if days_ago == 0: return "Posted today"
        if days_ago == 1: return "Posted yesterday"
        if days_ago <= 7: return f"Posted {days_ago} days ago"
        return f"Posted {dt.strftime('%b %d, %Y')} ({days_ago}d ago)"
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d",
                "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            days_ago = (datetime.now(timezone.utc) - dt).days
            if days_ago == 0: return "Posted today"
            if days_ago == 1: return "Posted yesterday"
            if days_ago <= 7: return f"Posted {days_ago} days ago"
            return f"Posted {dt.strftime('%b %d, %Y')} ({days_ago}d ago)"
        except ValueError:
            continue
    return "Date unknown"

def is_specialized(job):
    text = (job.get("description", "") + " " + job.get("title", "")).lower()
    return any(kw in text for kw in SPECIALIZATION_KEYWORDS)

def is_relevant(title):
    t = title.lower()
    if not any(k in t for k in KEYWORDS): return False
    if any(ex in t for ex in EXCLUDE): return False
    return True

# ── Scrapers ──────────────────────────────────────────────────────────────────

def fetch_greenhouse(company_name, company_id):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_id}/jobs?content=true"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  Greenhouse error for {company_name}: {r.status_code}")
            return []
        jobs = []
        for j in r.json().get("jobs", []):
            loc_list = j.get("offices", [])
            location = loc_list[0].get("name", "") if loc_list else j.get("location", {}).get("name", "")
            jobs.append({
                "title": j.get("title", ""),
                "company": company_name,
                "location": location,
                "url": j.get("absolute_url", ""),
                "posted_at": j.get("updated_at", ""),
                "description": j.get("content", "")
            })
        return jobs
    except Exception as e:
        print(f"  Greenhouse exception for {company_name}: {e}")
        return []

def fetch_lever(company_name, company_id):
    url = f"https://api.lever.co/v0/postings/{company_id}?mode=json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  Lever error for {company_name}: {r.status_code}")
            return []
        jobs = []
        for j in r.json():
            created_ms = j.get("createdAt", 0)
            posted_at = datetime.utcfromtimestamp(created_ms / 1000).strftime("%Y-%m-%dT%H:%M:%SZ") if created_ms else ""
            loc = j.get("categories", {}).get("location", "") or j.get("workplaceType", "")
            jobs.append({
                "title": j.get("text", ""),
                "company": company_name,
                "location": loc,
                "url": j.get("hostedUrl", ""),
                "posted_at": posted_at,
                "description": j.get("descriptionPlain", "") or ""
            })
        return jobs
    except Exception as e:
        print(f"  Lever exception for {company_name}: {e}")
        return []

def fetch_linkedin_rss(company_name, keywords, location):
    """Fetch jobs via LinkedIn's public RSS feed."""
    url = "https://www.linkedin.com/jobs/search/"
    params = {
        "keywords": keywords,
        "location": location,
        "f_TPR": "r2592000",  # last 30 days
        "f_JT": "F",          # full time
        "format": "rss"
    }
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        if r.status_code != 200:
            print(f"  LinkedIn RSS error for {company_name}: {r.status_code}")
            return []
        root = ET.fromstring(r.content)
        jobs = []
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        for item in root.findall(".//item"):
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            description = item.findtext("description", "")
            # LinkedIn RSS includes company in title like "Product Designer at Apple"
            jobs.append({
                "title": title,
                "company": company_name,
                "location": location,
                "url": link,
                "posted_at": pub_date,
                "description": description
            })
        return jobs
    except Exception as e:
        print(f"  LinkedIn RSS exception for {company_name}: {e}")
        return []

# ── Filter ────────────────────────────────────────────────────────────────────

WEST_COAST = [
    "san francisco", "palo alto", "mountain view", "sunnyvale", "santa clara",
    "cupertino", "menlo park", "redwood city", "san jose", "los angeles",
    "irvine", "san diego", "california", ", ca", " ca ",
    "seattle", "bellevue", "redmond", "kirkland", "washington", ", wa",
    "portland", "oregon", "remote", "united states", "usa", ", us"
]

def is_west_coast(location):
    loc = location.lower()
    return any(place in loc for place in WEST_COAST)

# ── Email ─────────────────────────────────────────────────────────────────────

def build_email(jobs_by_company):
    all_jobs = [j for jobs in jobs_by_company.values() for j in jobs]
    total = len(all_jobs)
    starred_count = sum(1 for j in all_jobs if j.get("starred"))
    date_str = datetime.now().strftime("%B %d, %Y")
    html = f"""<html><body style="font-family:sans-serif;color:#222;max-width:700px;margin:auto;padding:24px">
<h2>🎨 Weekly Design Job Digest — {date_str}</h2>
<p>{total} roles found · <b>⭐ {starred_count} match your specializations</b></p>
<p style="color:#888;font-size:13px">Product/UX/Interaction Designer · West Coast + Remote · Mid-level · ⭐ = wearable / hardware / mapping / GPS / spatial</p>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0">"""
    for company, jobs in sorted(jobs_by_company.items()):
        jobs_sorted = sorted(jobs, key=lambda j: (not j.get("starred"), j["title"].lower()))
        starred_in_co = sum(1 for j in jobs_sorted if j.get("starred"))
        star_note = f" · ⭐ {starred_in_co}" if starred_in_co else ""
        html += f'<h3 style="color:#0066cc">{company} <span style="font-size:13px;color:#888">({len(jobs)} roles{star_note})</span></h3><ul>'
        for j in jobs_sorted:
            star = "⭐ " if j.get("starred") else ""
            loc = f" · {j['location']}" if j.get("location") else ""
            date = " · <span style='color:#aaa'>" + format_date(j.get("posted_at", "")) + "</span>"
            html += f'<li style="margin-bottom:8px"><a href="{j["url"]}" style="color:#0066cc"><b>{star}{j["title"]}</b></a><span style="color:#888;font-size:13px">{loc}{date}</span></li>'
        html += "</ul>"
    html += """<hr style="border:none;border-top:1px solid #eee;margin:20px 0">
<p style="color:#aaa;font-size:12px">⭐ = wearable, hardware, mapping, GPS, smartwatch, spatial computing, handheld device, outdoor product.<br>
Greenhouse + Lever + LinkedIn RSS · Runs every Monday at 9 AM CST.</p>
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

    # Greenhouse
    for company_name, company_id in GREENHOUSE_COMPANIES:
        print(f"Fetching Greenhouse: {company_name}...")
        jobs = fetch_greenhouse(company_name, company_id)
        for j in jobs:
            if j["url"] in seen_urls: continue
            if not is_relevant(j["title"]): continue
            if not is_west_coast(j["location"]): continue
            seen_urls.add(j["url"])
            j["starred"] = is_specialized(j)
            all_jobs.append(j)
        print(f"  → {len([j for j in all_jobs if j['company'] == company_name])} relevant roles")
        time.sleep(1)

    # Lever
    for company_name, company_id in LEVER_COMPANIES:
        print(f"Fetching Lever: {company_name}...")
        jobs = fetch_lever(company_name, company_id)
        for j in jobs:
            if j["url"] in seen_urls: continue
            if not is_relevant(j["title"]): continue
            if not is_west_coast(j["location"]): continue
            seen_urls.add(j["url"])
            j["starred"] = is_specialized(j)
            all_jobs.append(j)
        print(f"  → {len([j for j in all_jobs if j['company'] == company_name])} relevant roles")
        time.sleep(1)

    # LinkedIn RSS
    for company_name, keywords, location in LINKEDIN_SEARCHES:
        print(f"Fetching LinkedIn RSS: {company_name} ({keywords})...")
        jobs = fetch_linkedin_rss(company_name, keywords, location)
        for j in jobs:
            if j["url"] in seen_urls: continue
            if not is_relevant(j["title"]): continue
            seen_urls.add(j["url"])
            j["starred"] = is_specialized(j)
            all_jobs.append(j)
        print(f"  → {len(jobs)} results from RSS")
        time.sleep(2)

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
