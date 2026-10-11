import requests
import smtplib
import os
import time
import re
import argparse
import json
import html as htmllib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from html.parser import HTMLParser

# Default recipient — override with the TO_EMAIL env var or --to
DEFAULT_TO_EMAIL = "yuerzhu02@gmail.com"
EXCLUDE = ["principal", "director", "head of", "vp ", "senior", "staff", "lead designer", "sr ", "sr.", "lead "]
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

WEST_COAST = [
    "san francisco", "palo alto", "mountain view", "sunnyvale", "santa clara",
    "cupertino", "menlo park", "redwood city", "san jose", "los angeles",
    "irvine", "san diego", "california", ", ca", " ca,", "(ca)",
    "culver city", "santa monica", "playa vista", "los gatos", "san mateo", "burlingame",
    "foster city", "oakland", "emeryville", "berkeley", "south san francisco",
    "seattle", "bellevue", "redmond", "kirkland", "washington", ", wa", " wa,",
    "portland", "oregon", ", or", "remote", "united states", "usa", ", us,",
    "anywhere", "distributed", "hybrid"
]

BAY_AREA = [
    "san francisco", "palo alto", "mountain view", "sunnyvale", "santa clara",
    "cupertino", "menlo park", "redwood city", "san jose", "los gatos", "san mateo",
    "burlingame", "foster city", "oakland", "emeryville", "berkeley", "south san francisco",
    "bay area"
]

# Region filters — pick with the REGION env var or --region
REGIONS = {
    "west-coast": ("West Coast + Remote", WEST_COAST),
    "bay-area":   ("Bay Area", BAY_AREA),
}

# Companies to scrape live in companies.json — one line per company.
COMPANIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "companies.json")

# Search term sent to career sites that support keyword search (every KEYWORDS entry contains it)
SEARCH_TERM = "designer"

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
                "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%B %d, %Y"):
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

def in_region(location, places):
    if not location:
        return False
    loc = location.lower()
    return any(place in loc for place in places)

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
    for url in [
        f"https://api.lever.co/v0/postings/{company_id}?mode=json",
        f"https://jobs.lever.co/{company_id}?format=json",
    ]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
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
        except Exception:
            pass
    print(f"  Lever failed for {company_name}")
    return []

def fetch_linkedin(company_name, keywords):
    """Fetch LinkedIn jobs via their guest search API."""
    url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    params = {
        "keywords": keywords,
        "location": "United States",
        "f_TPR": "r2592000",  # last 30 days
        "f_JT": "F",          # full time
        "start": 0,
        "count": 10,
    }
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)
        if r.status_code != 200:
            print(f"  LinkedIn error for {company_name}: {r.status_code}")
            return []

        # Parse each job card separately so title/company/location/url stay aligned
        jobs = []
        for card in r.text.split("<li")[1:]:
            title = re.search(r'class="base-search-card__title"[^>]*>\s*([^<]+?)\s*<', card)
            company = re.search(r'class="base-search-card__subtitle"[^>]*>\s*(?:<[^>]+>\s*)?([^<]+?)\s*<', card)
            location = re.search(r'class="job-search-card__location"[^>]*>\s*([^<]+?)\s*<', card)
            link = re.search(r'href="(https://www\.linkedin\.com/jobs/view/[^"?]+)', card)
            posted = re.search(r'<time[^>]*datetime="([^"]+)"', card)
            if not (title and link):
                continue
            # LinkedIn search matches loosely — drop jobs posted by other companies
            if not company or company_name.lower() not in company.group(1).lower():
                continue
            jobs.append({
                "title": htmllib.unescape(title.group(1)),
                "company": company_name,
                "location": htmllib.unescape(location.group(1)) if location else "United States",
                "url": link.group(1),
                "posted_at": posted.group(1) if posted else "",
                "description": ""
            })
        return jobs
    except Exception as e:
        print(f"  LinkedIn exception for {company_name}: {e}")
        return []

def fetch_ashby(company_name, org):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{org}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"  Ashby error for {company_name}: {r.status_code}")
            return []
        jobs = []
        for j in r.json().get("jobs", []):
            locations = [j.get("location", "")] + [l.get("location", "") for l in j.get("secondaryLocations", [])]
            jobs.append({
                "title": j.get("title", ""),
                "company": company_name,
                "location": "; ".join(l for l in locations if l),
                "url": j.get("jobUrl", ""),
                "posted_at": j.get("publishedAt", ""),
                "description": j.get("descriptionPlain", "") or ""
            })
        return jobs
    except Exception as e:
        print(f"  Ashby exception for {company_name}: {e}")
        return []

def fetch_workday(company_name, board_url):
    """Workday boards (e.g. https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite)."""
    m = re.match(r"(https://([^.]+)\.[^/]+)/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)", board_url)
    if not m:
        print(f"  Workday: can't parse URL for {company_name}")
        return []
    host, tenant, site = m.groups()
    api = f"{host}/wday/cxs/{tenant}/{site}"
    jobs = []
    try:
        offset, total = 0, None
        while total is None or offset < min(total, 400):
            r = requests.post(f"{api}/jobs", headers={**HEADERS, "Content-Type": "application/json"},
                              json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": SEARCH_TERM},
                              timeout=20)
            if r.status_code != 200:
                print(f"  Workday error for {company_name}: {r.status_code}")
                break
            data = r.json()
            # Workday only reports the total on the first page
            if total is None:
                total = data.get("total", 0)
            postings = data.get("jobPostings", [])
            if not postings:
                break
            for p in postings:
                # Listing only says "2 Locations" etc., so fetch details for matching titles
                if not is_relevant(p.get("title", "")):
                    continue
                d = requests.get(f"{api}{p['externalPath']}", headers=HEADERS, timeout=20)
                if d.status_code != 200:
                    continue
                info = d.json().get("jobPostingInfo", {})
                locations = [info.get("location", "")] + info.get("additionalLocations", [])
                jobs.append({
                    "title": info.get("title", p["title"]),
                    "company": company_name,
                    "location": "; ".join(l for l in locations if l),
                    "url": info.get("externalUrl", f"{board_url}{p['externalPath']}"),
                    "posted_at": info.get("startDate", ""),
                    "description": info.get("jobDescription", "")
                })
            offset += len(postings)
    except Exception as e:
        print(f"  Workday exception for {company_name}: {e}")
    return jobs

def fetch_eightfold(company_name, base_url, domain):
    """Eightfold career sites (e.g. Netflix)."""
    jobs = []
    try:
        start, count = 0, None
        while count is None or start < min(count, 300):
            r = requests.get(f"{base_url}/api/apply/v2/jobs", headers=HEADERS, timeout=20,
                             params={"domain": domain, "query": SEARCH_TERM, "start": start, "num": 10})
            if r.status_code != 200:
                print(f"  Eightfold error for {company_name}: {r.status_code}")
                break
            data = r.json()
            count = data.get("count", 0)
            positions = data.get("positions", [])
            if not positions:
                break
            for p in positions:
                jobs.append({
                    "title": p.get("name", ""),
                    "company": company_name,
                    "location": "; ".join(p.get("locations") or [p.get("location", "")]),
                    "url": p.get("canonicalPositionUrl", ""),
                    "posted_at": str(p.get("t_create", "")),
                    "description": p.get("job_description", "") or ""
                })
            start += len(positions)
    except Exception as e:
        print(f"  Eightfold exception for {company_name}: {e}")
    return jobs

def fetch_jibe(company_name, base_url):
    """Jibe career sites (e.g. careers.amd.com)."""
    jobs = []
    try:
        for page in range(1, 21):
            r = requests.get(f"{base_url}/api/jobs", headers=HEADERS, timeout=20,
                             params={"keywords": SEARCH_TERM, "limit": 100, "page": page})
            if r.status_code != 200:
                print(f"  Jibe error for {company_name}: {r.status_code}")
                break
            results = r.json().get("jobs", [])
            for item in results:
                j = item.get("data", {})
                jobs.append({
                    "title": j.get("title", ""),
                    "company": company_name,
                    "location": j.get("full_location") or j.get("location_name", ""),
                    "url": f"{base_url}/careers-home/jobs/{j.get('slug', '')}",
                    "posted_at": j.get("posted_date", ""),
                    "description": j.get("description", "") or ""
                })
            if len(results) < 100:
                break
    except Exception as e:
        print(f"  Jibe exception for {company_name}: {e}")
    return jobs

def fetch_talentbrew(company_name, base_url):
    """TalentBrew career sites (e.g. jobs.intuit.com) — search results come back as HTML."""
    jobs = []
    try:
        for page in range(1, 6):
            r = requests.get(f"{base_url}/search-jobs/results", timeout=20,
                             headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
                             params={"ActiveFacetID": 0, "CurrentPage": page, "RecordsPerPage": 100,
                                     "Keywords": SEARCH_TERM, "SearchResultsModuleName": "Search Results",
                                     "SearchFiltersModuleName": "Search Filters", "SearchType": 5})
            if r.status_code != 200:
                print(f"  TalentBrew error for {company_name}: {r.status_code}")
                break
            results = r.json().get("results", "")
            found = 0
            for a in re.finditer(r'<a href="(/job/([^/"]+)/[^"]+)"[^>]*data-title="([^"]*)"[^>]*>(.*?)</a>', results, re.S):
                path, city_slug, title, inner = a.groups()
                loc = re.search(r'class="job-location">\s*([^<]+?)\s*<', inner)
                # "Multiple Locations" is common — the URL's city slug is the primary location
                location = f"{loc.group(1) if loc else ''} ({city_slug.replace('-', ' ')})"
                jobs.append({
                    "title": htmllib.unescape(title),
                    "company": company_name,
                    "location": location,
                    "url": base_url + path,
                    "posted_at": "",
                    "description": ""
                })
                found += 1
            if found < 100:
                break
    except Exception as e:
        print(f"  TalentBrew exception for {company_name}: {e}")
    return jobs

def fetch_amazon(company_name):
    """amazon.jobs search JSON (includes subsidiaries like Twitch, AWS, Zoox)."""
    jobs = []
    try:
        offset, hits = 0, None
        while hits is None or offset < min(hits, 1000):
            r = requests.get("https://www.amazon.jobs/en/search.json", headers=HEADERS, timeout=20,
                             params={"base_query": SEARCH_TERM, "country": "USA",
                                     "result_limit": 100, "offset": offset, "sort": "recent"})
            if r.status_code != 200:
                print(f"  Amazon error: {r.status_code}")
                break
            data = r.json()
            hits = data.get("hits", 0)
            results = data.get("jobs", [])
            if not results:
                break
            for j in results:
                # Twitch posts through amazon.jobs too — keep its name instead of "Amazon"
                company = "Twitch" if "twitch" in (j.get("company_name") or "").lower() else company_name
                jobs.append({
                    "title": j.get("title", ""),
                    "company": company,
                    # Raw "US, CA, San Francisco" form — normalized_location always ends in
                    # "USA", which would pass the West Coast filter for every US job
                    "location": j.get("location") or j.get("normalized_location", ""),
                    "url": "https://www.amazon.jobs" + j.get("job_path", ""),
                    "posted_at": j.get("posted_date", ""),
                    "description": j.get("description", "") or ""
                })
            offset += len(results)
    except Exception as e:
        print(f"  Amazon exception: {e}")
    return jobs

def fetch_apple(company_name):
    """jobs.apple.com — results are embedded as JSON in the search page."""
    jobs = []
    try:
        # Unquoted searches match any word (thousands of results), so search each exact phrase
        for phrase in KEYWORDS:
            for page in range(1, 11):
                r = requests.get("https://jobs.apple.com/en-us/search", headers=HEADERS, timeout=20,
                                 params={"search": f'"{phrase}"', "location": "united-states-USA", "page": page})
                if r.status_code != 200:
                    print(f"  Apple error: {r.status_code}")
                    break
                m = re.search(r'window\.__staticRouterHydrationData\s*=\s*JSON\.parse\((".*?")\);', r.text, re.S)
                if not m:
                    print("  Apple: search data not found in page")
                    break
                data = json.loads(json.loads(m.group(1)))["loaderData"]["search"]
                results = data.get("searchResults", [])
                for j in results:
                    # Leave out countryName — "United States of America" would pass the West Coast filter
                    location = "; ".join(
                        ", ".join(v for v in (l.get("name"), l.get("city"), l.get("stateProvince")) if v)
                        for l in j.get("locations", []))
                    jobs.append({
                        "title": j.get("postingTitle", ""),
                        "company": company_name,
                        "location": location,
                        "url": f"https://jobs.apple.com/en-us/details/{j.get('positionId')}/{j.get('transformedPostingTitle', '')}",
                        "posted_at": j.get("postDateInGMT", ""),
                        "description": j.get("jobSummary", "") or ""
                    })
                if not results or page * 20 >= data.get("totalRecords", 0):
                    break
                time.sleep(1)
    except Exception as e:
        print(f"  Apple exception: {e}")
    return jobs

FETCHERS = {
    "greenhouse": lambda c: fetch_greenhouse(c["company"], c["id"]),
    "lever":      lambda c: fetch_lever(c["company"], c["id"]),
    "ashby":      lambda c: fetch_ashby(c["company"], c["id"]),
    "workday":    lambda c: fetch_workday(c["company"], c["url"]),
    "eightfold":  lambda c: fetch_eightfold(c["company"], c["url"], c["domain"]),
    "jibe":       lambda c: fetch_jibe(c["company"], c["url"]),
    "talentbrew": lambda c: fetch_talentbrew(c["company"], c["url"]),
    "amazon":     lambda c: fetch_amazon(c["company"]),
    "apple":      lambda c: fetch_apple(c["company"]),
    "linkedin":   lambda c: fetch_linkedin(c["company"], c["query"]),
}

# ── Email ─────────────────────────────────────────────────────────────────────

def build_email(jobs_by_company, region_label):
    all_jobs = [j for jobs in jobs_by_company.values() for j in jobs]
    total = len(all_jobs)
    starred_count = sum(1 for j in all_jobs if j.get("starred"))
    date_str = datetime.now().strftime("%B %d, %Y")
    html = f"""<html><body style="font-family:sans-serif;color:#222;max-width:700px;margin:auto;padding:24px">
<h2>🎨 Weekly Design Job Digest — {date_str}</h2>
<p>{total} roles found · <b>⭐ {starred_count} match your specializations</b></p>
<p style="color:#888;font-size:13px">Product/UX/Interaction Designer · {region_label} · Mid-level · ⭐ = wearable / hardware / mapping / GPS / spatial</p>
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
Company career sites + LinkedIn · Runs every Monday at 9 AM CST.</p>
</body></html>"""
    return html

def send_email(html_body, to_email):
    from_email = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎨 Weekly Design Jobs — {datetime.now().strftime('%b %d')}"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_email, app_password)
        server.sendmail(from_email, to_email, msg.as_string())
    print(f"✅ Email sent to {to_email}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print results instead of emailing")
    parser.add_argument("--to", default=os.environ.get("TO_EMAIL") or DEFAULT_TO_EMAIL)
    parser.add_argument("--region", default=os.environ.get("REGION") or "west-coast", choices=REGIONS)
    args = parser.parse_args()
    region_label, region_places = REGIONS[args.region]
    with open(COMPANIES_FILE) as f:
        companies = json.load(f)

    all_jobs = []
    seen_urls = set()

    for c in companies:
        source = c["source"]
        if source not in FETCHERS:
            print(f"Unknown source '{source}' for {c['company']} — skipping")
            continue
        print(f"Fetching {source}: {c['company']}...")
        jobs = FETCHERS[source](c)
        added = 0
        for j in jobs:
            if j["url"] in seen_urls: continue
            if not is_relevant(j["title"]): continue
            if not in_region(j["location"], region_places): continue
            seen_urls.add(j["url"])
            j["starred"] = is_specialized(j)
            all_jobs.append(j)
            added += 1
        print(f"  → {added} relevant roles (filtered from {len(jobs)} total)")
        time.sleep(2 if source == "linkedin" else 1)

    # Group by company
    jobs_by_company = {}
    for j in all_jobs:
        company = j["company"]
        if company not in jobs_by_company:
            jobs_by_company[company] = []
        jobs_by_company[company].append(j)

    print(f"\nTotal: {len(all_jobs)} roles across {len(jobs_by_company)} companies")

    if args.dry_run:
        for company, jobs in jobs_by_company.items():
            for j in jobs:
                print(f"  {'★ ' if j['starred'] else ''}{company}: {j['title']} — {j['location']} — {j['url']}")
    elif jobs_by_company:
        html = build_email(jobs_by_company, region_label)
        send_email(html, args.to)
    else:
        print("No relevant jobs found this week.")

if __name__ == "__main__":
    main()
