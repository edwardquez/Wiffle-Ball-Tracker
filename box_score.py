"""Box score for a live-scored game, built straight from the game's events (the engine replay), so every
number is exact per team, even with an all-time player who plays for both sides.

    box_score_tables(state) -> batting and pitching lines per team (plain data, tested in tests/)
    box_score_html(game)    -> line score, batting, pitching and play-by-play (Game Log)
"""
from html import escape

import game_engine as ge
import stats
import styles as ui
from live_scoring import ordinal
from live_view import line_score

# How a plate appearance reads in the play-by-play
VERB = {"1B": "singled", "2B": "doubled", "3B": "tripled", "HR": "homered", "BB": "walked", "K": "struck out",
        "GO": "grounded out", "PO": "popped out", "LO": "lined out", "FC": "reached on a fielder's choice",
        "SF": "hit a sac fly", "DP": "grounded into a double play", "TP": "hit into a triple play",
        "E": "reached on an error"}
HITS = {"1B", "2B", "3B", "HR"}


def box_score_tables(s):
    """{"batting": {team: [row, ...]}, "pitching": {team: [row, ...]}} in the order players appeared.

    Batting rows: name, PA, AB, H, R, RBI, BB, K. Pitching rows (team = the pitcher's side): name, OUTS, H,
    R, ER, BB, K, P. Runs scored and runs charged come from the plays, so they're exact."""
    bat = {1: {}, 2: {}}
    pit = {1: {}, 2: {}}

    def brow(team, name):
        return bat[team].setdefault(name, dict(name=name, PA=0, AB=0, H=0, R=0, RBI=0, BB=0, K=0))

    def prow(team, name):
        return pit[team].setdefault(name, dict(name=name, OUTS=0, H=0, R=0, ER=0, BB=0, K=0, P=0))

    for p in s.plate_appearances:
        t, o = p["team"], p["outcome"]
        r = brow(t, p["batter"])
        r["PA"] += 1
        r["AB"] += 0 if o in ("BB", "SF") else 1
        r["H"] += o in HITS
        r["RBI"] += int(p["rbi"])
        r["BB"] += o == "BB"
        r["K"] += o == "K"
        q = prow(3 - t, p["pitcher"])
        q["OUTS"] += p["outs_on_play"]
        q["H"] += o in HITS
        q["BB"] += o == "BB"
        q["K"] += o == "K"
        q["P"] += len(p["pitches"])
    for ev in s.runner_events:
        if ev["kind"] in ("CS", "PO"):
            prow(3 - ev["team"], ev["pitcher"])["OUTS"] += 1
    for t, plays in ((t, [p for p in s.plate_appearances if p["team"] == t] + [e for e in s.runner_events if e["team"] == t])
                     for t in (1, 2)):
        for p in plays:
            for run in p["runs"]:
                brow(t, run["player"])["R"] += 1
                q = prow(3 - t, run["pitcher"])
                q["R"] += 1
                q["ER"] += bool(run["earned"])
    return {"batting": {t: list(bat[t].values()) for t in (1, 2)},
            "pitching": {t: list(pit[t].values()) for t in (1, 2)}}


def _table(head, rows):
    th = f"padding:7px 4px; font-size:12px; font-weight:600; color:{ui.MUTED}; text-align:center;"
    td = f"padding:8px 4px; text-align:center; font-family:{ui.MONO}; font-size:13px;"
    h = f"<th style='{th} text-align:left; width:30%;'>{head[0]}</th>" + "".join(f"<th style='{th}'>{c}</th>" for c in head[1:])
    body = "".join(
        f"<tr style='border-bottom:1px solid {ui.RULE};'><td style='padding:8px 4px; font-size:14px; white-space:nowrap; "
        f"overflow:hidden; text-overflow:ellipsis;'>{escape(str(r[0]))}</td>" + "".join(f"<td style='{td}'>{c}</td>" for c in r[1:]) + "</tr>"
        for r in rows)
    return (f"<table style='width:100%; border-collapse:collapse; table-layout:fixed; margin-bottom:4px;'>"
            f"<thead><tr style='border-bottom:1px solid {ui.INK};'>{h}</tr></thead><tbody>{body}</tbody></table>")


def _label(text):
    return (f"<div style='margin:22px 0 4px; font-size:11px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; "
            f"color:{ui.MUTED};'>{text}</div>")


def play_text(kind, p):
    """One play-by-play line (HTML)."""
    scored = [r["player"] for r in p.get("runs", [])]
    if kind == "pa":
        text = f"<b>{escape(p['batter'])}</b> {VERB.get(p['outcome'], p['outcome'])}"
        if p["pitches"]:
            text += f" <span style='color:{ui.MUTED}; font-family:{ui.MONO}; font-size:12px;'>{escape(p['pitches'])}</span>"
    else:
        to = p.get("to")
        verb = {"SB": f"stole {'home' if to == 'H' else ordinal(to or 0)}", "CS": "was caught stealing",
                "PO": "was picked off"}[p["kind"]]
        text = f"<b>{escape(p['runner'])}</b> {verb}"
    if scored:
        text += f" · <span style='color:{ui.WIN}; font-weight:600;'>{escape(', '.join(scored))} scored</span>"
    return text


def plays_in_order(s):
    """Plate appearances and runner events together, in the order they happened."""
    return sorted([("pa", p) for p in s.plate_appearances] + [("run", r) for r in s.runner_events],
                  key=lambda x: x[1].get("n", 0))


def box_score_html(game):
    s = ge.replay(game["setup"], game.get("events") or [])
    tables = box_score_tables(s)
    team_names = {1: str(game.get("team1") or "Team 1"), 2: str(game.get("team2") or "Team 2")}
    out = [line_score(s)]
    for t in (1, 2):
        rows = [(r["name"], r["PA"], r["AB"], r["H"], r["R"], r["RBI"], r["BB"], r["K"]) for r in tables["batting"][t]]
        out.append(_label(f"Team {t} batting · {escape(team_names[t])}"))
        out.append(_table(["Batter", "PA", "AB", "H", "R", "RBI", "BB", "K"], rows))
    for t in (1, 2):
        rows = [(r["name"], stats.ip_text(r["OUTS"]), r["H"], r["R"], r["ER"], r["BB"], r["K"], r["P"])
                for r in tables["pitching"][t]]
        out.append(_label(f"Team {t} pitching"))
        out.append(_table(["Pitcher", "IP", "H", "R", "ER", "BB", "K", "P"], rows))

    pbp, last = [], None
    for kind, p in plays_in_order(s):
        half = (p["inning"], p["half"])
        if half != last:
            pbp.append(f"<div style='margin:14px 0 4px; font-size:11px; font-weight:600; letter-spacing:1.4px; "
                       f"text-transform:uppercase; color:{ui.MUTED};'>{'Top' if p['half'] == 'top' else 'Bottom'} "
                       f"of the {ordinal(p['inning'])}</div>")
            last = half
        pbp.append(f"<div style='padding:6px 0; font-size:14px; border-bottom:1px solid {ui.RULE};'>{play_text(kind, p)}</div>")
    out.append(_label("Play-by-play"))
    out.append(f"<div style='font-size:12px; color:{ui.MUTED}; margin-bottom:2px;'>Pitches: B ball · S strike · "
               "F foul · X put in play</div>")
    out.append("".join(pbp))
    return "".join(out)