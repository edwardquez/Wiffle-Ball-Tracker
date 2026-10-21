## Packages
import streamlit as st
import pandas as pd

import styles as ui
import stats
from db import league

# Page setup (must come first), then the shared look
st.set_page_config(page_title="Wiffle Ball Stats", layout="wide")
ui.apply()

# League tables, shared and cached for a few seconds (see db.py)
lg = league()
players = lg.players
completed = lg.completed

MIN_AB = 5   # an AVG leader with fewer at-bats than this gets a "small sample" tag
MIN_IP = 2   # minimum innings pitched to qualify for the ERA leader


# ---------------- Intro ---------------- #
season = int(completed["date"].dt.year.max()) if completed["date"].notna().any() else None
ui.html(
    (ui.eyebrow(f"Season {season}") if season else "")
    + "<h1 style='margin:16px 0 0; font-size:clamp(40px, 5vw, 60px); line-height:1.05;'>Wiffle Ball Stat Tracker</h1>"
    + f"<p style='margin:16px 0 0; max-width:640px; font-size:17px; line-height:1.6; color:{ui.BODY};'>"
    "A stat tracker for pickup Wiffle and Blitzball games with friends. Every at-bat is logged "
    "(batter, pitcher, count, runners on, outcome, RBIs), and batting, pitching and head-to-head "
    "stats are built from those events. Try scoring a game in practice mode!</p>"
    + f"<p style='margin:12px 0 0; font-family:{ui.MONO}; font-size:13px; color:{ui.MUTED};'>"
    "Python / Streamlit / MongoDB Atlas / pandas / Plotly</p>"
)
st.write("")

# A game being scored right now: point people to the Live page
in_progress = lg.games[(lg.games["mode"] == "live") & (lg.games["status"] == "active")]
if not in_progress.empty:
    g = in_progress.iloc[-1]
    ui.html(f"<a href='./Live' target='_self' style='display:flex; align-items:center; gap:10px; margin:22px 0 0; "
            f"padding:12px 14px; border:1px solid {ui.INK}; text-decoration:none; color:{ui.INK};'>"
            f"<span style='width:9px; height:9px; border-radius:50%; background:{ui.LOSS}; flex:none;'></span>"
            f"<span><b>Game in progress</b> · {ui.game_label(g['game_id'])} · follow it live &rarr;</span></a>")


# ---------------- League at a glance ---------------- #
runs = int(completed["team1_score"].sum() + completed["team2_score"].sum())
ui.html(
    ui.section_label("League at a glance", margin_top=40)
    + ui.kpi_grid([
        {"value": len(completed), "label": "Games played"},
        {"value": len(lg.pa), "label": "Plate appearances"},
        {"value": players["name"].nunique(), "label": "Players"},
        {"value": runs, "label": "Runs scored"},
    ])
)


# ---------------- Leaders ---------------- #
# Shared definitions from stats.py, so these match every other page
batting = lg.batting()
pitching = lg.pitching()
pitching = pitching[pitching["IP"] >= MIN_IP]


def leaders(df, col, ascending=False, round_to=3):
    """Everyone tied for the best value (compared as displayed), and that value."""
    if df.empty:
        return [], None
    values = df[col].astype(float).round(round_to)
    best = values.min() if ascending else values.max()
    return sorted(values[values == best].index.tolist()), best


# Everyone with an at-bat can lead in AVG; a leader under MIN_AB at-bats gets a small sample tag
avg_names, avg_val = leaders(batting[batting["AB"] >= 1], "AVG", round_to=3)
avg_few = [n for n in avg_names if batting.loc[n, "AB"] < MIN_AB]
avg_tag = ui.small_sample(f"Fewer than {MIN_AB} at-bats") if avg_few else ""
hr_names, hr_val = leaders(batting, "HR", round_to=0)
rbi_names, rbi_val = leaders(batting, "RBI", round_to=0)
era_names, era_val = leaders(pitching.dropna(subset=["ERA"]), "ERA", ascending=True, round_to=2)
war_names, war_val = leaders(stats.war(lg), "WAR", round_to=1)

ui.html(
    ui.section_label("Leaders", margin_top=40)
    + ui.kpi_grid([
        {"value": ui.rate(avg_val) if avg_names else "—", "label": "Batting average",
         "who": ui.names_with_ties(avg_names) if avg_names else "No at-bats yet", "who_tag": avg_tag},
        {"value": int(hr_val) if hr_names else "—", "label": "Home runs", "who": ui.names_with_ties(hr_names)},
        {"value": int(rbi_val) if rbi_names else "—", "label": "RBIs", "who": ui.names_with_ties(rbi_names)},
        {"value": f"{era_val:.2f}" if era_names else "—", "label": "ERA",
         "who": ui.names_with_ties(era_names) if era_names else "Not enough innings yet"},
        {"value": f"{war_val:+.1f}" if war_names and war_val else "—", "label": "Career WAR",
         "who": ui.names_with_ties(war_names) if war_names and war_val else "Not enough games yet"},
    ], min_width=130)
)


# ---------------- Latest game ---------------- #
if not completed.empty:
    latest = completed.iloc[-1]
    s1, s2 = int(latest["team1_score"]), int(latest["team2_score"])

    # Match number = its position among that season's completed games (same as the Game Log)
    same_season = completed[completed["date"].dt.year == latest["date"].year] if pd.notna(latest["date"]) else completed
    match_no = list(same_season["_id"]).index(latest["_id"]) + 1

    result_tag = ui.tag("Draw", ui.DRAW) if s1 == s2 else ui.tag("Final", ui.WIN)
    ui.html(
        ui.section_label("Latest game", margin_top=40)
        + f"<div style='border-top:2px solid {ui.INK};'>"
        + f"<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; "
        f"padding:14px 0; font-size:14px; color:{ui.MUTED}; border-bottom:1px solid {ui.RULE};'>"
        + f"<span style='display:inline-flex; align-items:center; gap:10px;'>{result_tag}"
        f"Match {match_no} · {ui.date_text(latest['date'])}</span>"
        + "<a href='./Game_Log' target='_self' style='font-weight:500;'>Full game log</a></div>"
        + ui.scoreline(str(latest["team1"]), s1, str(latest["team2"]), s2)
        + f"<div style='border-bottom:1px solid {ui.RULE};'></div></div>"
    )


# ---------------- Players ---------------- #
ui.html(
    ui.section_label("Players", margin_top=40)
    + ui.player_links(sorted(players["name"].dropna().tolist()))
)



