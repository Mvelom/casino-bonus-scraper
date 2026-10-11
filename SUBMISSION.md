# Submission notes

## Live page

Publish this repository with GitHub Pages (see `README.md`) and paste the live
URL here before sending the task:

https://mvelom.github.io/casino-bonus-scraper/

## Written part: production plan for 200 casinos, updated daily

**Where it runs.** One small EU VPS (Hetzner CX22-class, 2 vCPU / 4 GB, about EUR 5/month) running
Docker Compose: Postgres, a scraper job container, and Caddy. 200 pages a day is a few minutes of
work, so a single VM is cheaper and simpler than ECS or Lambda, and I can rebuild it from the compose
file in under an hour if it dies. I would add Playwright to the scraper image only for sources that
need JavaScript.

**Database and backups.** PostgreSQL 16 on a persistent volume. Tables: `casinos` and
`bonus_snapshots` (casino, scraped_at, the four fields, hash of the source text, needs_review), so
changes are kept as history and the LLM only re-runs when the page hash changes. Nightly `pg_dump`
to Backblaze B2 (30 daily + 12 monthly kept), a weekly provider snapshot, and a monthly restore test
into a scratch container so I know the backups actually work.

**Domain, DNS, HTTPS.** Domain at Cloudflare Registrar, DNS on Cloudflare (free). A/AAAA records to
the VPS. Caddy gets and renews Let's Encrypt certificates automatically. Firewall open on 80/443
only, SSH by key only.

**Scheduling and failure alerts.** A systemd timer runs `docker compose run scraper` at 03:00 daily
(4 workers, 2 s delay per domain, robots.txt respected). Each run pings Healthchecks.io on start,
success and failure, and it emails/Slacks me if no success arrives within 26 hours. The job also fails
loudly if more than 5% of casinos fail or if results look implausible (for example, bonuses
disappearing at many casinos at once, which usually means a layout change). Failed casinos keep
yesterday's data and show as stale after 48 hours. Sentry (free tier) catches exceptions, and
UptimeRobot watches the site.

**Rough monthly cost.** VPS about EUR 5, backup storage about EUR 1-3, domain about USD 1,
Cloudflare/Healthchecks/Sentry/UptimeRobot free. LLM: roughly 200 pages x 4k tokens x 30 days is about
24M input tokens, which is a few dollars on a small model and less with the hash check.
Total: about USD 15-30 per month.

---

# Five lines on AI
1. I used Codex to help draft the scraper, page, README and production plan; the scraper uses Claude's API for structured extraction.
2. I reviewed the output schema, source configuration and mobile page manually.
3. The first draft was structured around one casino page per row, which did not meet the brief's “one public source” requirement.
4. I caught that by rereading the brief and changed the scraper to pull all three offers from one AskGamblers page.
5. Before submission, I would run it with my API key and compare each generated field against the source page because offers change frequently.

# Time taken

Not independently measured in this workspace. Replace this with your actual elapsed time before submitting.

# What is missing / unfinished

- The checked-in JSON is a preview fixture, not a live run: this environment has no `ANTHROPIC_API_KEY` and cannot make the required external HTTP request. Run `python scrape.py` locally with the two documented environment variables to replace it.
- The page has not been published. Enable GitHub Pages and paste the resulting URL above.
