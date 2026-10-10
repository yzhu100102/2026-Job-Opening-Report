import requests
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
TO_EMAIL = "yuerzhu02@gmail.com"

EXCLUDE = ["principal", "director", "head of", "vp ", "senior", "staff", "lead designer"]

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

# Companies to search — JSearch will find their listings across job boards
COMPANIES = [
    "Apple", "Google", "Meta", "Microsoft", "Amazon",
    "Airbnb", "Figma", "Notion", "Stripe", "Lyft",
    "Dropbox", "Pinterest", "Robinhood", "Waymo", "Rivian",
    "Coinbase", "Netflix", "Spotify", "Snap", "Airtable",
    "Samsung", "Duolingo", "Twitch", "Adobe", "Uber",
    "DoorDash", "Instacart", "Canva", "Atlassian", "Salesforce"
]

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_HEADERS = {
    "X-RapidAPI-Key": os.environ.get("RAPIDAPI_KEY", ""),
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def format_date(date_str):
    if not date_str:
        return "Date unknown"
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
    # Try unix timestamp
    try:
        dt = datetime.fromtimestamp(int(date_str), tz=timezone.utc)
        days_ago = (datetime.now(timezone.utc) - dt).days
        if days_ago == 0:   return "Posted today"
        if days_ago == 1:   return "Posted yesterday"
        if days_ago <= 7:   return f"Posted {days_ago} days ago"
        return f"Posted {dt.strftime('%b %d, %Y')} ({days_ago}d ago)"
    except Exception:
        pass
    return "Date unknown"

def is_specialized(job):
    text = (job.get("description", "") + " " + job.get("title", "")).lower()
    return any(kw in text for kw in SPECIALIZATION_KEYWORDS)

def is_relevant(title):
    t = title.lower()
    keywords = ["product designer", "ux designer", "interaction designer", "ui designer"]
    if not any(k in t for k in keywords):
        return False
    if any(ex in t for ex in EXCLUDE):
        return False
    return True

# ── JSearch fetcher ───────────────────────────────────────────────────────────

def search_jobs(company):
    """Search JSearch for designer roles at a specific company on the west coast."""
    query = f"product designer OR ux designer at {company} in San Francisco OR Seattle OR Los Angeles OR remote"
    try:
        r = requests.get(
            JSEARCH_URL,
            headers=JSEARCH_HEADERS,
            params={
                "query": query,
                "num_pages": "2",
                "date_posted": "month",
                "employment_types": "FULLTIME",
                "job_requirements": "no_degree,under_3_years_experience,more_than_3_years_experience",
            },
            timeout=20
        )
        if r.status_code != 200:
            print(f"  JSearch error for {company}: {r.status_code} {r.text[:100]}")
            return []
        return r.json().get("data", [])
    except Exception as e:
        print(f"  JSearch error for {company}: {e}")
        return []

def normalise_jsearch(raw, company_name):
    """Convert JSearch results to our standard job format."""
    out = []
    for j in raw:
        # Only keep jobs actually from this company
        employer = j.get("employer_name", "").lower()
        if company_name.lower() not in employer:
            continue

        location_parts = []
        if j.get("job_city"):      location_parts.append(j["job_city"])
        if j.get("job_state"):     location_parts.append(j["job_state"])
        if j.get("job_country"):   location_parts.append(j["job_country"])
        location = ", ".join(location_parts) if location_parts else (
            "Remote" if j.get("job_is_remote") else "")

        out.append({
            "title": j.get("job_title", ""),
            "location": location,
            "url": j.get("job_apply_link") or j.get("job_google_link", ""),
            "company": j.get("employer_name", company_name),
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
    jobs_by_company = {}

    for company in COMPANIES:
        print(f"Searching {company}...")
        raw = search_jobs(company)
        jobs = normalise_jsearch(raw, company)

        for j in jobs:
            j["starred"] = is_specialized(j)

        filtered = [j for j in jobs if is_relevant(j["title"])]
        starred_n = sum(1 for j in filtered if j.get("starred"))
        print(f"  → {len(filtered)} relevant roles ({starred_n} starred)")
        if filtered:
            jobs_by_company[company] = filtered

    if jobs_by_company:
        html = build_email(jobs_by_company)
        send_email(html)
    else:
        print("No relevant jobs found this week.")

if __name__ == "__main__":
    main()
