import streamlit as st
import pandas as pd

from html import escape

import styles as ui
import stats
from db import league
from live_scoring import OUTCOME_NAMES
from box_score import box_score_html

# Page setup (must come first), then the shared look
st.set_page_config(page_title="Game Log", layout="wide")
ui.apply()

# League tables, shared and cached for a few seconds (see db.py)
lg = league()

# Team colors for the scoring-play feed (blue / gold, so they don't clash with win green / loss red)
TEAM1_TEXT, TEAM1_FILL = "#3F5F86", "#E0E8F2"
TEAM2_TEXT, TEAM2_FILL = "#8A5F0E", "#F4EAD2"

# Only completed games (both scores entered), numbered per season by the order they were created
completed = lg.completed
completed[["team1_score", "team2_score"]] = completed[["team1_score", "team2_score"]].astype(int)


# ---------------- Header + season picker ---------------- #
title_col, season_col = st.columns([3, 1], vertical_alignment="bottom")
title_col.title("Game Log")

if completed.empty:
    st.info("No completed games yet.")
    st.stop()

years = sorted(completed["date"].dt.year.dropna().astype(int).unique(), reverse=True)
# A link like Game_Log?game=Game_6 (from a Player Dashboard) opens on that game's season with its box score open
open_game = st.query_params.get("game")
linked = completed[completed["game_id"] == open_game]
start = years.index(int(linked["date"].dt.year.iloc[0])) if not linked.empty and pd.notna(linked["date"].iloc[0]) else 0
selected_year = season_col.selectbox("Season", years, index=start)

season_games = completed[completed["date"].dt.year == selected_year].reset_index(drop=True)


def scoring_plays(game):
    """(inning, team, player, description, runs) for each play that scored, in order.

    Live-scored games come from the play-by-play, so every run is there (errors, double plays and
    steals of home included) and the running score matches the final. Older games only have RBIs."""
    if game["mode"] == "live":
        plays = lg.scoring[lg.scoring["game_id"] == game["game_id"]]
        out = []
        for p in plays.itertuples(index=False):
            if p.outcome == "SB home":
                text = "stole home"
            else:
                text = f"{OUTCOME_NAMES.get(p.outcome, p.outcome)}, {int(p.rbi)} RBI"
                if p.runs != p.rbi:
                    text += f" ({int(p.runs)} run{'s' if p.runs != 1 else ''} scored)"
            out.append((p.inning, int(p.team), p.player, text, int(p.runs)))
        return out
    t1, t2 = stats.split_players(game["team1_players"]), stats.split_players(game["team2_players"])
    plays = lg.pa[(lg.pa["game_id"] == game["game_id"]) & (lg.pa["rbi"] > 0)]
    return [(p.inning if pd.notna(p.inning) else "Unknown inning",
             1 if p.batter in t1 else 2 if p.batter in t2 else 0, str(p.batter),
             f"{OUTCOME_NAMES.get(p.outcome, p.outcome)}, {int(p.rbi)} RBI", int(p.rbi))
            for p in plays.itertuples(index=False)]


def scoring_feed(game):
    """HTML play-by-play of the plays that scored runs, with a running score."""
    plays = scoring_plays(game)
    if not plays:
        return None

    def swatch(fill, edge):
        return f"<span style='display:inline-block; width:10px; height:10px; background:{fill}; border:1px solid {edge};'></span>"

    parts = [
        f"<div style='display:flex; flex-wrap:wrap; gap:6px 20px; font-size:13px; color:{ui.MUTED}; margin-bottom:6px;'>"
        f"<span style='display:inline-flex; align-items:center; gap:8px;'>{swatch('#C9D7E8', TEAM1_TEXT)}{escape(str(game['team1']))}</span>"
        f"<span style='display:inline-flex; align-items:center; gap:8px;'>{swatch('#EEDDB5', TEAM2_TEXT)}{escape(str(game['team2']))}</span>"
        "</div>"
    ]

    def chip(score, scored, text, fill):
        if scored:
            return (f"<span style='min-width:22px; text-align:center; padding:1px 6px; background:{fill}; "
                    f"color:{text}; font-weight:600;'>{score}</span>")
        return f"<span style='min-width:22px; text-align:center; padding:1px 6px;'>{score}</span>"

    t1 = t2 = 0
    last_inning = None
    for inning, team, player, text, runs in plays:
        if inning != last_inning:
            parts.append(
                f"<div style='margin:14px 0 4px; font-size:11px; font-weight:600; letter-spacing:1.6px; "
                f"text-transform:uppercase; color:{ui.MUTED};'>{escape(str(inning))}</div>"
            )
            last_inning = inning
        if team == 1:
            t1 += runs
        elif team == 2:
            t2 += runs

        parts.append(
            "<div style='display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:baseline; gap:16px; padding:7px 0;'>"
            f"<span style='font-size:15px;'><strong style='font-weight:600;'>{escape(player)}</strong>"
            f"<span style='color:{ui.BODY};'> — {escape(text)}</span></span>"
            f"<span style='display:inline-flex; align-items:center; gap:6px; font-family:{ui.MONO}; font-size:15px; color:{ui.MUTED};'>"
            f"{chip(t1, team == 1, TEAM1_TEXT, TEAM1_FILL)}–{chip(t2, team == 2, TEAM2_TEXT, TEAM2_FILL)}</span>"
            "</div>"
        )
    return "".join(parts)


# ---------------- Matches (newest first) ---------------- #
newest_first = season_games.iloc[::-1]
if open_game in set(season_games["game_id"]):     # a linked game goes to the top, box score open
    newest_first = pd.concat([newest_first[newest_first["game_id"] == open_game],
                              newest_first[newest_first["game_id"] != open_game]])
for _, game in newest_first.iterrows():
    s1, s2 = game["team1_score"], game["team2_score"]
    if s1 == s2:
        colors, weights, result = (ui.DRAW, ui.DRAW), (600, 600), ui.tag("Draw", ui.DRAW)
    elif s1 > s2:
        colors, weights, result = (ui.WIN, ui.LOSS), (600, 500), ui.tag("Final", ui.WIN)
    else:
        colors, weights, result = (ui.LOSS, ui.WIN), (500, 600), ui.tag("Final", ui.WIN)

    ui.html(
        f"<div style='margin-top:36px; border-top:2px solid {ui.INK};'>"
        f"<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; "
        f"padding:14px 0; font-size:14px; color:{ui.MUTED}; border-bottom:1px solid {ui.RULE};'>"
        f"<span><strong style='color:{ui.INK}; font-weight:600; letter-spacing:1.4px; font-size:12px; "
        f"text-transform:uppercase; margin-right:12px;'>Match {int(game['match_no'])}</strong>{ui.date_text(game['date'])}</span>"
        f"{result}</div>"
        + ui.scoreline(str(game["team1"]), s1, str(game["team2"]), s2, colors=colors, weights=weights)
        + "</div>"
    )

    # Live-scored games have every play, so they get a full box score
    if game["mode"] == "live" and isinstance(game["setup"], dict):
        with st.expander("Box score", expanded=game["game_id"] == open_game):
            ui.html(box_score_html(game))
    with st.expander("Scoring plays"):
        feed = scoring_feed(game)
        if feed:
            ui.html(feed)
        else:
            st.caption("No scoring plays recorded for this game.")


# ---------------- Player records ---------------- #
# Shared definition (stats.py): a draw is half a win; the all-time player's games go in "Both"
rec = stats.records(season_games)
rows = [{"name": n, "W": int(r.W), "D": int(r.D), "L": int(r.L), "gp": int(r.GP), "both": int(r.Both),
         "pct": r.Pct} for n, r in rec.iterrows()]
# Best Win % first; more wins breaks a tie, then name (players with only "Both" games go last)
rows.sort(key=lambda r: (pd.isna(r["pct"]), -(r["pct"] if pd.notna(r["pct"]) else 0), -r["W"], r["name"]))
show_both = any(r["both"] for r in rows)

# Name column padded in from the edge; number columns centered under their headers
th = f"padding:10px 12px; font-size:12px; font-weight:600; color:{ui.MUTED};"
td_num = f"padding:12px 12px; text-align:center; font-family:{ui.MONO};"
body = "".join(
    f"<tr style='border-bottom:1px solid {ui.RULE};'>"
    f"<td style='padding:12px 12px; font-weight:500;'>{escape(r['name'])}</td>"
    f"<td style='{td_num}'>{r['W']}</td><td style='{td_num}'>{r['D']}</td><td style='{td_num}'>{r['L']}</td>"
    f"<td style='{td_num}'>{r['gp']}</td>"
    + (f"<td style='{td_num}'>{r['both'] or ''}</td>" if show_both else "")
    + f"<td style='{td_num} font-weight:600;'>{ui.rate(r['pct']) if pd.notna(r['pct']) else '—'}</td></tr>"
    for r in rows
)
both_head = f"<th style='text-align:center; {th}' title='Games as the all-time player (not in W/L)'>Both</th>" if show_both else ""
# Desktop: unchanged (names 40% wide, roomy cells). Phones: tighter cells and a narrower name column,
# so every column (through Win %) fits on screen without scrolling sideways.
records_css = (
    "<style>@media (max-width: 640px) {"
    ".wf-records { font-size:14px !important; }"
    ".wf-records th, .wf-records td { padding-left:4px !important; padding-right:4px !important; }"
    ".wf-records th:first-child, .wf-records td:first-child { padding-left:6px !important; }"
    ".wf-records col.wf-name { width:30% !important; }"
    "}</style>"
)
ui.html(
    records_css
    + ui.section_label(f"Player records, {selected_year}", margin_top=56)
    + "<div>"
    "<table class='wf-records' style='width:100%; border-collapse:collapse; border:none; font-size:15px; table-layout:fixed;'>"
    f"<colgroup><col class='wf-name' style='width:40%'><col><col><col><col>{'<col>' if show_both else ''}<col></colgroup>"
    f"<thead><tr style='border-top:2px solid {ui.INK}; border-bottom:1px solid {ui.INK};'>"
    f"<th style='text-align:left; {th}'>Player</th><th style='text-align:center; {th}'>W</th>"
    f"<th style='text-align:center; {th}'>D</th><th style='text-align:center; {th}'>L</th>"
    f"<th style='text-align:center; {th}'>GP</th>{both_head}<th style='text-align:center; {th}'>Win %</th></tr></thead>"
    f"<tbody>{body}</tbody></table></div>"
)