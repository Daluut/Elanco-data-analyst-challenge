# Elanco Data Analyst Interview Challenge 2026

**Daluut Warsame**

This folder contains both parts of the challenge:

- **Setup and Foundations (points 6–9):** the answers are in `presentation/Setup_and_Foundations_Databricks.pdf`. The Databricks notebook and results are in `part1_databricks/`.
- **Website Data Challenge:** everything else in this folder, described below.

## Website Data Challenge

Turns the raw synthetic analytics export into cleaned, checked, analysis-ready tables, a daily summary, breakdowns and a short findings report.

## Data

The raw data files (`sessions.csv`, `events.csv`, `pages.csv`, `campaigns.csv` and the data dictionary) were supplied by Elanco for the challenge and are **not included** in this repository. To run the pipeline, place them in `data/raw/`. The row-level cleaned tables are also left out; the aggregated metrics, quality checks, charts and reports are included.

## How to run

Requirements: Python 3.10+ with `pandas` and `matplotlib` (`pip install pandas matplotlib`).

```bash
python src/pipeline.py    # raw CSVs -> clean tables, quality checks, metrics  (~2 s)
python src/analysis.py    # metrics -> charts + investigation tables           (~5 s)
```

Both scripts rebuild everything from `data/raw/` on every run, so rerunning is safe. `pipeline.py` exits with an error if any hard data-quality check fails.

## Folder layout

```
data/raw/                   supplied files (not included), never modified
src/pipeline.py             cleaning, checks, daily summary, breakdowns
src/analysis.py             investigation tables and charts
output/clean/               sessions_clean, events_clean, session_flags (one row per session)
output/quality/             dq_checks, cleaning_log, quarantined rows
output/metrics/             daily_summary, breakdown_channel / device / month_* / role, intent_funnel
output/metrics/investigations/  tables behind each finding
reports/findings.md         findings report (start here)
reports/quality_assumptions.md  checks, cleaning decisions, exclusions, pipeline design
reports/charts/             PNG charts used in the report
```

## Notes

- Tools: Python, pandas, matplotlib. The same logic can run in a Databricks notebook by uploading `data/raw/` to a Volume and pointing `RAW` at it.
- AI assistance: Claude (Anthropic) helped with profiling, code drafting and report structure. All outputs were rerun and checked.
- Approximate time spent: a few hours in total, spread over three days (Databricks setup and Part 1 queries, then running, reviewing and making sure I understood the Part 2 work).
