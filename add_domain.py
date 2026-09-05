#!/Users/anand/.local/share/uv/tools/cottagecrawl/bin/python3
"""
add_domain.py <domain> [--llm] [--llm-url URL] [--llm-model MODEL]

Scrapes the domain, extracts author/location/github via heuristics (default)
or an LLM (pass --llm), then opens a PR to add a row to index.csv.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx
import trafilatura
from bs4 import BeautifulSoup

SLASH_PAGES = ["", "about", "now", "uses", "contact"]
USER_AGENT = "SlashIndex-Bot/1.0 (+https://slashindex.fyi)"
REPO = "AvilPage/SlashIndex.fyi"
INDEX_CSV = Path(__file__).parent / "index.csv"

GITHUB_SKIP = {"features", "topics", "trending", "marketplace", "explore", "sponsors", "orgs", "organizations"}

TOPIC_KEYWORDS = [
    "technology", "tech", "programming", "software", "coding", "developer", "engineering",
    "health", "fitness", "wellness", "nutrition", "medicine",
    "travel", "photography", "art", "design", "music",
    "finance", "investing", "economics", "money",
    "science", "research", "machine learning", "ai", "data",
    "writing", "books", "literature", "philosophy",
    "gaming", "food", "cooking", "parenting", "education",
    "politics", "history", "culture", "environment", "sustainability",
]

ISO_TO_FLAG = {
    "IN": "🇮🇳", "US": "🇺🇸", "GB": "🇬🇧", "CA": "🇨🇦", "AU": "🇦🇺",
    "DE": "🇩🇪", "FR": "🇫🇷", "NL": "🇳🇱", "SE": "🇸🇪", "NO": "🇳🇴",
    "DK": "🇩🇰", "FI": "🇫🇮", "JP": "🇯🇵", "CN": "🇨🇳", "BR": "🇧🇷",
    "SG": "🇸🇬", "NZ": "🇳🇿", "CH": "🇨🇭", "AT": "🇦🇹", "PL": "🇵🇱",
    "ES": "🇪🇸", "IT": "🇮🇹", "PT": "🇵🇹",
}


def geocode_city(city: str) -> dict:
    """Return {country, state} for city — CSV index first, Nominatim fallback."""
    city_lower = city.strip().lower()
    try:
        import csv
        with INDEX_CSV.open() as f:
            for row in csv.DictReader(f):
                if row.get("city", "").strip().lower() == city_lower:
                    result = {}
                    if row.get("country"):
                        result["country"] = row["country"]
                    if row.get("state"):
                        result["state"] = row["state"]
                    if result:
                        return result
    except Exception:
        pass

    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1, "addressdetails": 1},
            headers={"User-Agent": "SlashIndex.fyi/1.0"},
            timeout=10,
        )
        data = resp.json()
        if not data:
            return {}
        addr = data[0].get("address", {})
        iso = addr.get("country_code", "").upper()
        flag = ISO_TO_FLAG.get(iso, "")
        country = f"{flag} {iso}" if flag else iso
        state = addr.get("state", "")
        return {"country": country, "state": state}
    except Exception:
        return {}


FLAG_MAP = {
    "india": "🇮🇳 IN", "united states": "🇺🇸 US", "usa": "🇺🇸 US", "uk": "🇬🇧 GB",
    "united kingdom": "🇬🇧 GB", "canada": "🇨🇦 CA", "australia": "🇦🇺 AU",
    "germany": "🇩🇪 DE", "france": "🇫🇷 FR", "netherlands": "🇳🇱 NL",
    "sweden": "🇸🇪 SE", "norway": "🇳🇴 NO", "denmark": "🇩🇰 DK",
    "finland": "🇫🇮 FI", "japan": "🇯🇵 JP", "china": "🇨🇳 CN",
    "brazil": "🇧🇷 BR", "singapore": "🇸🇬 SG", "new zealand": "🇳🇿 NZ",
    "switzerland": "🇨🇭 CH", "austria": "🇦🇹 AT", "poland": "🇵🇱 PL",
    "spain": "🇪🇸 ES", "italy": "🇮🇹 IT", "portugal": "🇵🇹 PT",
}


def fetch_page(client: httpx.Client, url: str) -> str:
    try:
        resp = client.get(url, timeout=15, follow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return ""


def scrape_domain(domain: str) -> dict[str, tuple[str, str]]:
    """Returns {page_name: (html, text)}"""
    pages: dict[str, tuple[str, str]] = {}
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for page in SLASH_PAGES:
            for scheme in ("https", "http"):
                url = f"{scheme}://{domain}/{page}".rstrip("/")
                html = fetch_page(client, url)
                if html:
                    text = trafilatura.extract(html, include_links=True, include_images=False) or ""
                    pages[page or "home"] = (html, text[:4000])
                    break
    return pages


def extract_github(html: str, text: str) -> str | None:
    matches = re.findall(r"github\.com/([A-Za-z0-9_-]+)", html + " " + text)
    for m in matches:
        if m.lower() not in GITHUB_SKIP:
            return m
    return None


def extract_author(html: str, text: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag, attr in [
        ("meta", {"name": "author"}),
        ("meta", {"property": "article:author"}),
        ("meta", {"name": "twitter:creator"}),
    ]:
        el = soup.find(tag, attr)
        if el and el.get("content", "").strip():
            val = el["content"].strip()
            if not val.startswith("@") and len(val) < 60:
                return val

    # og:site_name as fallback author if it looks like a person name
    og_name = soup.find("meta", {"property": "og:site_name"})
    if og_name and og_name.get("content"):
        val = og_name["content"].strip()
        if " " in val and len(val) < 40:
            return val

    return ""


def extract_location(html: str, text: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, str] = {}

    # geo meta tags
    geo = soup.find("meta", {"name": "geo.region"})
    if geo and geo.get("content"):
        # format: "IN-KA"
        parts = geo["content"].split("-")
        if parts:
            country_code = parts[0].upper()
            result["country_code"] = country_code

    geo_place = soup.find("meta", {"name": "geo.placename"})
    if geo_place and geo_place.get("content"):
        result["city"] = geo_place["content"].strip()

    # scan text for known countries
    lower_text = text.lower()
    for name, flag in FLAG_MAP.items():
        if re.search(r"\b" + re.escape(name) + r"\b", lower_text):
            result["country"] = flag
            break

    # attach flag from country_code if country not found via text
    if "country_code" in result and "country" not in result:
        code_to_flag = {v.split()[-1]: v for v in FLAG_MAP.values()}
        result["country"] = code_to_flag.get(result["country_code"], result["country_code"])

    return result


def extract_topics(domain: str, pages: dict[str, tuple[str, str]]) -> list[str]:
    all_html = "\n".join(h for h, _ in pages.values())
    all_text = "\n".join(t for _, t in pages.values()).lower()
    soup = BeautifulSoup(all_html, "html.parser")

    found: set[str] = set()

    # keywords meta tag
    kw_meta = soup.find("meta", {"name": "keywords"})
    if kw_meta and kw_meta.get("content"):
        for kw in kw_meta["content"].split(","):
            kw = kw.strip().lower()
            if 2 < len(kw) < 30:
                found.add(kw)

    # nav/tag/category links — extract slug words
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        for pat in ("/tag/", "/tags/", "/category/", "/categories/", "/topic/", "/topics/"):
            if pat in href:
                slug = href.split(pat)[-1].strip("/").split("/")[0].split("?")[0]
                if slug and 2 < len(slug) < 30:
                    found.add(slug.replace("-", " ").replace("_", " "))

    # keyword scan against known list
    for kw in TOPIC_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", all_text):
            found.add(kw)

    return sorted(found)[:4]


def heuristic_extract(domain: str, pages: dict[str, tuple[str, str]]) -> dict:
    all_html = "\n".join(h for h, _ in pages.values())
    all_text = "\n".join(t for _, t in pages.values())

    about_html, about_text = pages.get("about", ("", ""))
    home_html, home_text = pages.get("home", ("", ""))

    author = extract_author(about_html or home_html, about_text or home_text)
    github = extract_github(all_html, all_text)
    location = extract_location(about_html or home_html, about_text or home_text)
    topics = extract_topics(domain, pages)

    return {
        "author": author,
        "github_username": github,
        "topics": topics,
        "country": location.get("country", ""),
        "state": location.get("state", ""),
        "city": location.get("city", ""),
    }


def llm_extract(domain: str, pages: dict[str, tuple[str, str]], base_url: str, model: str) -> dict:
    combined = "\n\n---\n\n".join(
        f"PAGE: /{name}\n{text}" for name, (_, text) in pages.items()
    )

    prompt = f"""Extract structured info about the blog/website owner from the scraped text below.

Domain: {domain}

Scraped content:
{combined[:8000]}

Return a JSON object with these fields (use null if unknown):
{{
  "author": "full name of the blog owner",
  "github_username": "github username (without github.com/)",
  "topics": ["list", "of", "topics", "the", "blog", "covers"],
  "country": "country with flag emoji and 2-letter code, e.g. '🇮🇳 IN'",
  "state": "state/province name",
  "city": "city name"
}}

Rules:
- author: the person's real name, not a handle
- github_username: only if explicitly linked or mentioned
- topics: up to 4 short lowercase tags describing the blog's content
- country/state/city: only if mentioned or clearly implied
- Return ONLY valid JSON, no explanation"""

    payload = {
        "model": model,
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}],
    }

    if "anthropic" in base_url or "api.anthropic" in base_url:
        import anthropic
        client = anthropic.Anthropic(base_url=base_url if "anthropic" not in base_url else None)
        msg = client.messages.create(**payload)
        raw = msg.content[0].text.strip()
    else:
        # OpenAI-compatible endpoint (local LLMs)
        resp = httpx.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 500},
            timeout=60,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def get_slash_pages(domain: str) -> list[str]:
    found = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
        for page in ["about", "now", "uses", "contact", "colophon"]:
            for scheme in ("https", "http"):
                url = f"{scheme}://{domain}/{page}"
                try:
                    resp = client.head(url, timeout=8, follow_redirects=True)
                    if resp.status_code == 200:
                        found.append(page)
                        break
                except Exception:
                    pass
    return found


def create_pr(domain: str, info: dict, slash_pages: list[str], github_username: str | None) -> None:
    branch = f"add/{domain.replace('.', '-')}"
    author = info.get("author") or ""
    country = info.get("country") or ""
    state = info.get("state") or ""
    city = info.get("city") or ""
    pages_str = ", ".join(slash_pages)

    topics_str = ", ".join(info.get("topics") or [])
    new_row = f'{domain},{author},"{topics_str}","{pages_str}",{country},{state},{city}'

    subprocess.run(["git", "checkout", "master"], check=True)
    subprocess.run(["git", "pull", "origin", "master"], check=True)
    subprocess.run(["git", "branch", "-D", branch], capture_output=True)
    subprocess.run(["git", "checkout", "-b", branch], check=True)

    lines = INDEX_CSV.read_text().splitlines()
    lines.append(new_row)
    INDEX_CSV.write_text("\n".join(lines) + "\n")

    commit_name = os.environ.get("GIT_COMMITTER_NAME", "SlashIndex Bot")
    commit_email = os.environ.get("GIT_COMMITTER_EMAIL", "bot@slashindex.fyi")
    gh_user = os.environ.get("GH_USER", "")

    subprocess.run(["git", "add", "index.csv"], check=True)
    commit_env = {**os.environ, "GIT_COMMITTER_NAME": commit_name, "GIT_COMMITTER_EMAIL": commit_email}
    subprocess.run([
        "git", "commit",
        "--author", f"{commit_name} <{commit_email}>",
        "-m", f"Add {domain} to SlashIndex.fyi",
    ], check=True, env=commit_env)

    if not os.environ.get("CI") and gh_user:
        subprocess.run(["gh", "auth", "switch", "--user", gh_user], check=True)
    subprocess.run(["git", "push", "-u", "origin", branch, "--force"], check=True)


    pr_cmd = [
        "gh", "pr", "create",
        "--repo", REPO,
        "--title", f"Add {domain} to SlashIndex.fyi",
        "--body", f"Add {domain} to index.\n\nauthor: {author}\nlocation: {city}, {state}, {country}" +
                  (f"\n\ncc @{github_username}" if github_username else "") +
                  "\n\n---\n_Raised by AI. Feel free to update if any information is incorrect._",
    ]

    # check for existing open PR on this branch
    existing_pr = subprocess.run(
        ["gh", "pr", "view", branch, "--repo", REPO, "--json", "url", "--jq", ".url"],
        capture_output=True, text=True,
    )
    if existing_pr.returncode == 0 and existing_pr.stdout.strip():
        pr_url = existing_pr.stdout.strip()
        body = (f"Add {domain} to index.\n\nauthor: {author}\nlocation: {city}, {state}, {country}" +
                (f"\n\ncc @{github_username}" if github_username else "") +
                "\n\n---\n_Raised by AI. Feel free to update if any information is incorrect._")
        subprocess.run(
            ["gh", "pr", "edit", pr_url, "--repo", REPO, "--body", body],
            check=True,
        )
        print(f"PR updated: {pr_url}")
    else:
        result = subprocess.run(pr_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"PR created: {result.stdout.strip()}")
        else:
            print(f"PR creation failed: {result.stderr.strip()}")

    subprocess.run(["git", "checkout", "master"], check=True)


def _resolve_gh(value: str) -> str:
    """Return GitHub username from a username, profile URL, or PR URL/number."""
    import json, re as _re
    value = value.strip()
    # PR number
    if value.isdigit():
        data = json.loads(subprocess.run(
            ["gh", "pr", "view", value, "--json", "author"],
            check=True, capture_output=True, text=True,
        ).stdout)
        return data["author"]["login"]
    # PR URL: https://github.com/*/pull/N
    m = _re.search(r"github\.com/[^/]+/[^/]+/pull/(\d+)", value)
    if m:
        data = json.loads(subprocess.run(
            ["gh", "pr", "view", m.group(1), "--json", "author"],
            check=True, capture_output=True, text=True,
        ).stdout)
        return data["author"]["login"]
    # Profile URL: https://github.com/username
    m = _re.match(r"https?://github\.com/([^/]+)/?$", value)
    if m:
        return m.group(1)
    # Plain username
    return value


def github_profile_location(username: str) -> str:
    """Return raw `location` field from GitHub profile, empty if unset/unavailable."""
    try:
        resp = subprocess.run(
            ["gh", "api", f"users/{username}", "--jq", ".location"],
            capture_output=True, text=True, timeout=10,
        )
        if resp.returncode == 0:
            return resp.stdout.strip()
    except Exception:
        pass
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain")
    parser.add_argument("--llm", action="store_true", help="Use LLM for extraction instead of heuristics")
    parser.add_argument("--llm-url", default="https://api.anthropic.com", help="LLM base URL (OpenAI-compatible or Anthropic)")
    parser.add_argument("--llm-model", default="claude-haiku-4-5-20251001", help="Model name")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Print extracted info, skip PR creation")
    parser.add_argument("--gh", metavar="USER_OR_URL", help="GitHub username, profile URL, or PR URL/number to use for @mention")
    parser.add_argument("--city", help="Override city")
    parser.add_argument("--state", help="Override state/province")
    parser.add_argument("--country", help="Override country (with flag emoji, e.g. '🇮🇳 IN')")
    args = parser.parse_args()

    domain = args.domain.strip().removeprefix("http://").removeprefix("https://").rstrip("/")

    existing = [l for l in INDEX_CSV.read_text().splitlines() if l.startswith(domain + ",")]
    if existing:
        print(f"ERROR: {domain} already in index.csv. Skipping.")
        sys.exit(0)

    print(f"Scraping {domain}...")

    pages = scrape_domain(domain)
    if not pages:
        print("ERROR: Could not fetch any pages.")
        sys.exit(1)

    print(f"Fetched {len(pages)} pages: {list(pages)}")

    if args.llm:
        print(f"Extracting via LLM ({args.llm_model})...")
        info = llm_extract(domain, pages, args.llm_url, args.llm_model)
    else:
        print("Extracting via heuristics...")
        info = heuristic_extract(domain, pages)

    print(f"Extracted: {info}")

    github_username = info.get("github_username") or None
    if args.gh:
        github_username = _resolve_gh(args.gh)
    if github_username:
        print(f"GitHub: {github_username}")

    if args.city:
        info["city"] = args.city
    elif not info.get("city") and github_username:
        loc = github_profile_location(github_username)
        if loc:
            city = loc.split(",")[0].strip()
            if city:
                info["city"] = city
                print(f"GitHub profile location: {loc}")

    if info.get("city") and (not args.state or not args.country):
        geo = geocode_city(info["city"])
        if not args.state and not info.get("state") and geo.get("state"):
            info["state"] = geo["state"]
        if not args.country and not info.get("country") and geo.get("country"):
            info["country"] = geo["country"]

    if args.state:
        info["state"] = args.state
    if args.country:
        info["country"] = args.country

    print("Checking slash pages...")
    slash_pages = get_slash_pages(domain)
    print(f"Pages found: {slash_pages}")

    if args.dry_run:
        print(f"Dry run — would add row: {domain},{info.get('author','')},{info.get('country','')},{info.get('state','')},{info.get('city','')},topics={info.get('topics',[])},pages={slash_pages}")
        return

    print("Creating PR...")
    create_pr(domain, info, slash_pages, github_username)


if __name__ == "__main__":
    main()
