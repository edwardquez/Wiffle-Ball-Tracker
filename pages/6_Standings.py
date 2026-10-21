import streamlit as st

from html import escape
from urllib.parse import quote

import styles as ui
import stats
from db import league

# Page setup (must come first), then the shared look
st.set_page_config(page_title="Standings", layout="wide")
ui.apply()

# League tables, shared and cached for a few seconds (see db.py)
lg = league()

# Stat type toggle and stat tabs: restyle Streamlit's controls to match the rest of the site.
# Stat type = navy segmented control; stat picker = underlined text tabs.
st.markdown(f"""
<style>
.st-key-stat_type button {{
    min-height:44px !important; padding:0 22px !important; border-radius:0 !important; font-size:15px;
    border-color:{ui.INK} !important; background:transparent !important; color:{ui.INK} !important;
}}
.st-key-stat_type button[aria-checked="true"] {{ background:{ui.INK} !important; }}
.st-key-stat_type button[aria-checked="true"] p {{ color:{ui.CREAM} !important; font-weight:600; }}
.st-key-stat_level button {{
    min-height:32px !important; padding:0 14px !important; border-radius:0 !important;
    border-color:#B9B2A4 !important; background:transparent !important;
}}
.st-key-stat_level button p {{ font-size:13px; color:{ui.MUTED}; }}
.st-key-stat_level button[aria-checked="true"] {{ border-color:{ui.INK} !important; background:{ui.PANEL} !important; }}
.st-key-stat_level button[aria-checked="true"] p {{ color:{ui.INK} !important; font-weight:600; }}
.st-key-stat_pick {{ width:100% !important; }}
.st-key-stat_pick [data-testid="stButtonGroup"] {{ width:100%; }}
.st-key-stat_pick [role="radiogroup"] {{
    gap:4px 22px !important; border-bottom:1px solid {ui.RULE}; width:100%;
}}
.st-key-stat_pick button {{
    min-height:44px !important; padding:0 2px !important; margin-bottom:-1px; border:none !important;
    border-bottom:2px solid transparent !important; border-radius:0 !important;
    background:transparent !important; box-shadow:none !important;
}}
.st-key-stat_pick button p {{ color:{ui.MUTED}; font-size:15px; }}
.st-key-stat_pick button:hover p {{ color:{ui.INK}; }}
.st-key-stat_pick button[aria-checked="true"] {{ border-bottom-color:{ui.INK} !important; }}
.st-key-stat_pick button[aria-checked="true"] p {{ color:{ui.INK}; font-weight:600; }}
</style>
""", unsafe_allow_html=True)

title_col, season_col = st.columns([3, 1], vertical_alignment="bottom")
title_col.title("Standings", anchor=False)
# Career (every game) or one season; each season is measured against that season's league
season_pick = season_col.selectbox("Season", ["Career"] + [str(y) for y in stats.seasons(lg)], key="season")
year = None if season_pick == "Career" else int(season_pick)
lgs = lg if year is None else stats.season_league(lg, year)

# ---------- Stat pickers ---------- #
# Short tab label -> (column in the table, heading shown above the board)
HITTING = {
    "AVG": ("AVG", "Batting average"), "OBP": ("OBP", "On-base percentage"), "SLG": ("SLG", "Slugging percentage"),
    "OPS": ("OPS", "On-base plus slugging"), "HR": ("HR", "Home runs"), "RBI": ("RBI", "Runs batted in"),
    "R": ("R", "Runs scored"), "1B": ("1B", "Singles"), "2B": ("2B", "Doubles"), "3B": ("3B", "Triples"),
    "BB": ("BB", "Walks"), "BB%": ("BB%", "Walk rate"), "K%": ("K%", "Strikeout rate"),
}
PITCHING = {
    "ERA": ("ERA", "Earned run average"), "WHIP": ("WHIP", "Walks + hits per inning"),
    "K": ("P_K", "Strikeouts"), "K%": ("P_K%", "Strikeout rate"), "K/9": ("K/9", "Strikeouts per 9 innings"),
    "Hits Allowed": ("P_H", "Hits allowed"), "HR Allowed": ("P_HR", "Home runs allowed"),
    "Strike %": ("STR%", "Strike percentage"),
}
# Advanced (sabermetric) stats, shown with the Standard / Advanced switch under Hitting and Pitching
HITTING_ADV = {
    "wOBA": ("wOBA", "Weighted on-base average"), "wRC+": ("wRC+", "Weighted runs created plus"),
    "ISO": ("ISO", "Isolated power"), "BABIP": ("BABIP", "Batting average on balls in play"),
}
PITCHING_ADV = {
    "FIP": ("FIP", "Fielding-independent pitching"), "ERA-": ("ERA-", "ERA minus"),
    "K-BB%": ("K-BB%", "Strikeout rate minus walk rate"), "Opp OPS": ("OPP_OPS", "Opponent OPS"),
}
# Glossary entry for each board's "What's this?" link (column -> term on the Glossary page)
GLOSSARY = {
    "AVG": "avg", "OBP": "obp", "SLG": "slg", "OPS": "ops", "HR": "HR", "RBI": "rbi", "R": "r", "1B": "1B",
    "2B": "2B", "3B": "3B", "BB": "BB", "BB%": "bbpct", "K%": "kpct",
    "ERA": "era", "WHIP": "whip", "P_K": "K", "P_K%": "kpct", "K/9": "k9", "P_H": "codes", "P_HR": "HR", "STR%": "strpct",
    "wOBA": "woba", "wRC+": "wrc", "ISO": "iso", "BABIP": "babip",
    "FIP": "fip", "ERA-": "eraminus", "K-BB%": "kbb", "OPP_OPS": "oppops",
    "WAR": "war", "fWAR": "fwar", "bWAR": "fwar", "Batting runs": "batruns", "Pitching runs": "pitchruns",
    "Fielding runs": "fieldruns", "TO": "to", "E": "err",
}
# One line under the board explaining each advanced stat
EXPLAIN = {
    "wOBA": "Like OBP, but each way of reaching base counts by its run value: a home run is worth about three walks.",
    "wRC+": "Overall hitting with 100 as the league average: 130 is 30% better than the league's typical hitter.",
    "ISO": "Raw power: slugging minus batting average, so only extra bases count.",
    "BABIP": "Average on balls in play (no strikeouts or home runs). Very high or very low is usually luck that evens out.",
    "FIP": "ERA from only what a pitcher controls (strikeouts, walks, home runs), on the ERA scale. Lower is better.",
    "ERA-": "ERA with 100 as the league average. Lower is better: 80 is 20% better than the league.",
    "K-BB%": "Strikeouts minus walks, per batter faced. A quick read on pure pitching skill.",
    "OPP_OPS": "The OPS of the hitters a pitcher faced. Lower is better.",
}
OVERALL = {
    "WAR": ("WAR", "Wins above replacement"),
    "fWAR": ("fWAR", "WAR · FIP pitching only (fWAR-style)"), "bWAR": ("bWAR", "WAR · runs-allowed pitching only (bWAR-style)"),

    "Batting runs": ("Batting runs", "Batting runs above average"),
    "Pitching runs": ("Pitching runs", "Pitching runs above average"),
    "Fielding runs": ("Fielding runs", "Fielding runs above average"),
}
FIELDING = {
    "Throw-outs": ("TO", "Throw-outs"), "Errors": ("E", "Errors"),
}
# "Small sample" tag (players are still ranked): rate stats and WAR built on very few chances
SMALL_PA = 15      # hitting rates (AVG, OBP, K%...): fewer plate appearances than this
SMALL_BF = 12      # pitching rates (ERA, WHIP, K/9...): fewer batters faced than this
SMALL_WAR = 30     # WAR and run values: fewer plate appearances + batters faced than this
HIT_RATES = {"AVG", "OBP", "SLG", "OPS", "BB%", "K%", "wOBA", "wRC+", "ISO", "BABIP"}
PITCH_RATES = {"ERA", "WHIP", "P_K%", "K/9", "STR%", "FIP", "ERA-", "K-BB%", "OPP_OPS"}
# Lower is better for these columns (a hitter's K% included)
LOWER_IS_BETTER = {"ERA", "WHIP", "P_H", "P_HR", "K%", "E", "FIP", "ERA-", "OPP_OPS"}
PCT = {"K%", "BB%", "P_K%", "STR%", "K-BB%"}
RATE3 = {"AVG", "OBP", "SLG", "OPS", "wOBA", "ISO", "BABIP", "OPP_OPS"}
TWO_DP = {"ERA", "WHIP", "K/9", "FIP"}
WHOLE = {"wRC+", "ERA-"}           # index stats: shown and ranked as whole numbers
ONE_DP_SIGNED = {"WAR", "fWAR", "bWAR", "Batting runs", "Pitching runs", "Fielding runs"}

def keep_selected(key, fallback):
    """Tapping the selected button of a segmented control clears it; put the previous choice back instead."""
    if st.session_state.get(key) is None:
        st.session_state[key] = st.session_state.get(f"_{key}_last", fallback)
    st.session_state[f"_{key}_last"] = st.session_state[key]


stat_type = st.segmented_control("Stat type", ["Overall", "Hitting", "Pitching", "Fielding"], default="Overall",
                                 key="stat_type", label_visibility="collapsed",
                                 on_change=keep_selected, args=("stat_type", "Overall")) or "Overall"
level = "Standard"
if stat_type in ("Hitting", "Pitching"):
    level = st.segmented_control("Level", ["Standard", "Advanced"], default="Standard", key="stat_level",
                                 label_visibility="collapsed",
                                 on_change=keep_selected, args=("stat_level", "Standard")) or "Standard"
options = {"Overall": OVERALL, "Hitting": HITTING_ADV if level == "Advanced" else HITTING,
           "Pitching": PITCHING_ADV if level == "Advanced" else PITCHING, "Fielding": FIELDING}[stat_type]
category = st.pills("Stat", list(options), default=list(options)[0],
                    key="stat_pick", label_visibility="collapsed")
if category not in options:          # switching type can leave a stat that doesn't exist on the other side
    category = list(options)[0]
sort_col, heading = options[category]
ascending = sort_col in LOWER_IS_BETTER


# ---------- Per-player stats (shared definitions from stats.py) ---------- #
bat = lgs.advanced_batting()
pit = lgs.advanced_pitching().rename(columns={"K": "P_K", "K%": "P_K%", "H": "P_H", "HR": "P_HR"})
fld = stats.fielding(lgs.fielding)
df = (bat.join(pit[["ERA", "WHIP", "P_K", "P_K%", "K/9", "P_H", "P_HR", "STR%", "BF",
                    "FIP", "ERA-", "K-BB%", "OPP_OPS"]], how="outer")
      .join(fld[["TO", "E"]], how="outer"))
bl, fw, bw = (stats.war(lg, m, season=year) for m in ("blend", "fip", "ra"))
war_cols = (bl[["Batting runs", "Pitching runs", "Fielding runs", "WAA", "WAR", "G"]]
            .rename(columns={"G": "WAR_G"}).assign(fWAR=fw["WAR"], bWAR=bw["WAR"]))
df = df.join(war_cols, how="outer")
df.index.name = "Player"
df = df.reset_index()
# Fielding and run stats only exist for live-scored games; only rank players who have that data
if stat_type == "Fielding":
    in_live = df["Player"].isin(lgs.live_players)
    df[["TO", "E"]] = df[["TO", "E"]].fillna(0).where(in_live)
# Compare values as displayed, so players who look tied share a rank
if sort_col in RATE3 or sort_col in PCT:
    df[sort_col] = df[sort_col].round(3)
elif sort_col in TWO_DP:
    df[sort_col] = df[sort_col].round(2)
elif sort_col in WHOLE:
    df[sort_col] = df[sort_col].round(0)
elif sort_col in ONE_DP_SIGNED:
    df[sort_col] = df[sort_col].round(1)
    df.loc[df["WAR_G"].fillna(0) == 0, sort_col] = float("nan")   # didn't play in this season


def fmt(value):
    if sort_col in RATE3:
        return ui.rate(value)
    if sort_col in PCT:
        return f"{value * 100:.1f}%"
    if sort_col in TWO_DP:
        return f"{value:.2f}"
    if sort_col in ONE_DP_SIGNED:
        return "0.0" if abs(value) < 0.05 else f"{value:+.1f}"
    return f"{value:.0f}"


# ---------- Leaderboard ---------- #
if df.empty or df[sort_col].dropna().empty:
    st.info("No data for this stat yet. Play some games to see the standings.")
    st.stop()

# How many chances each player's number is built on, for the small sample tag
if stat_type == "Hitting" and sort_col in HIT_RATES:
    df["_n"], small_limit, small_what = df["PA"], SMALL_PA, "plate appearances"
elif stat_type == "Pitching" and sort_col in PITCH_RATES:
    df["_n"], small_limit, small_what = df["BF"], SMALL_BF, "batters faced"
elif stat_type == "Overall":
    df["_n"], small_limit, small_what = df["PA"].fillna(0) + df["BF"].fillna(0), SMALL_WAR, "plate appearances + batters faced"
else:
    df["_n"], small_limit, small_what = float("inf"), 0, ""   # counting stats and fielding: no tag
df["_n"] = df["_n"].fillna(0)

board = (df[["Player", sort_col, "_n"]].dropna(subset=[sort_col])
         .sort_values(by=[sort_col, "Player"], ascending=[ascending, True]).reset_index(drop=True))

# Players with the same value share a rank (1, T2, T2, 4...), like a real leaderboard
board["Rank"] = board[sort_col].rank(method="min", ascending=ascending).astype(int)
rank_counts = board["Rank"].value_counts()
top_rank, bottom_rank = board["Rank"].min(), board["Rank"].max()
biggest = board[sort_col].abs().max()   # WAR and runs can be negative: bars show size

rows = []
for _, row in board.iterrows():
    best = row["Rank"] == top_rank
    worst = row["Rank"] == bottom_rank and not best
    color = ui.WIN if best else ui.LOSS if worst else ui.INK
    bar = ui.WIN if best else ui.LOSS if worst else "rgba(20,33,61,0.38)"
    weight = 600 if best else 500
    width = abs(row[sort_col]) / biggest * 100 if biggest else 0
    rank = f"T{row['Rank']}" if rank_counts[row["Rank"]] > 1 else f"#{row['Rank']}"
    name = escape(str(row["Player"]))
    small = (ui.small_sample(f"Only {int(row['_n'])} {small_what} (under {small_limit})")
             if row["_n"] < small_limit else "")
    rows.append(
        "<div style='display:grid; grid-template-columns:56px minmax(0,260px) minmax(0,1fr) 80px; "
        f"align-items:center; gap:20px; padding:14px 0; border-bottom:1px solid {ui.RULE};'>"
        f"<span style='font-family:{ui.MONO}; font-size:14px; color:{ui.MUTED};'>{rank}</span>"
        "<span style='min-width:0;'>"
        f"<a href='./Player_Dashboard?player={quote(str(row['Player']))}' target='_self' "
        f"style='font-size:17px; font-weight:{weight}; text-decoration:none;'>{name}</a>{small}</span>"
        f"<div style='height:4px; background:{ui.TRACK};'>"
        f"<div style='height:4px; width:{width:.0f}%; background:{bar};'></div></div>"
        f"<span style='text-align:right; font-family:{ui.MONO}; font-size:17px; color:{color}; "
        f"font-weight:{weight};'>{fmt(row[sort_col])}</span></div>"
    )

explain = EXPLAIN.get(sort_col) if level == "Advanced" else None
term = GLOSSARY.get(sort_col)
what = ui.glossary_link(term) if term else ""
ui.html(
    f"<div role='heading' aria-level='2' style='margin:28px 0 6px; font-family:{ui.SERIF}; "
    f"font-size:30px; font-weight:500; color:{ui.INK};'>{heading}"
    f"<span style='font-size:18px; color:{ui.MUTED};'> · {season_pick.lower() if year is None else season_pick}</span></div>"
    + (f"<p style='margin:0 0 16px; font-size:14px; line-height:1.5; color:{ui.BODY}; max-width:720px;'>{explain} {what}</p>"
       if explain else f"<div style='margin:0 0 14px;'>{what}</div>")
    + f"<div style='border-top:2px solid {ui.INK};'>{''.join(rows)}</div>"
)