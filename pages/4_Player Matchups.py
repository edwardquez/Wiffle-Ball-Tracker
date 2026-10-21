import streamlit as st
import pandas as pd

from html import escape

import styles as ui
import stats
from db import league
from live_scoring import OUTCOME_NAMES

# Page setup (must come first), then the shared look
st.set_page_config(page_title="Player Matchups", layout="wide")
ui.apply()

# League tables, shared and cached for a few seconds (see db.py)
lg = league()
players, games = lg.players, lg.games

# Plate appearances with the long outcome names the at-bat log tags use
pa = lg.pa.copy()
pa["outcome_name"] = pa["outcome"].map(lambda c: OUTCOME_NAMES.get(c, c))
pa["_id"] = pa["game_order"] * 100000 + pa["seq"]


st.title("Player Matchups", anchor=False)

# ---------- Player pickers with a swap button ---------- #
names = sorted(players["name"].dropna().unique())
if len(names) < 2:
    st.info("Add at least two players to compare matchups.")
    st.stop()

if "mu_p1" not in st.session_state:
    st.session_state.mu_p1 = names[0]
    st.session_state.mu_p2 = names[1]


def swap_players():
    st.session_state.mu_p1, st.session_state.mu_p2 = st.session_state.mu_p2, st.session_state.mu_p1


c1, c2, c3 = st.columns([5, 1, 5], vertical_alignment="bottom")
player1 = c1.selectbox("Player 1", names, key="mu_p1")
c2.button("⇄", on_click=swap_players, help="Swap players", width="stretch")
player2 = c3.selectbox("Player 2", names, key="mu_p2")

if player1 == player2:
    st.warning("Please select two different players.")
    st.stop()

# Each player batting against the other (the pitching side is the same at-bats seen from the mound)
player1_hitting = pa[(pa["batter"] == player1) & (pa["pitcher"] == player2)]
player2_hitting = pa[(pa["batter"] == player2) & (pa["pitcher"] == player1)]
player1_pitching = player2_hitting
player2_pitching = player1_hitting


# ---------- Stat calculations (shared definitions from stats.py) ---------- #
def hitting_stats(data):
    b = stats.batting(data)
    r = b.iloc[0] if not b.empty else pd.Series(0.0, index=b.columns)
    nan = float("nan")
    return {
        "Plate appearances": r["PA"],
        "At-bats": r["AB"],
        "Hits": r["H"],
        "Singles": r["1B"],
        "Doubles": r["2B"],
        "Triples": r["3B"],
        "Home runs": r["HR"],
        "RBIs": r["RBI"],
        "Walks": r["BB"],
        "Strikeouts": r["K"],
        "AVG": r["AVG"] if not b.empty else nan,
        "OBP": r["OBP"] if not b.empty else nan,
        "SLG": r["SLG"] if not b.empty else nan,
    }


def pitching_stats(data):
    """Pitching numbers that add something beyond the opponent's batting line.

    Hits/walks/HR/strikeouts allowed are the same at-bats as the other player's batting
    stats, and ERA/WHIP/IP swing wildly on a handful of batters faced, so they're left out here.
    """
    return {
        "Games faced": data["game_id"].nunique(),
        "Outs recorded": int(data["outs"].sum()),
        "Double plays": int(data["outcome"].eq("DP").sum()),
        "Strikes thrown": int(data["strikes"].sum()),
        "Balls thrown": int(data["balls"].sum()),
    }


# Which side "wins" a row ("high" / "low"); rows not listed show no edge
RATE_STATS = {"AVG", "OBP", "SLG"}
HITTING_EDGE = {"AVG": "high", "OBP": "high", "SLG": "high", "Strikeouts": "low"}
PITCHING_EDGE = {"Outs recorded": "high", "Double plays": "high"}

BAR_NEUTRAL = "rgba(20,33,61,0.38)"   # filled part of a bar with no edge


def fmt_stat(stat, v):
    if pd.isna(v):
        return "—"
    return ui.rate(v) if stat in RATE_STATS else f"{v:.0f}"


def section_rule(label, top):
    """Section label sitting on a thin navy rule, with breathing room before the rows."""
    return (
        f"<div role='heading' aria-level='2' style='margin:{top}px 0 14px; padding-bottom:8px; "
        f"border-bottom:1px solid {ui.INK}; font-size:12px; font-weight:600; letter-spacing:1.6px; "
        f"text-transform:uppercase;'>{label}</div>"
    )


def comparison_rows(left, right, edges):
    """One row per stat: values either side of the label, a thin bar under each (always shown,
    filling from the center out). Better side green, worse side red, where 'better' is clear."""
    rows = []
    for stat in left:
        lv, rv = left[stat], right[stat]
        edge = edges.get(stat)
        l_win = r_win = False
        if edge and not pd.isna(lv) and not pd.isna(rv) and lv != rv:
            l_win = (lv > rv) if edge == "high" else (lv < rv)
            r_win = not l_win
        has_edge = l_win or r_win

        top = max(v for v in (lv, rv, 0) if not pd.isna(v))
        lw = 0 if pd.isna(lv) or top == 0 else lv / top * 100
        rw = 0 if pd.isna(rv) or top == 0 else rv / top * 100

        def color(win):
            return ui.WIN if win else (ui.LOSS if has_edge else ui.INK)

        def bar(win):
            return ui.WIN if win else (ui.LOSS if has_edge else BAR_NEUTRAL)

        def value(v, win, align):
            return (f"<div style='text-align:{align}; font-family:{ui.MONO}; font-size:17px; "
                    f"color:{color(win)}; font-weight:{600 if win else 400};'>{fmt_stat(stat, v)}</div>")

        rows.append(
            "<div style='padding:9px 0; display:flex; flex-direction:column; gap:7px;'>"
            "<div style='display:grid; grid-template-columns:minmax(0,1fr) 160px minmax(0,1fr); align-items:baseline;'>"
            + value(lv, l_win, "right")
            + f"<div style='text-align:center; font-size:13px; color:{ui.MUTED};'>{stat}</div>"
            + value(rv, r_win, "left")
            + "</div>"
            "<div style='display:grid; grid-template-columns:minmax(0,1fr) 160px minmax(0,1fr);'>"
            f"<div style='height:2px; background:{ui.TRACK}; display:flex; justify-content:flex-end;'>"
            f"<div style='height:2px; width:{lw:.0f}%; background:{bar(l_win)};'></div></div>"
            "<div></div>"
            f"<div style='height:2px; background:{ui.TRACK}; display:flex;'>"
            f"<div style='height:2px; width:{rw:.0f}%; background:{bar(r_win)};'></div></div>"
            "</div></div>"
        )
    return "".join(rows)


# ---------- Headline ---------- #
h1, h2 = hitting_stats(player1_hitting), hitting_stats(player2_hitting)


def headline(name, opp, h):
    if h["Plate appearances"] == 0:
        return f"<strong style='color:{ui.INK};'>{escape(name)}</strong> hasn't batted against {escape(opp)} yet."
    extras = [f"{h['Home runs']:.0f} HR"] if h["Home runs"] else []
    extras += [f"{h['RBIs']:.0f} RBI"] if h["RBIs"] else []
    extras += [f"{h['Walks']:.0f} BB"] if h["Walks"] else []
    extra = (", " + ", ".join(extras)) if extras else ""
    return (f"<strong style='color:{ui.INK};'>{escape(name)}</strong> is {h['Hits']:.0f}-for-{h['At-bats']:.0f} "
            f"({ui.rate(h['AVG'])}){extra} against {escape(opp)}.")


ui.html(
    f"<div style='margin:4px 0 28px; font-size:16px; line-height:1.6; color:{ui.BODY};'>"
    f"<div>{headline(player1, player2, h1)}</div><div>{headline(player2, player1, h2)}</div></div>"
)

# ---------- Names, then the two comparison sections ---------- #
names_header = (
    "<div style='display:grid; grid-template-columns:minmax(0,1fr) 160px minmax(0,1fr); align-items:end; "
    f"padding-bottom:12px; border-bottom:2px solid {ui.INK};'>"
    f"<div style='text-align:right; font-family:{ui.SERIF}; font-size:34px; font-weight:500; line-height:1;'>{escape(player1)}</div>"
    f"<div style='text-align:center; font-size:12px; letter-spacing:1.6px; text-transform:uppercase; "
    f"color:{ui.MUTED}; padding-bottom:4px;'>versus</div>"
    f"<div style='text-align:left; font-family:{ui.SERIF}; font-size:34px; font-weight:500; line-height:1;'>{escape(player2)}</div>"
    "</div>"
)
ui.html(
    names_header
    + section_rule("At the plate", top=28)
    + comparison_rows(h1, h2, HITTING_EDGE)
    + section_rule("On the mound", top=44)
    + comparison_rows(pitching_stats(player1_pitching), pitching_stats(player2_pitching), PITCHING_EDGE)
)


# ---------- At-bat logs ---------- #
# Square box-score tags: label, fill tint, border
TAGS = {
    "Single": ("1B", "#E3EFE7", "#7FA98F"), "Double": ("2B", "#E3EFE7", "#7FA98F"), "Triple": ("3B", "#E3EFE7", "#7FA98F"),
    "Home Run": ("HR", "#F4EAD2", "#C49A45"),
    "Strike Out": ("K", "#F6E1DA", "#C9826F"),
    "Walk": ("BB", "#E0E8F2", "#7F9BBE"),
    "Ground Out": ("GO", "#ECE9E2", "#B5AE9F"), "Pop Out": ("PO", "#ECE9E2", "#B5AE9F"),
    "Line Out": ("LO", "#ECE9E2", "#B5AE9F"), "Fielder's Choice": ("FC", "#ECE9E2", "#B5AE9F"),
    "Sacrifice Fly": ("SF", "#ECE9E2", "#B5AE9F"), "Double Play": ("DP", "#ECE9E2", "#B5AE9F"),
    "Triple Play": ("TP", "#ECE9E2", "#B5AE9F"),
    "Reached on Error": ("E", "#E0E8F2", "#7F9BBE"),
}

# Match numbers the same way the Game Log does: completed games in creation order, per season
completed = lg.completed
game_info = games.set_index("game_id")[["date", "_id"]].join(completed.set_index("game_id")[["match_no"]])


def tag(outcome):
    """A box-score tag. Tap (phone) or hover (computer) shows what it stands for. The tag itself isn't
    positioned, so the tooltip lines up with the start of its row of tags and never runs off the screen."""
    label, fill, border = TAGS.get(outcome, (str(outcome)[:2].upper(), "#ECE9E2", "#B5AE9F"))
    return (
        f"<span {ui.TAP} style='position:static; display:inline-block; min-width:26px; text-align:center; "
        f"padding:2px 5px; margin:0 5px 5px 0; border:1px solid {border}; background:{fill}; color:{ui.INK}; "
        f"border-radius:2px; font-family:{ui.MONO}; font-size:12px; font-weight:600;'>{label}"
        f"{ui.tip(f'<b>{escape(label)}</b> · {escape(str(outcome))}', 'wf-l wf-noarrow')}</span>"
    )


def matchup_log(log):
    """One row per game (newest first): date and match number, a summary, then a tag per at-bat."""
    if log.empty:
        return f"<p style='margin:8px 0; font-size:14px; color:{ui.MUTED};'>No at-bats in this matchup yet.</p>"

    log = log.join(game_info, on="game_id", rsuffix="_game").sort_values(["_id_game", "_id"], ascending=[False, True])
    rows = []
    for _, ab in log.groupby("game_id", sort=False):
        first = ab.iloc[0]
        match = f" · Match {int(first['match_no'])}" if pd.notna(first["match_no"]) else ""
        o = ab["outcome_name"]
        parts = [f"{len(ab)} PA", f"{o.isin(['Single', 'Double', 'Triple', 'Home Run']).sum()} H"]
        hr, bb, k = o.eq("Home Run").sum(), o.eq("Walk").sum(), o.eq("Strike Out").sum()
        rbi = int(pd.to_numeric(ab["rbi"], errors="coerce").fillna(0).sum())
        parts += [f"{hr} HR"] if hr else []
        parts += [f"{rbi} RBI"] if rbi else []
        parts += [f"{bb} BB"] if bb else []
        parts += [f"{k} K"] if k else []
        rows.append(
            f"<div style='padding:14px 0 11px; border-bottom:1px solid {ui.RULE};'>"
            "<div style='display:flex; justify-content:space-between; flex-wrap:wrap; gap:6px; font-size:14px; margin-bottom:10px;'>"
            f"<span style='font-weight:600;'>{ui.date_text(first['date'])}{match}</span>"
            f"<span style='color:{ui.MUTED}; font-family:{ui.MONO}; font-size:13px;'>{' · '.join(parts)}</span></div>"
            f"<div style='position:relative; display:flex; flex-wrap:wrap;'>{''.join(tag(x) for x in o)}</div></div>"
        )
    # No hairline under the last game; the expander's own border closes it
    rows[-1] = rows[-1].replace(f"border-bottom:1px solid {ui.RULE};", "", 1)
    return "".join(rows)


ui.html(section_rule("At-bat logs", top=44).replace(f"border-bottom:1px solid {ui.INK};", "border-bottom:none;"))
log1, log2 = st.columns(2, gap="large")
with log1:
    with st.expander(f"{player1} at bat vs {player2}"):
        ui.html(matchup_log(player1_hitting))
with log2:
    with st.expander(f"{player2} at bat vs {player1}"):
        ui.html(matchup_log(player2_hitting))