"""Live: a read-only scoreboard for anyone following a game. Refreshes itself every few seconds while a
game is being scored; nothing on this page changes the game."""
import streamlit as st
from html import escape

import game_engine as ge
import styles as ui
from box_score import plays_in_order, play_text
from db import get_db
from live_view import scoreboard, diamond, line_score

REFRESH_SECONDS = 10

st.set_page_config(page_title="Live", layout="wide")
ui.apply()
st.markdown("<style>[data-testid='stMainBlockContainer'] { max-width:680px; }</style>", unsafe_allow_html=True)
st.title("Live", anchor=False)


def label(text, top=22):
    return (f"<div style='margin:{top}px 0 6px; font-size:12px; font-weight:600; letter-spacing:1.4px; "
            f"text-transform:uppercase; color:{ui.MUTED};'>{text}</div>")


@st.fragment(run_every=REFRESH_SECONDS)
def live_board():
    # Read straight from the database (not the stats cache), so this is never more than one refresh behind
    games = get_db().games
    game = games.find_one({"mode": "live", "status": "active"}, sort=[("_id", -1)])
    if not game:
        last = games.find_one({"team1_score": {"$ne": None}, "team2_score": {"$ne": None}}, sort=[("_id", -1)])
        msg = (f"<p style='font-size:16px; line-height:1.6; color:{ui.BODY};'>No game is being scored right now. "
               "When the Scorekeeper starts one, it shows up here and updates by itself.</p>")
        if last:
            msg += (f"<p style='font-size:15px; color:{ui.MUTED};'>Last game: {escape(ui.game_label(last.get('game_id', '')))} · "
                    f"{escape(str(last.get('team1', 'Team 1')))} {int(last['team1_score'])}–{int(last['team2_score'])} "
                    f"{escape(str(last.get('team2', 'Team 2')))} · <a href='./Game_Log' target='_self'>Game Log</a></p>")
        ui.html(msg)
        return
    try:
        s = ge.replay(game["setup"], game.get("events") or [])
    except ge.GameError:
        ui.html(f"<p style='color:{ui.MUTED};'>This game can't be shown right now.</p>")
        return

    dot = f"<span style='display:inline-block; width:8px; height:8px; border-radius:50%; background:{ui.LOSS}; margin-right:7px;'></span>"
    status = {"live": "", "tied": " · tied after the last inning", "final": " · final, waiting to be saved"}[s.status]
    ui.html(f"<div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:4px 12px; "
            f"margin:-6px 0 14px; font-size:13px; color:{ui.MUTED};'>"
            f"<span>{dot}<b style='color:{ui.INK}; letter-spacing:1.2px;'>LIVE</b> · {escape(ui.game_label(game['game_id']))}{status}</span>"
            f"<span>Updates every {REFRESH_SECONDS} seconds</span></div>")
    ui.html(scoreboard(s) + diamond(s))
    if s.status == "live":
        allt = (game["setup"].get("all_time") or {})
        tag = " · all-time hitter" if allt.get("role") == "hitter" and allt.get("name") == s.batter else ""
        ui.html(f"<div style='margin:6px 0 4px; padding:14px 0; border-top:1px solid {ui.RULE}; border-bottom:1px solid {ui.RULE}; "
                "display:flex; justify-content:space-between; align-items:end; gap:12px;'>"
                f"<div><div style='font-size:12px; font-weight:600; letter-spacing:1.2px; text-transform:uppercase; color:{ui.MUTED};'>At bat{tag}</div>"
                f"<div style='font-family:{ui.SERIF}; font-size:28px; line-height:1.2;'>{escape(s.batter)}</div>"
                f"<div style='font-size:14px; color:{ui.MUTED};'>vs {escape(s.pitcher)} · on deck {escape(s.on_deck)}</div></div>"
                f"<div style='font-family:{ui.MONO}; font-size:32px;'>{s.balls}–{s.strikes}</div></div>")

    recent = plays_in_order(s)[-6:][::-1]
    if recent:
        rows = "".join(
            f"<div style='display:flex; gap:12px; padding:8px 0; border-bottom:1px solid {ui.RULE}; font-size:14px;'>"
            f"<span style='flex:none; width:52px; font-size:12px; color:{ui.MUTED}; padding-top:2px;'>"
            f"{'Top' if p['half'] == 'top' else 'Bot'} {p['inning']}</span><span>{play_text(kind, p)}</span></div>"
            for kind, p in recent)
        ui.html(label("Latest plays") + rows)
    ui.html(label("Line score", 26) + line_score(s))


live_board()