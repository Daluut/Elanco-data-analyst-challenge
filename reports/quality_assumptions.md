# Quality and assumptions note

*Daluut Warsame*

## Output grain

| Output | Grain (one row per…) | Notes |
|---|---|---|
| `output/clean/sessions_clean.csv` | session | Original URL kept; `landing_page_path`, `channel`, `is_suspected_bot` added |
| `output/clean/events_clean.csv` | event | Page catalogue + session date joined (many-to-one, validated) |
| `output/clean/session_flags.csv` | session | Events aggregated to session level *before* joining, so session counts cannot be multiplied |
| `output/metrics/daily_summary.csv` | UTC session-start date | All 181 days present (zero-filled). Events count on their session's date |
| `output/metrics/breakdown_*.csv` | channel / device / month×channel / month×device / role | Role table is **not additive**: a session can view several roles |

## Cleaning decisions and excluded-record counts

| Table | Issue | Rows | Decision |
|---|---|---|---|
| sessions | Exact duplicate rows | 30 | Dropped (kept first) |
| sessions | Device case/whitespace (`Mobile`, `" DESKTOP "`) | 60 | Trimmed + lower-cased |
| sessions | Missing country | 90 | Kept as `Unknown` |
| sessions | Blank source/medium **with** a campaign_id | 9 | Filled from `campaigns.csv`, flagged `source_medium_imputed` |
| sessions | Blank source/medium, no campaign | 36 | Kept, channel `Unknown` |
| sessions | Suspected bot (`traffic-check.example`) | 1,350 | **Kept but flagged**; excluded from eligible metrics |
| events | Exact duplicate rows | 120 | Dropped (kept first) |
| events | Orphans: session_id not in sessions (`MISSING…`) | 12 | **Quarantined** (`output/quality/quarantine_events.csv`) |
| events | Timestamp `not-a-timestamp` | 8 | Kept (still counted via session date), excluded from sequence logic |
| events | Negative engagement seconds | 10 | Set to null; event kept |
| both | URL variants: trailing `/`, `?ref=…`, `#fragment` | 4,650+ events, 2,500+ landing URLs | Normalised to canonical path; original URL kept |

Raw files in `data/raw/` are never modified. Row counts reconcile: raw = clean + duplicates dropped + quarantined (checked automatically).

**Why flag the bots rather than delete them?** The decision is a judgement. Keeping the rows lets anyone reverse it, and the daily summary shows both `tracked_sessions_all` and `eligible_sessions`.

**Why fill 9 source values from the campaign table?** The session carries an explicit campaign_id, and each campaign has exactly one documented source/medium. I did **not** infer campaigns from dates, as the data dictionary warns against that.

## Checks performed (`output/quality/dq_checks.csv`)

All hard checks PASS: primary-key uniqueness (all four tables), valid ISO-8601 timestamps, referential integrity (event→session, campaign_id→campaigns), allowed event names, non-page events have 0 seconds, every session has ≥1 page view, events fall within 30 minutes of session start and on the same UTC date, email clicks only on `/application`, and raw-to-clean reconciliation.

Warnings (kept, reported): 3 sessions whose landing page differs from the first recorded event page. The pipeline exits with an error if any hard check fails.

## Key definitions

- **Eligible session**: a tracked session not flagged as suspected bot.
- **Application-email click rate** = distinct eligible sessions with ≥1 `application_email_click` ÷ eligible sessions, by session-start date.
- **Application-intent journey**: population-based, **not** strictly ordered. Stage 1 is an eligible session; stage 2 is a session that viewed `/application` by any route (Apply Now click *or* direct landing: 1,107 sessions landed straight on `/application`); stage 3 is a session that clicked Send Email. Order is not required because a direct landing can skip Apply Now (290 email-click sessions never clicked Apply Now) and because 8 events lack valid timestamps. A check confirmed every email-click session also viewed `/application`.
- **Data Analyst interest**: no Data Analyst page exists, so Technical Analyst viewers are used as an explicitly labelled proxy.

## Proposed daily pipeline

1. **Incremental load.** Each day, land the new export files in a dated raw folder (`raw/date=YYYY-MM-DD/`), never overwriting. In Databricks this would be Auto Loader into a bronze Delta table.
2. **Safe reruns (idempotent).** Clean into silver tables using `MERGE` on `session_id` / `event_id`, then rebuild only the affected dates in the gold daily summary (`replace where date in …`). Running the same day twice gives the same result.
3. **Late or corrected data.** Reprocess a rolling window (e.g. last 7 days) on every run, so late events and corrected rows update their session's date. A correction to an older date triggers a targeted backfill of that date.
4. **Quality monitoring.** Run the checks in `dq_checks.csv` on every load. Hard failures (duplicate keys, orphans above a threshold, reconciliation mismatch) stop publication. Soft alerts flag a single source above X% of daily traffic, a zero count for any event type on a device, or a day-on-day swing above 3× normal. Either of the last two would have caught both anomalies in this dataset on day one.
5. **Orchestration.** A scheduled Databricks Job (or cron + Python) runs bronze → silver → gold → checks, logs row counts per step, and alerts the owner on failure.
