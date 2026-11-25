"""
Investigation charts and tables for the findings report.
Reads only the outputs of pipeline.py (run that first):   python src/analysis.py
Writes charts to reports/charts/ and supporting tables to output/metrics/investigations/.
"""
from pathlib import Path
import math
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parents[1]
CLEAN, MET = ROOT / "output" / "clean", ROOT / "output" / "metrics"
CH, INV = ROOT / "reports" / "charts", MET / "investigations"
CH.mkdir(parents=True, exist_ok=True); INV.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, AQUA, YELLOW, GREY, INK, INK2 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#a3a29c", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": "#c9c8c2", "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#ecebe7", "grid.linewidth": 0.8, "axes.axisbelow": True,
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "axes.titleweight": "bold",
                     "axes.titlesize": 11.5, "axes.titlelocation": "left"})

f = pd.read_csv(CLEAN / "session_flags.csv", parse_dates=["session_date"])
e = pd.read_csv(CLEAN / "events_clean.csv", low_memory=False)
d = pd.read_csv(MET / "daily_summary.csv", parse_dates=["date"])
cmp = pd.read_csv(ROOT / "data" / "raw" / "campaigns.csv", parse_dates=["start_date", "end_date"])
elig = f[f.is_eligible].copy()
elig["month"] = elig.session_date.dt.strftime("%Y-%m")
ev = e[~e.is_suspected_bot]


def save(fig, name):
    fig.tight_layout(); fig.savefig(CH / name, dpi=150); plt.close(fig)


def prop_ci(k, n, z=1.96):
    p = k / n; h = z * math.sqrt(p * (1 - p) / n); return p, p - h, p + h


# ---------------------------------------------------------------- 1. traffic over time
fig, ax = plt.subplots(figsize=(10, 4))
for _, c in cmp.iterrows():
    ax.axvspan(c.start_date, c.end_date + pd.Timedelta(days=1), color="#eef3fb", zorder=0)
    ax.text(c.start_date, 640, c.campaign_id, fontsize=8, color=INK2, va="top")
ax.bar(d.date, d.suspected_bot_sessions, bottom=d.eligible_sessions, color=ORANGE, width=1, label="Suspected bot (traffic-check.example)")
ax.plot(d.date, d.eligible_sessions, color=GREY, lw=1, label="Eligible sessions (daily)")
ax.plot(d.date, d.eligible_sessions.rolling(7, center=True).mean(), color=BLUE, lw=2, label="Eligible sessions (7-day average)")
ax.set_ylim(0, 650); ax.set_ylabel("Sessions per day")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
ax.set_title("Traffic peaked in October; a 3-day January spike is mostly bot-like traffic")
ax.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), frameon=False, fontsize=8.5)
save(fig, "01_daily_sessions.png")

# ---------------------------------------------------------------- 2. channel mix by month
mc = elig.pivot_table(index="month", columns="channel", values="session_id", aggfunc="size", fill_value=0)
order = ["Organic Search", "Social", "Direct", "Email", "Referral", "Unknown"]
mc = mc[[c for c in order if c in mc]]
mc.to_csv(INV / "monthly_sessions_by_channel.csv")
colors = [BLUE, ORANGE, AQUA, YELLOW, "#6250d6", GREY]
fig, ax = plt.subplots(figsize=(10, 4))
bottom = pd.Series(0, index=mc.index)
for col, colr in zip(mc.columns, colors):
    ax.bar(mc.index, mc[col], bottom=bottom, color=colr, label=col, width=0.65, edgecolor="#fcfcfb", linewidth=1.5)
    bottom += mc[col]
for i, t in enumerate(bottom): ax.text(i, t + 60, f"{t:,}", ha="center", fontsize=9, color=INK)
ax.set_ylabel("Eligible sessions"); ax.set_ylim(0, bottom.max() * 1.12)
ax.set_title("October rise led by Social (LinkedIn campaign); Nov & Jan bumps from Email")
ax.legend(ncol=6, frameon=False, fontsize=8.5, loc="upper right")
save(fig, "02_monthly_channel_mix.png")

# Month-on-month change by channel (which channels drove changes)
chg = mc.diff().dropna(); chg.to_csv(INV / "monthly_change_by_channel.csv")

# landing-page contribution by month
lp = elig.pivot_table(index="month", columns="landing_page_path", values="session_id", aggfunc="size", fill_value=0)
lp.to_csv(INV / "monthly_sessions_by_landing_page.csv")

# ---------------------------------------------------------------- 3. anomaly A: bot-like spike
win = f[(f.session_date >= "2026-01-12") & (f.session_date <= "2026-01-18")]
bot = f[f.is_suspected_bot]
a = pd.DataFrame({
    "metric": ["sessions", "distinct visitors", "% desktop", "% US or SG", "% landing on home page",
               "page views per session", "% with any apply/email click", "distinct hours of day with traffic"],
    "traffic-check.example": [len(bot), bot.visitor_id.nunique(), (bot.device_category == "desktop").mean(),
                              bot.country_code.isin(["US", "SG"]).mean(), (bot.landing_page_path == "/").mean(),
                              bot.page_views.mean(), (bot.apply_cta_click | bot.email_click).mean(),
                              pd.to_datetime(bot.session_start_ts).dt.hour.nunique()],
    "all other sessions": [len(elig), elig.visitor_id.nunique(), (elig.device_category == "desktop").mean(),
                           elig.country_code.isin(["US", "SG"]).mean(), (elig.landing_page_path == "/").mean(),
                           elig.page_views.mean(), (elig.apply_cta_click | elig.email_click).mean(),
                           pd.to_datetime(elig.session_start_ts).dt.hour.nunique()]})
a.to_csv(INV / "anomaly_A_bot_profile.csv", index=False)

# ---------------------------------------------------------------- 4. anomaly B: mobile email clicks drop
dev = elig[elig.device_category.isin(["desktop", "mobile"])]
dd = dev.groupby(["session_date", "device_category"]).agg(app=("viewed_application", "sum"), em=("email_click", "sum")).unstack()
dd = dd.loc["2025-11-17":"2025-12-21"]
gap = (dd.index >= "2025-12-02") & (dd.index <= "2025-12-09")
per = pd.DataFrame({
    "period": ["Before (1 Sep - 1 Dec)", "Gap (2 - 9 Dec)", "After (10 Dec - 28 Feb)"],
    "start": ["2025-09-01", "2025-12-02", "2025-12-10"], "end": ["2025-12-01", "2025-12-09", "2026-02-28"]})
rows = []
for _, p in per.iterrows():
    x = dev[(dev.session_date >= p.start) & (dev.session_date <= p.end)]
    for dv in ["desktop", "mobile"]:
        y = x[x.device_category == dv]
        rows.append({"period": p.period, "device": dv, "sessions_viewing_application": int(y.viewed_application.sum()),
                     "sessions_email_click": int(y.email_click.sum()),
                     "email_per_application_viewer": round(y.email_click.sum() / max(y.viewed_application.sum(), 1), 3),
                     "sessions_apply_cta": int(y.apply_cta_click.sum()), "sessions_video_play": int(y.video_play.sum())})
pd.DataFrame(rows).to_csv(INV / "anomaly_B_mobile_email_gap.csv", index=False)

fig, ax = plt.subplots(figsize=(10, 3.8))
x = range(len(dd)); w = 0.4
ax.bar([i - w / 2 for i in x], dd[("em", "desktop")], width=w, color=BLUE, label="Desktop sessions with email click")
ax.bar([i + w / 2 for i in x], dd[("em", "mobile")], width=w, color=ORANGE, label="Mobile sessions with email click")
gi = [i for i, g in zip(x, gap) if g]
ax.axvspan(gi[0] - 0.5, gi[-1] + 0.5, color="#fdeee8", zorder=0)
n_gap_app = int(dd[("app", "mobile")][gap].sum())
ax.text(gi[0], ax.get_ylim()[1] * 0.95, f"2-9 Dec: zero mobile email clicks\n({n_gap_app} mobile sessions still reached /application)",
        fontsize=8.5, color=INK, va="top")
ax.set_xticks(list(x)[::2]); ax.set_xticklabels([t.strftime("%d %b") for t in dd.index[::2]], fontsize=8)
ax.set_ylabel("Sessions per day"); ax.legend(frameon=False, fontsize=8.5, loc="upper right")
ax.set_title("Mobile Send Email clicks vanished for 8 days while desktop carried on")
save(fig, "03_mobile_email_gap.png")

# ---------------------------------------------------------------- 5. anomaly C: interview-prep journey
pv = ev[ev.event_name == "page_view"].groupby("page_path").size()
cta = ev[ev.event_name == "apply_cta_click"].groupby("page_path").size()
pg = pd.DataFrame({"page_views": pv, "apply_cta_clicks": cta}).fillna(0).astype(int)
pg = pg.drop(index="/application")    # Apply Now is not offered on the application page itself
pg["apply_clicks_per_100_views"] = (pg.apply_cta_clicks / pg.page_views * 100).round(1)
pg = pg.sort_values("apply_clicks_per_100_views")
pg.to_csv(INV / "apply_clicks_by_page.csv")
fig, ax = plt.subplots(figsize=(10, 3.8))
cols = [ORANGE if p in ("/interview-preparation",) else BLUE for p in pg.index]
ax.barh(pg.index, pg.apply_clicks_per_100_views, color=cols, height=0.6)
for i, v in enumerate(pg.apply_clicks_per_100_views): ax.text(v + 0.2, i, f"{v}", va="center", fontsize=8.5, color=INK)
ax.set_xlabel("Apply Now clicks per 100 page views (eligible sessions)"); ax.grid(axis="y", visible=False)
ax.set_title("Interview Preparation barely produces Apply clicks - yet the January newsletter sent readers there")
save(fig, "04_apply_clicks_by_page.png")

camp = []
for cid, x in elig[elig.campaign_id.notna()].groupby("campaign_id"):
    camp.append({"campaign_id": cid, "sessions": len(x), "top_landing_page": x.landing_page_path.mode()[0],
                 "share_on_top_landing_page": round((x.landing_page_path == x.landing_page_path.mode()[0]).mean(), 3),
                 "apply_cta_rate": round(x.apply_cta_click.mean(), 4), "email_click_rate": round(x.email_click.mean(), 4)})
camp.append({"campaign_id": "(no campaign)", "sessions": int(elig.campaign_id.isna().sum()), "top_landing_page": "/",
             "share_on_top_landing_page": round((elig[elig.campaign_id.isna()].landing_page_path == "/").mean(), 3),
             "apply_cta_rate": round(elig[elig.campaign_id.isna()].apply_cta_click.mean(), 4),
             "email_click_rate": round(elig[elig.campaign_id.isna()].email_click.mean(), 4)})
pd.DataFrame(camp).to_csv(INV / "campaign_sessions_summary.csv", index=False)

# ---------------------------------------------------------------- 6. Data Analyst question
# No /roles/data-analyst exists in pages.csv or anywhere in events. Technical Analyst is used as the
# nearest analytics placement, clearly labelled as a proxy.
ta = elig[elig.viewed_role_technical_analyst]
oth = elig[elig.viewed_role_page & ~elig.viewed_role_technical_analyst]
rows = []
for name, x in [("Technical Analyst viewers (proxy)", ta), ("Other role-page viewers", oth), ("All eligible sessions", elig)]:
    p, lo, hi = prop_ci(x.email_click.sum(), len(x))
    rows.append({"group": name, "sessions": len(x), "email_click_rate": round(p, 4), "ci95_low": round(lo, 4),
                 "ci95_high": round(hi, 4), "apply_cta_rate": round(x.apply_cta_click.mean(), 4),
                 "viewed_application_rate": round(x.viewed_application.mean(), 4),
                 "mean_page_views": round(x.page_views.mean(), 2), "pct_mobile": round((x.device_category == "mobile").mean(), 3),
                 "pct_organic_search": round((x.channel == "Organic Search").mean(), 3)})
pd.DataFrame(rows).to_csv(INV / "data_analyst_proxy_comparison.csv", index=False)

roles = ["technical_analyst", "data_engineer", "software_engineer", "marketing_associate"]
rm = elig.groupby("month")[[f"viewed_role_{r}" for r in roles]].mean() * 100
rm.columns = [r.replace("_", " ").title() for r in roles]
rm.round(2).to_csv(INV / "monthly_role_share_pct.csv")
fig, ax = plt.subplots(figsize=(10, 3.8))
for col, colr, lw in zip(rm.columns, [ORANGE, BLUE, AQUA, GREY], [2.6, 1.6, 1.6, 1.6]):
    ax.plot(rm.index, rm[col], color=colr, lw=lw, marker="o", ms=4, label=col)
    ax.text(len(rm) - 0.9, rm[col].iloc[-1], col, va="center", fontsize=8.5, color=INK)
ax.set_xlim(-0.3, len(rm) + 0.6); ax.set_ylim(0, 40)
ax.set_ylabel("% of eligible sessions viewing role page")
ax.legend(frameon=False, fontsize=8.5, ncol=4, loc="upper left")
ax.set_title("Technical Analyst (closest analytics role) holds a steady 13-15% share; Data Engineer jumps only with its campaign")
save(fig, "05_role_interest_share.png")

print("Charts:", sorted(p.name for p in CH.glob("*.png")))
print("Tables:", sorted(p.name for p in INV.glob("*.csv")))
for t in ["anomaly_A_bot_profile", "anomaly_B_mobile_email_gap", "campaign_sessions_summary", "data_analyst_proxy_comparison"]:
    print("\n==", t); print(pd.read_csv(INV / f"{t}.csv").to_string(index=False))
print("\n== monthly change by channel"); print(chg.to_string())
