"""
Supplier Sales Email Finder Agent — Web Scraping Version
---------------------------------------------------------
1. DDG search → find official website
2. Scrape contact/about pages → extract real emails
3. LLM picks the best sales email OR returns contact page URL as fallback
4. Saves confirmed email (high quality) or contact_page_url (fallback)

Usage:
    python supplier_email_agent.py
    python supplier_email_agent.py --force
    python supplier_email_agent.py --supplier-id 1 --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent

MODEL = "gpt-4o"
SLEEP_BETWEEN_SUPPLIERS = 2
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

CONTACT_PAGE_KEYWORDS = [
    "contact", "contact-us", "contacts", "about", "about-us",
    "sales", "reach-us", "get-in-touch", "inquiry", "enquiry",
]

# Emails that are clearly NOT for B2B sales inquiries
BAD_EMAIL_PREFIXES = [
    "sponsor", "press", "media", "pr@", "hr@", "jobs@", "career",
    "privacy", "legal", "compliance", "noreply", "no-reply",
    "donotreply", "webmaster", "abuse", "security", "support@",
    "help@", "billing@", "invoice@", "payment@",
]

EMAIL_REGEX = re.compile(
    r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b'
)

IGNORE_EMAIL_PATTERNS = [
    "example.com", "domain.com", "email.com",
    "noreply", "no-reply", "donotreply",
    "privacy", "legal", "webmaster", "sentry", "wix.com",
]

SKIP_DOMAINS = [
    "linkedin", "facebook", "twitter", "yelp", "wikipedia",
    "bloomberg", "crunchbase", "dnb.com", "glassdoor",
    "zoominfo", "hoovers", "manta.com", "baidu.com",
    "medscape.com", "drugs.com",
]

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def _load_config() -> tuple[str, str]:
    env_path = _ROOT / ".env"
    db_path  = _ROOT / "db.sqlite"

    if not env_path.exists():
        raise FileNotFoundError(f".env not found at {env_path}")
    if not db_path.exists():
        raise FileNotFoundError(f"db.sqlite not found at {db_path}")

    api_key = None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "OPENAI_API_KEY":
            api_key = value.strip().strip('"').strip("'")
            break

    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in .env")

    print(f"[Config] DB:      {db_path}")
    print(f"[Config] API key: {api_key[:12]}...{api_key[-4:]}")
    return api_key, str(db_path)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _ensure_columns(conn: sqlite3.Connection) -> None:
    for col, col_type in [
        ("sales_email",       "TEXT"),
        ("email_confidence",  "TEXT"),
        ("email_source",      "TEXT"),
        ("email_searched_at", "TEXT"),
        ("company_website",   "TEXT"),
        ("contact_page_url",  "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE Supplier ADD COLUMN {col} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass


def _get_suppliers(
    conn: sqlite3.Connection,
    supplier_id: Optional[int] = None,
    skip_existing: bool = True,
) -> list[tuple[int, str]]:
    query = "SELECT Id, Name FROM Supplier"
    conditions = []
    if supplier_id is not None:
        conditions.append(f"Id = {supplier_id}")
    elif skip_existing:
        conditions.append("(sales_email IS NULL AND email_confidence IS NULL)")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY Name"
    return [(r[0], r[1]) for r in conn.execute(query).fetchall()]


def _write_result(
    conn: sqlite3.Connection,
    supplier_id: int,
    email: Optional[str],
    confidence: str,
    source: Optional[str],
    website: Optional[str],
    contact_page: Optional[str],
) -> None:
    conn.execute(
        """UPDATE Supplier SET
            sales_email=?, email_confidence=?, email_source=?,
            email_searched_at=datetime('now'), company_website=?,
            contact_page_url=?
           WHERE Id=?""",
        (email, confidence, source, website, contact_page, supplier_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Step 1: Find official website via DDG
# ---------------------------------------------------------------------------

def _search_website(supplier_name: str) -> Optional[str]:
    query = f"{supplier_name} official website ingredient supplier"

    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.error("Install ddgs: pip install ddgs")
            return None

    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=10))

        for r in results:
            url = r.get("url") or r.get("href", "")
            if not url:
                continue
            parsed = urlparse(url)
            if not any(s in parsed.netloc for s in SKIP_DOMAINS):
                return f"{parsed.scheme}://{parsed.netloc}"
    except Exception as exc:
        logger.warning("DDG search failed for %r: %s", supplier_name, exc)

    # Fallback: guess domain from first word of name
    try:
        slug = re.sub(r"[^a-z0-9]", "", supplier_name.lower().split()[0])
        for url in [f"https://www.{slug}.com", f"https://{slug}.com"]:
            resp = httpx.get(url, headers=HEADERS, timeout=8, follow_redirects=True)
            if resp.status_code == 200:
                parsed = urlparse(str(resp.url))
                return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Step 2: Scrape website for emails + find contact pages
# ---------------------------------------------------------------------------

def _fetch_page(url: str, timeout: int = 10) -> Optional[str]:
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=timeout,
                         follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
        return None
    except Exception:
        return None


def _extract_emails_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    emails = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            email = href[7:].split("?")[0].strip().lower()
            if EMAIL_REGEX.match(email):
                emails.add(email)

    text = soup.get_text()
    for match in EMAIL_REGEX.finditer(text):
        emails.add(match.group().lower())

    filtered = []
    for email in emails:
        if any(p in email for p in IGNORE_EMAIL_PATTERNS):
            continue
        if len(email) > 100:
            continue
        filtered.append(email)

    return filtered


def _find_contact_pages(base_url: str, homepage_html: str) -> list[str]:
    soup = BeautifulSoup(homepage_html, "html.parser")
    contact_urls = []
    base_domain = urlparse(base_url).netloc

    for a in soup.find_all("a", href=True):
        href = a["href"].lower().strip()
        text = a.get_text().lower().strip()
        if any(kw in href or kw in text for kw in CONTACT_PAGE_KEYWORDS):
            full_url = urljoin(base_url, a["href"])
            if urlparse(full_url).netloc == base_domain:
                if full_url not in contact_urls and full_url != base_url:
                    contact_urls.append(full_url)

    return contact_urls[:5]


def _is_good_sales_email(email: str) -> bool:
    """Returns True if email looks like a genuine B2B sales contact."""
    email_lower = email.lower()
    if any(p in email_lower for p in BAD_EMAIL_PREFIXES):
        return False
    return True


def _scrape_site(website: str) -> tuple[list[str], list[str], Optional[str]]:
    """
    Returns: (good_emails, all_emails, best_contact_page_url)
    """
    all_emails: list[str] = []
    contact_page_url: Optional[str] = None

    homepage_html = _fetch_page(website)
    if not homepage_html:
        return [], [], None

    all_emails.extend(_extract_emails_from_html(homepage_html))

    contact_pages = _find_contact_pages(website, homepage_html)

    for page_url in contact_pages:
        if contact_page_url is None:
            contact_page_url = page_url  # save first contact page as fallback
        time.sleep(0.5)
        html = _fetch_page(page_url)
        if html:
            page_emails = _extract_emails_from_html(html)
            all_emails.extend(page_emails)

    # Deduplicate
    seen: set[str] = set()
    unique: list[str] = []
    for e in all_emails:
        if e not in seen:
            seen.add(e)
            unique.append(e)

    good_emails = [e for e in unique if _is_good_sales_email(e)]

    return good_emails, unique, contact_page_url


# ---------------------------------------------------------------------------
# Step 3: LLM picks the best sales email
# ---------------------------------------------------------------------------

def _llm_pick_best_email(
    supplier_name: str,
    candidates: list[str],
    api_key: str,
) -> Optional[str]:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    prompt = f"""You are a B2B sales researcher.

Supplier: "{supplier_name}"
Real emails found on their website: {json.dumps(candidates)}

Pick the BEST email for a B2B sourcing inquiry.
Prefer: sales@, info@, contact@, procurement@, inquiry@, business@
Avoid: noreply@, privacy@, legal@, hr@, jobs@, sponsorships@, press@, support@

If none are suitable for a B2B sourcing inquiry, return null.

Respond ONLY with valid JSON:
{{
  "best_email": "<chosen email or null>",
  "reasoning": "<one sentence>"
}}"""

    try:
        resp = httpx.post(
            OPENAI_API_URL,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.0,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = json.loads(resp.json()["choices"][0]["message"]["content"])
        chosen = (data.get("best_email") or "").strip().lower()
        if chosen in candidates:
            return chosen
        return None
    except Exception as exc:
        logger.warning("LLM pick failed: %s", exc)
        return candidates[0]


# ---------------------------------------------------------------------------
# Main per-supplier function
# ---------------------------------------------------------------------------

def find_supplier_email(
    supplier_name: str,
    api_key: str,
) -> tuple[Optional[str], str, Optional[str], Optional[str], Optional[str]]:
    """Returns: (email, confidence, source_url, website, contact_page_url)"""

    print(f"           → searching website...", end=" ", flush=True)
    website = _search_website(supplier_name)
    if not website:
        print("no website found")
        return None, "not_found", None, None, None
    print(f"{website}")

    print(f"           → scraping...", end=" ", flush=True)
    good_emails, all_emails, contact_page_url = _scrape_site(website)

    if good_emails:
        print(f"good emails: {good_emails[:3]}")
        email = _llm_pick_best_email(supplier_name, good_emails, api_key)
        if email:
            return email, "confirmed", website, website, contact_page_url

    # No good email — fall back to contact page
    if all_emails:
        bad_only = [e for e in all_emails if not _is_good_sales_email(e)]
        print(f"only unsuitable emails {bad_only[:2]} → contact page fallback")
    else:
        print(f"no emails → contact page fallback")

    return None, "contact_page", None, website, contact_page_url


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_agent(
    conn: sqlite3.Connection,
    api_key: str,
    supplier_id: Optional[int] = None,
    dry_run: bool = False,
    skip_existing: bool = True,
) -> list[dict]:
    _ensure_columns(conn)
    suppliers = _get_suppliers(conn, supplier_id=supplier_id,
                               skip_existing=skip_existing)

    print(f"\n[Agent] {len(suppliers)} supplier(s) to process.\n")
    if not suppliers:
        print("[Agent] Nothing to do.")
        return []

    results = []

    for i, (sid, name) in enumerate(suppliers, 1):
        print(f"[{i:2d}/{len(suppliers)}] {name}")

        email, confidence, source, website, contact_page = find_supplier_email(
            name, api_key
        )

        if email:
            print(f"           ✓ email: {email}")
        elif contact_page:
            print(f"           → contact page: {contact_page}")
        else:
            print(f"           ✗ nothing found")

        result = {
            "supplier_id": sid,
            "supplier_name": name,
            "email": email,
            "confidence": confidence,
            "source": source,
            "website": website,
            "contact_page": contact_page,
        }
        results.append(result)

        if not dry_run:
            _write_result(conn, sid, email, confidence, source, website, contact_page)

        if i < len(suppliers):
            time.sleep(SLEEP_BETWEEN_SUPPLIERS)

    found_email = sum(1 for r in results if r["email"])
    found_page  = sum(1 for r in results if not r["email"] and r["contact_page"])
    not_found   = len(results) - found_email - found_page

    print(f"\n{'='*50}")
    print(f"[Agent] Done!")
    print(f"  ✓ Email found:        {found_email}/{len(results)}")
    print(f"  → Contact page only:  {found_page}/{len(results)}")
    print(f"  ✗ Nothing found:      {not_found}/{len(results)}")
    if dry_run:
        print("  [DRY RUN — nothing written to DB]")

    return results


def print_results(conn: sqlite3.Connection) -> None:
    rows = conn.execute("""
        SELECT Name, sales_email, email_confidence, company_website, contact_page_url
        FROM Supplier
        WHERE email_searched_at IS NOT NULL
        ORDER BY email_confidence DESC, Name
    """).fetchall()

    print(f"\n{'Supplier':<35} {'Email / Contact Page':<55} {'Conf'}")
    print("-" * 100)
    for r in rows:
        display = r[1] or r[4] or "N/A"
        print(f"{r[0]:<35} {display:<55} {r[2]}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--supplier-id", type=int, default=None)
    p.add_argument("--dry-run",     action="store_true")
    p.add_argument("--force",       action="store_true")
    p.add_argument("--show",        action="store_true")
    p.add_argument("--log-level",   default="WARNING",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = p.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    api_key, db_path = _load_config()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        if args.show:
            print_results(conn)
        else:
            _ensure_columns(conn)
            if args.force:
                target = f"Id = {args.supplier_id}" if args.supplier_id else "1=1"
                conn.execute(f"""UPDATE Supplier SET
                    sales_email=NULL, email_confidence=NULL,
                    email_source=NULL, email_searched_at=NULL,
                    company_website=NULL, contact_page_url=NULL
                    WHERE {target}""")
                conn.commit()
                print("[Force] Reset done.")

            run_agent(
                conn,
                api_key=api_key,
                supplier_id=args.supplier_id,
                dry_run=args.dry_run,
                skip_existing=not args.force,
            )
            print_results(conn)
    finally:
        conn.close()