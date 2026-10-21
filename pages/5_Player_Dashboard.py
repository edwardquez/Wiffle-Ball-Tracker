import streamlit as st
import pandas as pd

from urllib.parse import unquote

import styles as ui
import stats
from db import league

# Page setup (must come first), then the shared look
st.set_page_config(page_title="Player Dashboard", layout="wide")
ui.apply()

# League tables, shared and cached for a few seconds (see db.py)
lg = league()
players, games = lg.players, lg.games
split_players = stats.split_players


# ---------------- Which player? ---------------- #
selected_player = st.query_params.get("player")
selected_player = unquote(selected_player) if selected_player else None

if not selected_player or selected_player not in players["name"].values:
    st.title("Player Dashboard", anchor=False)
    ui.html(
        ui.section_label("Choose a player", margin_top=24)
        + ui.player_links(sorted(players["name"].dropna().tolist()))
    )
    st.stop()

# Back to the player list (clears ?player=... from the URL)
if st.button("← All players", type="tertiary"):
    st.query_params.clear()
    st.rerun()

st.title(selected_player, anchor=False)


# ---------------- Game info shared by both game logs ---------------- #
# Match numbers the same way the Game Log does: completed games in creation order, per season
completed = lg.completed
game_info = games.set_index("game_id")[["date", "_id", "team1_players", "team2_players", "team1_score", "team2_score"]]
game_info = game_info.join(completed.set_index("game_id")[["match_no"]])


def player_result(game_id):
    """('W', 8, 7) from this player's team's point of view, or None if unknown."""
    if game_id not in game_info.index:
        return None
    g = game_info.loc[game_id]
    if isinstance(g, pd.DataFrame):          # duplicate game_id: use the first
        g = g.iloc[0]
    if pd.isna(g["team1_score"]) or pd.isna(g["team2_score"]):
        return None
    if selected_player in split_players(g["team1_players"]):
        mine, theirs = int(g["team1_score"]), int(g["team2_score"])
    elif selected_player in split_players(g["team2_players"]):
        mine, theirs = int(g["team2_score"]), int(g["team1_score"])
    else:
        return None
    letter = "W" if mine > theirs else "L" if mine < theirs else "D"
    return letter, mine, theirs


# Record line under the name: W-D-L across completed games (stats.records; a draw is half a win)
rec = stats.records(completed)
r = rec.loc[selected_player] if selected_player in rec.index else None
line = f"{int(r.GP)} games · {int(r.W)}-{int(r.D)}-{int(r.L)} record" if r is not None else "0 games"
if r is not None and r.Both:
    line += f" · {int(r.Both)} as the all-time player"
ui.html(f"<div style='margin:-8px 0 28px; font-size:15px; color:{ui.MUTED};'>{line}</div>")


def row_for(df, name):
    return df.loc[name] if name in df.index else pd.Series(dtype=float)


def num(v, digits=0, pct=False):
    if v is None or pd.isna(v):
        return "—"
    if pct:
        return f"{v * 100:.1f}%"
    return f"{v:.{digits}f}"


# ---------------- VALUE (WAR) ---------------- #
def signed(v, digits=1):
    return "—" if v is None or pd.isna(v) else f"{v:+.{digits}f}".replace("+0.0", "0.0").replace("-0.0", "0.0")


st.header("Value", anchor=False)
# Career WAR = the sum of his seasons, each season measured against that season's league
w = row_for(stats.war(lg), selected_player)
ra_share = stats.runs_allowed_share(lg).get(selected_player)
games_n = int(w.get("G", 0) or 0)
live_n = int(w.get("Live G", 0) or 0)
ui.html(
    ui.kpi_grid([
        {"value": signed(w.get("WAR")), "label": "Career WAR"},
        {"value": signed(w.get("Batting runs")), "label": "Batting runs"},
        {"value": signed(w.get("Pitching runs")), "label": "Pitching runs"},
        {"value": signed(w.get("Fielding runs")), "label": "Fielding runs"},
        {"value": signed(w.get("Replacement runs")), "label": "Replacement runs"},
    ], min_width=140)
    + f"<div style='margin:10px 0 24px; font-size:13px; color:{ui.MUTED};'>Wins above a replacement player "
      f"(0.0 = a fill-in; {signed(w.get('WAA'))} vs. the league average) · {games_n} games ({live_n} live-scored)"
      + (f" · pitching mix {100 - ra_share * 100:.0f}% FIP / {ra_share * 100:.0f}% runs allowed" if ra_share is not None and pd.notna(ra_share) else "")
      + " · fielding counts live games only</div>"
)

# Season by season (newest first), with the career line at the bottom
by_season = stats.war_by_season(lg)
mine = by_season.loc[[selected_player]] if selected_player in by_season.index else by_season.iloc[0:0]
if len(mine):
    th = f"padding:10px 12px; font-size:12px; font-weight:600; color:{ui.MUTED}; text-align:right;"
    td = f"padding:11px 12px; text-align:right; font-family:{ui.MONO};"
    cols = [("G", lambda v: f"{v:.0f}"), ("Batting runs", signed), ("Pitching runs", signed),
            ("Fielding runs", signed), ("Replacement runs", signed), ("WAR", signed)]
    heads = ["G", "Batting", "Pitching", "Fielding", "Replacement", "WAR"]

    def tr(label, r, bold=False):
        weight = "font-weight:600;" if bold else ""
        cells = "".join(f"<td style='{td} {weight if c == 'WAR' or bold else ''}'>{f(r[c])}</td>" for c, f in cols)
        return (f"<tr style='border-bottom:1px solid {ui.RULE}; {'border-top:1px solid ' + ui.INK + ';' if bold else ''}'>"
                f"<td style='padding:11px 12px; {weight}'>{label}</td>{cells}</tr>")

    body = "".join(tr(str(int(r["Season"])), r) for _, r in mine.sort_values("Season", ascending=False).iterrows())
    body += tr("Career", w, bold=True)
    ui.html(
        f"<div style='margin:0 0 8px; font-size:13px; color:{ui.MUTED};'>Season by season · batting, pitching, "
        "fielding and replacement are in runs; WAR is those runs turned into wins</div>"
        "<div style='overflow-x:auto; margin-bottom:36px;'>"
        "<table style='width:100%; min-width:560px; border-collapse:collapse; font-size:15px;'>"
        f"<thead><tr style='border-top:2px solid {ui.INK}; border-bottom:1px solid {ui.INK};'>"
        f"<th style='{th} text-align:left;'>Season</th>" + "".join(f"<th style='{th}'>{h}</th>" for h in heads)
        + f"</tr></thead><tbody>{body}</tbody></table></div>"
    )


pa_bat = lg.pa[lg.pa["batter"] == selected_player]
pa_pit = lg.pa[lg.pa["pitcher"] == selected_player]


# ---------------- Game log table (shared by hitting and pitching) ---------------- #
RESULT_COLOR = {"W": ui.WIN, "L": ui.LOSS, "D": ui.DRAW}
RESULT_FILL = {"W": "rgba(46,107,78,0.10)", "L": "rgba(168,67,44,0.09)", "D": "rgba(63,95,134,0.10)"}


def tint(value, baseline, scale, higher_is_better=True):
    """Green if this game beat the player's career number, red if worse; stronger = bigger gap."""
    if pd.isna(value) or pd.isna(baseline):
        return ""
    diff = (value - baseline) if higher_is_better else (baseline - value)
    if abs(diff) < 1e-9:
        return ""
    strong = abs(diff) > scale / 2
    if diff > 0:
        return f"background-color: rgba(46,107,78,{0.20 if strong else 0.10});"
    return f"background-color: rgba(168,67,44,{0.18 if strong else 0.09});"


def show_game_log(rows, key_cols, title, toggle_key, rate_specs, standouts, formats):
    """Per-game table: newest first, Result column, rate stats shaded vs. career, standouts highlighted."""
    ui.html(ui.section_label(title, margin_top=36))
    df = pd.DataFrame(rows)
    if df.empty:
        st.caption("No games yet.")
        return

    df["_order"] = df["game_id"].map(lambda g: game_info["_id"].get(g) if g in game_info.index else None)
    df = df.sort_values("_order", ascending=False, na_position="last").reset_index(drop=True)
    df.insert(0, "Date", df["game_id"].map(lambda g: ui.date_text(game_info["date"].get(g)) if g in game_info.index else "—"))
    df.insert(1, "Game", df["game_id"].map(
        lambda g: f"Match {int(game_info['match_no'].get(g))}" if g in game_info.index and pd.notna(game_info["match_no"].get(g)) else "—"))
    res = df["game_id"].map(player_result)
    df.insert(2, "Result", res.map(lambda r: f"{r[0]} {r[1]}–{r[2]}" if r else "—"))
    # Live-scored games have a full box score on the Game Log
    live_ids = set(games.loc[games["mode"] == "live", "game_id"])
    df["Box score"] = df["game_id"].map(lambda g: f"./Game_Log?game={g}" if g in live_ids else None)
    df = df.drop(columns=["game_id", "_order"])

    show_all = st.toggle("Show all columns", key=toggle_key)
    view = df if show_all else df[["Date", "Game", "Result"] + key_cols + ["Box score"]]

    def style_cells(frame):
        css = pd.DataFrame("", index=frame.index, columns=frame.columns)
        for i, r in frame.iterrows():
            letter = str(r["Result"])[:1]
            if letter in RESULT_COLOR:
                css.at[i, "Result"] = f"color: {RESULT_COLOR[letter]}; background-color: {RESULT_FILL[letter]}; font-weight: 600;"
            for col, (baseline, scale, higher) in rate_specs.items():
                if col in frame.columns:
                    css.at[i, col] = tint(r[col], baseline, scale, higher)
            for col, rule in standouts(r).items():
                if col in frame.columns:
                    css.at[i, col] += rule
        return css

    styled = view.style.apply(style_cells, axis=None).format({c: f for c, f in formats.items() if c in view.columns})
    st.dataframe(styled, hide_index=True, width="stretch", column_config={
        "Box score": st.column_config.LinkColumn("Box score", display_text="Open", help="Opens in a new tab"),
    })


# ---------------- HITTING ---------------- #
st.header("Hitting", anchor=False)

b = row_for(lg.batting(batter=selected_player), selected_player)
career_avg, career_obp, career_slg = b.get("AVG"), b.get("OBP"), b.get("SLG")

ui.html(
    ui.kpi_grid([
        {"value": ui.rate(career_avg), "label": "Batting average"},
        {"value": ui.rate(career_obp), "label": "On-base %"},
        {"value": ui.rate(career_slg), "label": "Slugging %"},
        {"value": num(b.get("HR")), "label": "Home runs"},
        {"value": num(b.get("RBI")), "label": "RBIs"},
    ], min_width=140)
    + ui.stat_grid([
        {"value": num(b.get("G")), "label": "Games"},
        {"value": num(b.get("PA")), "label": "Plate appearances"},
        {"value": num(b.get("AB")), "label": "At-bats"},
        {"value": num(b.get("H")), "label": "Hits"},
        {"value": num(b.get("R")), "label": "Runs scored"},
        {"value": num(b.get("1B")), "label": "Singles"},
        {"value": num(b.get("2B")), "label": "Doubles"},
        {"value": num(b.get("3B")), "label": "Triples"},
        {"value": ui.rate(b.get("OPS")), "label": "OPS"},
        {"value": num(b.get("BB")), "label": "Walks"},
        {"value": num(b.get("BB%"), pct=True), "label": "Walk rate"},
        {"value": num(b.get("K")), "label": "Strikeouts"},
        {"value": num(b.get("K%"), pct=True), "label": "Strikeout rate"},
        {"value": num(b.get("SF")), "label": "Sacrifice flies"},
    ], min_width=110)
)

hitting_rows = []
for game_id, g in pa_bat.groupby("game_id"):
    gb = row_for(lg.batting(games=[game_id], batter=selected_player), selected_player)
    hitting_rows.append({
        "game_id": game_id, "PA": gb.PA, "AB": gb.AB, "H": gb.H, "1B": gb["1B"], "2B": gb["2B"], "3B": gb["3B"],
        "HR": gb.HR, "XBH": gb["2B"] + gb["3B"] + gb.HR, "R": gb.R, "RBI": gb.RBI, "BB": gb.BB, "K": gb.K,
        "SF": gb.SF, "AVG": gb.AVG, "OBP": gb.OBP, "SLG": gb.SLG, "K%": gb["K%"] * 100 if pd.notna(gb["K%"]) else float("nan"),
    })

count = lambda v: "—" if pd.isna(v) else f"{v:.0f}"
show_game_log(
    hitting_rows,
    key_cols=["AB", "H", "HR", "RBI", "BB", "K", "AVG", "OBP", "SLG"],
    title="Hitting game log",
    toggle_key="hitting_all_cols",
    rate_specs={"AVG": (career_avg, 0.25, True), "OBP": (career_obp, 0.25, True), "SLG": (career_slg, 0.50, True)},
    standouts=lambda r: {
        **({"HR": f"color: {ui.GOLD}; font-weight: 700;"} if r.get("HR", 0) > 0 else {}),
        **({"H": "font-weight: 700;"} if r.get("H", 0) >= 2 else {}),
    },
    formats={"AVG": ui.rate, "OBP": ui.rate, "SLG": ui.rate, "K%": lambda v: "—" if pd.isna(v) else f"{v:.1f}%",
             **{c: count for c in ["PA", "AB", "H", "1B", "2B", "3B", "HR", "XBH", "R", "RBI", "BB", "K", "SF"]}},
)


# ---------------- PITCHING ---------------- #
ui.html("<div style='height:28px;'></div>")
st.header("Pitching", anchor=False)

# Innings include caught-stealing and pickoff outs (lg.pitching adds them)
p = row_for(lg.pitching(pitcher=selected_player), selected_player)
career_era, career_whip = p.get("ERA"), p.get("WHIP")
outs = int(p.get("OUTS", 0) or 0)

ui.html(
    ui.kpi_grid([
        {"value": num(career_era, 2), "label": "ERA"},
        {"value": ui.innings(outs), "label": "Innings pitched"},
        {"value": num(p.get("K")), "label": "Strikeouts"},
        {"value": num(p.get("K%"), pct=True), "label": "Strikeout rate"},
        {"value": num(career_whip, 2), "label": "WHIP"},
    ], min_width=140)
    + ui.stat_grid([
        {"value": num(p.get("G")), "label": "Games pitched"},
        {"value": num(p.get("BF")), "label": "Batters faced"},
        {"value": num(p.get("ER")), "label": "Earned runs"},
        {"value": num(p.get("R")), "label": "Runs allowed"},
        {"value": num(p.get("H")), "label": "Hits allowed"},
        {"value": num(p.get("BB")), "label": "Walks allowed"},
        {"value": num(p.get("HR")), "label": "Home runs allowed"},
        {"value": num(p.get("K/9"), 1), "label": "K per 9"},
        {"value": num(p.get("BB/9"), 1), "label": "BB per 9"},
        {"value": num(p.get("P")), "label": "Pitches"},
        {"value": num(p.get("STR%"), pct=True), "label": "Strike %"},
        {"value": num(p.get("DP")), "label": "Double plays"},
    ], min_width=110)
)

pitching_rows = []
for game_id, g in pa_pit.groupby("game_id"):
    gp = row_for(lg.pitching(games=[game_id], pitcher=selected_player), selected_player)
    g_outs = int(gp.OUTS)
    pitching_rows.append({
        "game_id": game_id,
        # Baseball notation stored as a number (3.1 = 3⅓ innings) so it right-aligns and sorts like the others
        "IP": g_outs // 3 + (g_outs % 3) / 10, "H": gp.H, "ER": gp.ER, "R": gp.R, "BB": gp.BB, "K": gp.K, "HR": gp.HR,
        "ERA": gp.ERA, "WHIP": gp.WHIP, "K/9": gp["K/9"], "BF": gp.BF, "P": gp.P, "STR%": gp["STR%"],
        "Outs": g_outs, "DP": gp.DP,
    })

show_game_log(
    pitching_rows,
    key_cols=["IP", "H", "ER", "BB", "K", "ERA", "WHIP"],
    title="Pitching game log",
    toggle_key="pitching_all_cols",
    rate_specs={"ERA": (career_era, 4.0, False), "WHIP": (career_whip, 1.0, False)},
    standouts=lambda r: {
        # scoreless outing of at least one full inning ("1.0" or more)
        **({"ER": f"color: {ui.WIN}; font-weight: 700;"} if r.get("ER", 1) == 0 and r.get("IP", 0) >= 1 else {}),
        **({"K": "font-weight: 700;"} if r.get("K", 0) >= 3 else {}),
    },
    formats={"IP": "{:.1f}", "STR%": lambda v: "—" if pd.isna(v) else f"{v * 100:.0f}%",
             **{c: (lambda v: "—" if pd.isna(v) else f"{v:.2f}") for c in ["ERA", "WHIP", "K/9"]},
             **{c: count for c in ["H", "ER", "R", "BB", "K", "HR", "BF", "P", "Outs", "DP"]}},
)


# ---------------- FIELDING ---------------- #
ui.html("<div style='height:28px;'></div>")
st.header("Fielding", anchor=False)
f = row_for(stats.fielding(lg.fielding, names=[selected_player]), selected_player)
ui.html(
    ui.kpi_grid([
        {"value": num(f.get("TO")), "label": "Throw-outs"},
        {"value": num(f.get("E")), "label": "Errors"},
    ], min_width=140)
    + ui.stat_grid([
        {"value": num(f.get(f"TO {lab}")), "label": lab} for lab in stats.HOW_LABELS.values()
    ], min_width=110)
)