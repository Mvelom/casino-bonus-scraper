# Casino bonus scraper

This project collects three welcome offers from **one public comparison page**,
uses Claude to turn each offer's free-text terms into structured fields, writes
`data/bonuses.json`, and displays that JSON in a phone-friendly web page.

## Source and fields

The configured source is AskGamblers' public [Casino Welcome Bonuses page](https://www.askgamblers.com/casino-bonuses/welcome).
The scraper selects BangaWin Casino, Winoly Casino, and Rokubet Casino from that
single page. Each output row has `welcome_bonus`, `wagering_multiplier`,
`min_deposit`, and `source_url`, plus the casino name, timestamp, and a
`needs_review` guard.

## Install

Requires Python 3.9+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configure and run

Set an Anthropic key and a contact address for the polite User-Agent, then run
the scraper with one command:

```powershell
$env:ANTHROPIC_API_KEY = "your-key"
$env:SCRAPER_CONTACT = "your-email@example.com"
python scrape.py
```

The script exits non-zero on a blocked source, an invalid model response, or a
missing casino. That makes failures visible to a scheduler. The checked-in JSON
is a clearly labelled preview so the page can be viewed before the first live
run; replace it by running the command above before submitting.

## View locally

```powershell
python -m http.server 8000
```

Open `http://localhost:8000`. The page reads `data/bonuses.json` at runtime;
it does not duplicate the offer data in HTML.

## Responsible scraping choices

- The scraper reads `robots.txt` before fetching. If it cannot verify permission
  or the URL is disallowed, it stops rather than attempting a workaround.
- It does not use a browser automation bypass, login, CAPTCHA solver, or retry
  strategy for bot blocks.
- The model receives only short text slices around the three named offers.
- Pydantic validates the model response. A row is marked `needs_review` when a
  number returned by the model does not appear in its source-text slice.

## Publish

For GitHub Pages, commit `index.html` and `data/bonuses.json`, then enable
**Settings -> Pages -> Deploy from a branch**, choosing `main` and `/ (root)`.
After deployment, add that public URL to `SUBMISSION.md`.

## Limits

Offers vary by location and can change. The output is a snapshot, not advice or
a recommendation to gamble. The page deliberately does not try to work around
JavaScript-only or protected sources. This version has no automated tests; the
submission checklist includes the manual checks performed.
