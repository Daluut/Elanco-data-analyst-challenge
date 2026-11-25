"""
Elanco Students website data challenge - cleaning + metrics pipeline.

Reads the raw CSVs in data/raw (never modified), writes:
  output/clean/     cleaned, analysis-ready tables (one row per session / per event)
  output/quality/   data-quality check results, cleaning log, quarantined rows
  output/metrics/   daily summary and breakdowns

Run from the project folder:   python src/pipeline.py
Every run rebuilds all outputs from the raw files, so rerunning is safe (idempotent).
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "output"

PERIOD_START, PERIOD_END = "2025-09-01", "2026-02-28"   # inclusive, from the data dictionary
TS_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"   # ISO 8601 UTC ending in Z

# Sources treated as non-human traffic. Evidence (see reports/quality_assumptions.md):
# 1,353 sessions in 3 days, 100% desktop, 100% US/SG, every session a new visitor,
# all landing on the home page, spread evenly across all 24 hours.
SUSPECTED_BOT_SOURCES = {"traffic-check.example"}

CHANNEL_MAP = {"organic": "Organic Search", "social": "Social", "email": "Email",
               "referral": "Referral", "(none)": "Direct"}

log = []      # cleaning log: (table, step, rows_affected, action)
checks = []   # data-quality checks: (table, check, failures, status, note)


def note(table, step, n, action):
    log.append({"table": table, "step": step, "rows_affected": int(n), "action": action})


def check(table, name, failures, note_="", warn_only=False):
    status = "PASS" if failures == 0 else ("WARN" if warn_only else "FAIL")
    checks.append({"table": table, "check": name, "failures": int(failures), "status": status, "note": note_})


def url_to_path(url: pd.Series) -> pd.Series:
    """Normalise a URL to a canonical page path: drop host, query string, fragment, trailing slash."""
    p = (url.str.strip()
            .str.replace(r"^https?://[^/]+", "", regex=True)
            .str.split(r"[?#]", regex=True).str[0]
            .str.rstrip("/"))
    return p.mask(p == "", "/")


def read_raw(name):
    # Read everything as text and keep blanks as "" so nothing is silently converted.
    return pd.read_csv(RAW / name, dtype=str, keep_default_na=False)


# --------------------------------------------------------------------------- sessions
def clean_sessions(raw: pd.DataFrame, campaigns: pd.DataFrame):
    s = raw.copy()
    note("sessions", "raw rows", len(s), "read")

    # 1. Duplicates: exact duplicate rows are dropped. Same id with different content would be quarantined.
    n = s.duplicated().sum()
    s = s.drop_duplicates()
    note("sessions", "exact duplicate rows", n, "dropped (kept first copy)")
    conflict = s[s.session_id.duplicated(keep=False)]
    note("sessions", "same session_id, conflicting content", len(conflict), "quarantined")
    s = s[~s.session_id.isin(conflict.session_id)]

    # 2. Timestamps
    valid_fmt = s.session_start_utc.str.match(TS_PATTERN)
    s["session_start_ts"] = pd.to_datetime(s.session_start_utc.where(valid_fmt), utc=True, errors="coerce")
    bad_ts = s.session_start_ts.isna()
    out_of_range = ~bad_ts & ~s.session_start_ts.dt.strftime("%Y-%m-%d").between(PERIOD_START, PERIOD_END)
    quarantine = pd.concat([conflict.assign(reason="conflicting duplicate session_id"),
                            s[bad_ts].assign(reason="invalid session_start_utc"),
                            s[out_of_range].assign(reason="session outside reporting period")])
    note("sessions", "invalid or out-of-period start time", (bad_ts | out_of_range).sum(), "quarantined")
    s = s[~bad_ts & ~out_of_range].copy()
    s["session_date"] = s.session_start_ts.dt.strftime("%Y-%m-%d")   # daily grain = UTC session-start date

    # 3. Categorical tidy-up
    dev_raw = s.device_category
    s["device_category"] = dev_raw.str.strip().str.lower()
    note("sessions", "device_category case/whitespace fixed", (dev_raw != s.device_category).sum(),
         "trimmed + lower-cased (e.g. ' DESKTOP ' -> 'desktop')")
    bad_dev = ~s.device_category.isin(["desktop", "mobile", "tablet"])
    s.loc[bad_dev, "device_category"] = "unknown"
    note("sessions", "device_category not desktop/mobile/tablet", bad_dev.sum(), "set to 'unknown'")

    s["country_code"] = s.country_code.str.strip().str.upper()
    n = (s.country_code == "").sum()
    s["country_code"] = s.country_code.replace("", "Unknown")
    note("sessions", "missing country_code", n, "labelled 'Unknown' (kept)")

    # 4. Source / medium: blanks are filled ONLY when the session carries an explicit campaign_id,
    #    using that campaign's documented source/medium. Otherwise they stay Unknown.
    for c in ["source", "medium", "campaign_id"]:
        s[c] = s[c].str.strip()
    s["source_medium_imputed"] = False
    cmp = campaigns.set_index("campaign_id")
    fill = (s.source == "") & (s.campaign_id != "") & s.campaign_id.isin(cmp.index)
    s.loc[fill, "source"] = s.loc[fill, "campaign_id"].map(cmp.source)
    s.loc[fill, "medium"] = s.loc[fill, "campaign_id"].map(cmp.medium)
    s.loc[fill, "source_medium_imputed"] = True
    note("sessions", "blank source/medium with a campaign_id", fill.sum(), "filled from campaigns.csv, flagged")
    n = (s.source == "").sum()
    s["source"] = s.source.replace("", "(unknown)")
    s["medium"] = s.medium.replace("", "(unknown)")
    note("sessions", "blank source/medium, no campaign", n, "kept, channel = 'Unknown'")

    s["channel"] = s.medium.map(CHANNEL_MAP).fillna("Unknown")
    s.loc[(s.source == "(direct)") & (s.medium == "(none)"), "channel"] = "Direct"

    unknown_cmp = (s.campaign_id != "") & ~s.campaign_id.isin(cmp.index)
    note("sessions", "campaign_id not in campaigns.csv", unknown_cmp.sum(), "kept, flagged by check")
    s["campaign_id"] = s.campaign_id.replace("", pd.NA)

    # 5. Landing page: keep original URL for traceability, add normalised path
    s["landing_page_path"] = url_to_path(s.landing_page_url)

    # 6. Suspected bot traffic: flagged, not deleted; excluded from the 'eligible' population
    s["is_suspected_bot"] = s.source.isin(SUSPECTED_BOT_SOURCES)
    note("sessions", "suspected bot sessions (traffic-check.example)", s.is_suspected_bot.sum(),
         "kept but flagged; excluded from eligible-session metrics")

    return s, quarantine


# --------------------------------------------------------------------------- events
def clean_events(raw: pd.DataFrame, sessions: pd.DataFrame, pages: pd.DataFrame):
    e = raw.copy()
    note("events", "raw rows", len(e), "read")

    n = e.duplicated().sum()
    e = e.drop_duplicates()
    note("events", "exact duplicate rows", n, "dropped (kept first copy)")
    conflict = e[e.event_id.duplicated(keep=False)]
    e = e[~e.event_id.isin(conflict.event_id)]
    note("events", "same event_id, conflicting content", len(conflict), "quarantined")

    # Orphans: events whose session is not in the cleaned sessions table cannot be attributed.
    orphan = ~e.session_id.isin(sessions.session_id)
    quarantine = pd.concat([conflict.assign(reason="conflicting duplicate event_id"),
                            e[orphan].assign(reason="session_id not found in sessions")])
    note("events", "orphan events (no matching session)", orphan.sum(), "quarantined")
    e = e[~orphan].copy()

    # Timestamps: an invalid event timestamp does not mean the event did not happen.
    # Keep the row (it still counts toward its session), flag it, exclude it from ordered-sequence logic.
    valid_fmt = e.event_timestamp_utc.str.match(TS_PATTERN)
    e["event_ts"] = pd.to_datetime(e.event_timestamp_utc.where(valid_fmt), utc=True, errors="coerce")
    e["event_ts_valid"] = e.event_ts.notna()
    note("events", "invalid event_timestamp_utc", (~e.event_ts_valid).sum(),
         "kept (counted via session date), flagged, excluded from sequence analysis")

    # Engagement seconds: must be a non-negative integer.
    secs = pd.to_numeric(e.engagement_seconds, errors="coerce")
    bad = secs.isna() | (secs < 0)
    note("events", "negative / non-numeric engagement_seconds", bad.sum(), "set to null (event kept)")
    e["engagement_seconds"] = secs.mask(bad).astype("Int64")

    e["event_name"] = e.event_name.str.strip().str.lower()

    # Page path normalisation + join to catalogue (left join: unknown paths are kept, not rewritten)
    e["page_path"] = url_to_path(e.page_url)
    e = e.merge(pages, on="page_path", how="left", validate="many_to_one")
    unknown = e.page_title.isna()
    note("events", "page_path not in pages.csv", unknown.sum(), "kept, page_group = 'unknown'")
    e["page_group"] = e.page_group.fillna("unknown")
    e["placement_role"] = e.placement_role.replace("", pd.NA)

    # Bring session context onto each event (many-to-one join cannot multiply sessions)
    e = e.merge(sessions[["session_id", "session_date", "session_start_ts", "is_suspected_bot"]],
                on="session_id", how="left", validate="many_to_one")
    return e, quarantine


# --------------------------------------------------------------------------- checks
def run_checks(raw_s, raw_e, s, e, pages, campaigns):
    check("sessions", "session_id unique in clean table", s.session_id.duplicated().sum())
    check("events", "event_id unique in clean table", e.event_id.duplicated().sum())
    check("pages", "page_path unique", pages.page_path.duplicated().sum())
    check("campaigns", "campaign_id unique", campaigns.campaign_id.duplicated().sum())
    check("sessions", "session_start_utc valid ISO-8601 UTC", s.session_start_ts.isna().sum())
    check("events", "every event joins to a session (referential integrity)", e.session_date.isna().sum())
    check("events", "event_name in allowed set",
          (~e.event_name.isin(["page_view", "apply_cta_click", "application_email_click", "video_play"])).sum())
    check("events", "non-page_view events have 0 engagement seconds",
          ((e.event_name != "page_view") & (e.engagement_seconds.fillna(0) != 0)).sum())
    check("events", "engagement_seconds non-negative (after cleaning)", (e.engagement_seconds < 0).sum())
    pv = e[e.event_name == "page_view"].groupby("session_id").size()
    check("sessions", "every session has >= 1 page view", (~s.session_id.isin(pv.index)).sum())

    ev = e[e.event_ts_valid]
    off = (ev.event_ts - ev.session_start_ts).dt.total_seconds()
    check("events", "event not before its session start", (off < 0).sum())
    check("events", "event within 30 minutes of session start", (off >= 1800).sum())
    check("events", "event on same UTC date as session start",
          (ev.event_ts.dt.strftime("%Y-%m-%d") != ev.session_date).sum())
    check("events", "application_email_click recorded on /application",
          ((e.event_name == "application_email_click") & (e.page_path != "/application")).sum())
    check("events", "all page paths found in pages.csv", (e.page_group == "unknown").sum(), warn_only=True)

    first = ev.sort_values(["session_id", "event_ts", "event_id"]).groupby("session_id").page_path.first()
    lp = s.set_index("session_id").landing_page_path
    mism = (first != lp.reindex(first.index)).sum()
    check("sessions", "landing page matches first recorded event page", mism,
          "kept; small number, may be tracking order or untracked first hit", warn_only=True)
    check("sessions", "campaign_id exists in campaigns.csv",
          (s.campaign_id.notna() & ~s.campaign_id.isin(campaigns.campaign_id)).sum())
    c = s.dropna(subset=["campaign_id"]).merge(campaigns[["campaign_id", "start_date", "end_date"]], on="campaign_id")
    check("sessions", "campaign sessions within campaign window",
          ((c.session_date < c.start_date) | (c.session_date > c.end_date)).sum(),
          "outside-window sessions are allowed (reused links)", warn_only=True)

    # Reconciliation: raw rows = clean rows + duplicates removed + quarantined
    rs, re = len(raw_s), len(raw_e)
    check("sessions", f"reconciliation raw {rs} = clean + dropped + quarantined",
          rs - (len(s) + raw_s.duplicated().sum() + pd.read_csv(OUT / 'quality' / 'quarantine_sessions.csv').shape[0]))
    check("events", f"reconciliation raw {re} = clean + dropped + quarantined",
          re - (len(e) + raw_e.duplicated().sum() + pd.read_csv(OUT / 'quality' / 'quarantine_events.csv').shape[0]))


# --------------------------------------------------------------------------- metrics
def session_flags(s, e):
    """One row per session with boolean flags. Built by aggregating events to session grain FIRST,
    then joining 1:1 to sessions, so session counts can never be multiplied by events."""
    def has(df, mask):
        return df.loc[mask, "session_id"].unique()

    f = s[["session_id", "visitor_id", "session_date", "session_start_ts", "device_category", "country_code",
           "channel", "source", "medium", "campaign_id", "landing_page_path", "is_suspected_bot"]].copy()
    pv = e[e.event_name == "page_view"]
    f = f.merge(pv.groupby("session_id").agg(page_views=("event_id", "size"),
                                             engaged_seconds=("engagement_seconds", "sum")),
                on="session_id", how="left", validate="one_to_one")
    f["page_views"] = f.page_views.fillna(0).astype(int)
    f["viewed_role_page"] = f.session_id.isin(has(pv, pv.page_group == "role"))
    f["viewed_application"] = f.session_id.isin(has(pv, pv.page_path == "/application"))
    f["landed_on_application"] = f.landing_page_path == "/application"
    f["apply_cta_click"] = f.session_id.isin(has(e, e.event_name == "apply_cta_click"))
    f["email_click"] = f.session_id.isin(has(e, e.event_name == "application_email_click"))
    f["video_play"] = f.session_id.isin(has(e, e.event_name == "video_play"))
    for role in sorted(pv.placement_role.dropna().unique()):
        col = "viewed_role_" + role.lower().replace(" ", "_")
        f[col] = f.session_id.isin(has(pv, (pv.page_group == "role") & (pv.placement_role == role)))
    f["is_eligible"] = ~f.is_suspected_bot
    return f


def rate(num, den):
    return (num / den).where(den > 0).round(4)


def build_metrics(f, e):
    m = OUT / "metrics"
    elig = f[f.is_eligible]
    pv = e[(e.event_name == "page_view")]

    # ---- daily summary (grain: one row per UTC session-start date)
    days = pd.DataFrame({"date": pd.date_range(PERIOD_START, PERIOD_END).strftime("%Y-%m-%d")})
    d = (f.groupby("session_date").agg(tracked_sessions_all=("session_id", "size"),
                                       suspected_bot_sessions=("is_suspected_bot", "sum"))
         .join(elig.groupby("session_date").agg(
             eligible_sessions=("session_id", "size"),
             page_views=("page_views", "sum"),
             sessions_with_apply_cta_click=("apply_cta_click", "sum"),
             sessions_viewing_application=("viewed_application", "sum"),
             sessions_with_application_email_click=("email_click", "sum"))))
    d = days.merge(d, left_on="date", right_index=True, how="left").fillna(0)
    num_cols = d.columns.drop("date")
    d[num_cols] = d[num_cols].astype(int)
    d["page_views_all_incl_bots"] = d.date.map(pv.groupby("session_date").size()).fillna(0).astype(int)
    d["application_email_click_rate"] = rate(d.sessions_with_application_email_click, d.eligible_sessions)
    d["apply_cta_click_rate"] = rate(d.sessions_with_apply_cta_click, d.eligible_sessions)
    d["email_clicks_per_application_viewer"] = rate(d.sessions_with_application_email_click,
                                                    d.sessions_viewing_application)
    d.to_csv(m / "daily_summary.csv", index=False)

    # ---- breakdowns (eligible sessions only)
    def summarise(df, by):
        g = df.groupby(by).agg(sessions=("session_id", "size"),
                               page_views=("page_views", "sum"),
                               sessions_apply_cta=("apply_cta_click", "sum"),
                               sessions_viewing_application=("viewed_application", "sum"),
                               sessions_email_click=("email_click", "sum")).reset_index()
        g["share_of_sessions"] = (g.sessions / g.sessions.sum()).round(4)
        g["apply_cta_rate"] = rate(g.sessions_apply_cta, g.sessions)
        g["email_click_rate"] = rate(g.sessions_email_click, g.sessions)
        g["email_per_application_viewer"] = rate(g.sessions_email_click, g.sessions_viewing_application)
        return g

    elig = elig.assign(month=elig.session_date.str[:7])
    summarise(elig, ["channel"]).sort_values("sessions", ascending=False).to_csv(m / "breakdown_channel.csv", index=False)
    summarise(elig, ["device_category"]).to_csv(m / "breakdown_device.csv", index=False)
    summarise(elig, ["month", "channel"]).to_csv(m / "breakdown_month_channel.csv", index=False)
    summarise(elig, ["month", "device_category"]).to_csv(m / "breakdown_month_device.csv", index=False)

    # Role breakdown: a session can view several roles, so rows are NOT additive.
    role_cols = [c for c in f.columns if c.startswith("viewed_role_") and c != "viewed_role_page"]
    rows = []
    for c in role_cols:
        x = elig[elig[c]]
        rows.append({"placement_role": c.replace("viewed_role_", "").replace("_", " ").title(),
                     "sessions_viewing_role": len(x),
                     "share_of_eligible_sessions": round(len(x) / len(elig), 4),
                     "sessions_viewing_only_this_role": int((x[role_cols].sum(axis=1) == 1).sum()),
                     "email_click_rate": round(x.email_click.mean(), 4),
                     "apply_cta_rate": round(x.apply_cta_click.mean(), 4)})
    roles = pd.DataFrame(rows)
    roles.loc[len(roles)] = {"placement_role": "Any role page (distinct sessions)",
                             "sessions_viewing_role": int(elig.viewed_role_page.sum()),
                             "share_of_eligible_sessions": round(elig.viewed_role_page.mean(), 4),
                             "sessions_viewing_only_this_role": None,
                             "email_click_rate": round(elig[elig.viewed_role_page].email_click.mean(), 4),
                             "apply_cta_rate": round(elig[elig.viewed_role_page].apply_cta_click.mean(), 4)}
    roles.to_csv(m / "breakdown_role_nonadditive.csv", index=False)

    # Intent funnel (distinct-session populations, not strictly ordered)
    funnel = pd.DataFrame([
        ("1. Eligible tracked sessions", len(elig)),
        ("2a. Clicked Apply Now (any page)", int(elig.apply_cta_click.sum())),
        ("2b. Viewed /application (any route, incl. direct landing)", int(elig.viewed_application.sum())),
        ("2c. ...of which landed directly on /application", int((elig.viewed_application & elig.landed_on_application).sum())),
        ("3. Clicked Send Email (intent, not a completed application)", int(elig.email_click.sum())),
        ("3a. ...email click without any Apply Now click", int((elig.email_click & ~elig.apply_cta_click).sum())),
    ], columns=["stage", "distinct_sessions"])
    funnel["pct_of_eligible"] = (funnel.distinct_sessions / len(elig)).round(4)
    funnel.to_csv(m / "intent_funnel.csv", index=False)
    return d


def main():
    for p in ["clean", "quality", "metrics"]:
        (OUT / p).mkdir(parents=True, exist_ok=True)
    log.clear(); checks.clear()

    raw_s, raw_e = read_raw("sessions.csv"), read_raw("events.csv")
    pages, campaigns = read_raw("pages.csv"), read_raw("campaigns.csv")

    s, q_s = clean_sessions(raw_s, campaigns)
    e, q_e = clean_events(raw_e, s, pages)
    q_s.to_csv(OUT / "quality" / "quarantine_sessions.csv", index=False)
    q_e.to_csv(OUT / "quality" / "quarantine_events.csv", index=False)

    f = session_flags(s, e)
    run_checks(raw_s, raw_e, s, e, pages, campaigns)

    s.drop(columns=["session_start_ts"]).to_csv(OUT / "clean" / "sessions_clean.csv", index=False)
    e.drop(columns=["event_ts", "session_start_ts"]).to_csv(OUT / "clean" / "events_clean.csv", index=False)
    f.to_csv(OUT / "clean" / "session_flags.csv", index=False)
    build_metrics(f, e)

    pd.DataFrame(log).to_csv(OUT / "quality" / "cleaning_log.csv", index=False)
    ch = pd.DataFrame(checks)
    ch.to_csv(OUT / "quality" / "dq_checks.csv", index=False)

    print(pd.DataFrame(log).to_string(index=False))
    print()
    print(ch.to_string(index=False))
    if (ch.status == "FAIL").any():
        raise SystemExit("One or more hard data-quality checks FAILED - outputs written but review before use.")


if __name__ == "__main__":
    main()
