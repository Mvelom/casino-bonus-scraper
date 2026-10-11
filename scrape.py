#!/usr/bin/env python3
"""Scrape three casino welcome offers from one public comparison page.

The script checks robots.txt, fetches one AskGamblers page, then asks Claude to
turn the three selected offers' free-text terms into structured JSON.
Run: python scrape.py
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import anthropic
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError

ROOT = Path(__file__).parent
CONFIG_FILE = ROOT / "sources.json"
OUT_FILE = ROOT / "data" / "bonuses.json"
MAX_CHARS = 14_000
BLOCK_MARKERS = ("captcha", "verify you are human", "access denied", "are you a robot", "checking your browser")


class Blocked(Exception):
    """The source cannot be fetched without breaking the task rules."""


class Bonus(BaseModel):
    casino: str
    welcome_bonus: Optional[str] = None
    wagering_multiplier: Optional[float] = None
    min_deposit: Optional[str] = None


def user_agent() -> str:
    contact = os.environ.get("SCRAPER_CONTACT")
    if not contact:
        raise ValueError("Set SCRAPER_CONTACT to an email address before scraping.")
    return f"BonusScreeningBot/1.0 (screening task; contact: {contact})"


def allowed_by_robots(url: str, headers: dict) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = requests.get(robots_url, headers=headers, timeout=15)
    except requests.RequestException:
        return False
    if response.status_code in (404, 410):
        return True
    if response.status_code >= 400:
        return False
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser.can_fetch(headers["User-Agent"], url)


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "svg", "form"]):
        tag.decompose()
    return re.sub(r"\n{2,}", "\n", soup.get_text("\n", strip=True))


def fetch_text(url: str, headers: dict) -> str:
    if not allowed_by_robots(url, headers):
        raise Blocked("robots.txt disallows this URL, or could not be checked")
    response = requests.get(url, headers=headers, timeout=25)
    if response.status_code >= 400:
        raise Blocked(f"HTTP {response.status_code}")
    text = visible_text(response.text)
    if any(marker in text.lower() for marker in BLOCK_MARKERS):
        raise Blocked("page looks like a CAPTCHA or bot check")
    if len(text) < 500:
        raise Blocked("page has too little readable text (likely JavaScript-only)")
    return text


def offer_context(page_text: str, names: list[str]) -> str:
    """Return a small, auditable slice around each requested casino's offer."""
    lines = page_text.splitlines()
    chunks = []
    for name in names:
        try:
            index = next(i for i, line in enumerate(lines) if line.strip().casefold() == name.casefold())
        except StopIteration as error:
            raise ValueError(f"{name!r} was not found on the source page") from error
        chunks.append("\n".join(lines[index:index + 18]))
    return "\n\n--- NEXT CASINO ---\n\n".join(chunks)[:MAX_CHARS]


def extract_with_llm(client: anthropic.Anthropic, names: list[str], context: str) -> list[Bonus]:
    prompt = """Extract the selected casino welcome offers from the source text below.
Return ONLY a JSON array of exactly three objects, in this same order and using
the supplied casino names exactly. Every object must have exactly these keys:
casino, welcome_bonus, wagering_multiplier, min_deposit.

welcome_bonus is the offer headline as written. wagering_multiplier is the
number before x in the wagering requirement (for example, 40 for 40xb).
min_deposit includes the displayed amount and currency. Use null if a field is
not stated. Do not infer, calculate, or add prose.

Selected casinos: """ + ", ".join(names) + "\n\nSource text:\n" + context
    message = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5"),
        max_tokens=800,
        system="You are a precise data extraction service. Use only the provided text.",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = "".join(block.text for block in message.content if block.type == "text").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    records = [Bonus(**item) for item in json.loads(raw)]
    if [record.casino for record in records] != names:
        raise ValueError("The model did not return the three requested casinos in order")
    return records


def numbers(value: str) -> set[str]:
    value = re.sub(r"(?<=\d)[,\s](?=\d{3}\b)", "", value)
    return set(re.findall(r"\d+(?:\.\d+)?", value))


def grounded(record: Bonus, context: str) -> bool:
    values = " ".join(filter(None, [record.welcome_bonus, record.min_deposit,
                                     f"{record.wagering_multiplier:g}" if record.wagering_multiplier is not None else None]))
    return numbers(values) <= numbers(context)


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY first.", file=sys.stderr)
        return 2
    try:
        headers = {"User-Agent": user_agent(), "Accept-Language": "en"}
        config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        source_url = config["url"]
        names = config["casinos"]
        if len(names) != 3 or len(set(names)) != 3:
            raise ValueError("sources.json must name exactly three distinct casinos")
        page_text = fetch_text(source_url, headers)
        context = offer_context(page_text, names)
        records = extract_with_llm(anthropic.Anthropic(), names, context)
    except (ValueError, KeyError, requests.RequestException, json.JSONDecodeError,
            ValidationError, anthropic.APIError, Blocked) as error:
        print(f"Scrape failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "generated_at": now,
        "source": config["source_name"],
        "model": os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5"),
        "casinos": [{**record.model_dump(), "source_url": source_url,
                      "scraped_at": now, "needs_review": not grounded(record, context)}
                     for record in records],
    }
    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_FILE} ({len(records)} casinos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
