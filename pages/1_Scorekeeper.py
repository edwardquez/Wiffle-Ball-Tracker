import streamlit as st
import os
import hmac

from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape

import styles as ui
import game_engine as ge
import live_scoring as ls
from live_view import scoreboard, diamond, line_score
from db import get_db, clear_cache

# Page setup (must come first), then the shared look
st.set_page_config(page_title="Scorekeeper", layout="wide")
ui.apply()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")    # db.py loads .env for local runs
# The server runs on UTC; default the game date to the league's local day
try:
    LOCAL_TZ = ZoneInfo("America/Los_Angeles")
except Exception:          # no time zone data on this computer: fall back to the server's clock
    LOCAL_TZ = None

# Phone-first layout: a narrow column, big tap targets, and button grids that stay side by side
# on small screens (Streamlit normally stacks columns on phones).
st.markdown(f"""
<style>
[data-testid="stMainBlockContainer"] {{ max-width:640px; padding-left:1rem; padding-right:1rem; padding-top:2.5rem; }}
[data-testid="stMain"] [data-testid="stWidgetLabel"] p {{
    font-size:12px; font-weight:600; letter-spacing:1.2px; text-transform:uppercase; color:{ui.MUTED};
}}
[data-testid="stMain"] [data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p {{
    font-size:15px; font-weight:400; letter-spacing:0; text-transform:none; color:{ui.INK};
}}
[data-testid="stMain"] .stButton button {{ min-height:48px; font-weight:600; font-size:15px; }}
[class*="st-key-grid"] [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap !important; gap:8px !important; }}
[class*="st-key-grid"] [data-testid="stColumn"] {{ min-width:0 !important; flex:1 1 0 !important; width:auto !important; }}
[class*="st-key-grid"] [data-testid="stVerticalBlock"] {{ gap:8px !important; }}
[class*="st-key-pitch_"] button {{ min-height:76px !important; font-size:20px !important; }}
[class*="st-key-oc_"] button {{ min-height:60px !important; font-family:{ui.MONO}; font-size:19px !important; }}
[class*="st-key-lu_"] button {{ min-height:50px !important; font-weight:500 !important; padding:0 6px !important; }}
.st-key-grid_nav button, .st-key-grid_nav [data-testid="stPopover"] button {{
    min-height:48px !important; border:none !important; background:transparent !important; font-size:14px !important;
}}
.st-key-grid_nav {{ border-top:1px solid {ui.RULE}; padding-top:4px; margin-top:8px; }}
.st-key-undo button p {{ color:{ui.LOSS} !important; }}
[data-testid="stMain"] [data-testid="stButtonGroup"] button[aria-checked="true"],
[role="dialog"] [data-testid="stButtonGroup"] button[aria-checked="true"] {{
    background:{ui.INK} !important; border-color:{ui.INK} !important;
}}
[data-testid="stMain"] [data-testid="stButtonGroup"] button[aria-checked="true"] p,
[role="dialog"] [data-testid="stButtonGroup"] button[aria-checked="true"] p {{ color:{ui.CREAM} !important; }}
[data-testid="stMain"] [data-testid="stButtonGroup"] button,
[role="dialog"] [data-testid="stButtonGroup"] button {{ border-radius:2px !important; min-height:40px; }}
[role="dialog"] [data-testid="stWidgetLabel"] p {{
    font-size:12px; font-weight:600; letter-spacing:1.2px; text-transform:uppercase; color:{ui.MUTED};
}}
[role="dialog"] .stButton button {{ min-height:52px; font-weight:600; }}
[class*="st-key-outbox_"] {{
    background:{ui.PANEL}; border-left:2px solid {ui.LOSS}; padding:10px 12px 4px; margin:4px 0 6px;
}}
.st-key-danger button {{ border:1px solid {ui.LOSS} !important; color:{ui.LOSS} !important; background:transparent !important; }}
</style>
""", unsafe_allow_html=True)


def label(text):
    return (f"<div style='font-size:12px; font-weight:600; letter-spacing:1.2px; text-transform:uppercase; "
            f"color:{ui.MUTED};'>{text}</div>")


def heading(text, size=28, top=0):
    ui.html(f"<div role='heading' aria-level='2' style='margin:{top}px 0 6px; font-family:{ui.SERIF}; "
            f"font-size:{size}px; font-weight:500; color:{ui.INK}; line-height:1.15;'>{text}</div>")


# ---------------------------------------------------------------- login
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
# Practice mode: visitors can try the Scorekeeper without the password. Everything goes into a private
# in-memory database that only exists in their browser session, so the league's real data is never touched.
if "practice" not in st.session_state:
    st.session_state.practice = False
PRACTICE = st.session_state.practice and not st.session_state.is_admin


def cb_practice(on):
    st.session_state.practice = on
    st.session_state.pop("practice_db", None)          # leaving (or restarting) throws the sandbox away
    for k in [k for k in st.session_state if k.startswith(("lv_", "ack_", "lu", "rot", "allt"))]:
        st.session_state.pop(k, None)


if not st.session_state.is_admin and not PRACTICE:
    st.title("Scorekeeper", anchor=False)
    ui.html(f"<p style='margin:0 0 24px; font-size:16px; line-height:1.6; color:{ui.BODY};'>"
            "This page is for recording games and is password protected. All stats are public; "
            "use the menu to browse them.</p>")
    with st.form("scorekeeper_login", border=False):
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log in", type="primary"):
            if ADMIN_PASSWORD and hmac.compare_digest(password, ADMIN_PASSWORD):
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    ui.html(f"<div style='margin-top:34px; padding:18px 18px 8px; background:{ui.PANEL}; border-left:2px solid {ui.INK};'>"
            f"<div style='font-family:{ui.SERIF}; font-size:22px;'>Just looking?</div>"
            f"<p style='margin:6px 0 10px; font-size:15px; line-height:1.55; color:{ui.BODY};'>Try the live scorekeeper in "
            "practice mode: pick lineups and score a game pitch by pitch. It's a private sandbox, so nothing you do "
            "touches the league's real stats, and it disappears when you leave.</p></div>")
    st.button("Try practice mode", width="stretch", on_click=cb_practice, args=(True,))
    st.stop()

with st.sidebar:
    if PRACTICE:
        st.button("Leave practice mode", type="tertiary", on_click=cb_practice, args=(False,))
    elif st.button("Log out of Scorekeeper", type="tertiary"):
        st.session_state.is_admin = False
        st.rerun()


# ---------------------------------------------------------------- data
# The live game is always read fresh from the database (never cached)
if PRACTICE:
    if "practice_db" not in st.session_state:
        import mongomock                                   # an in-memory stand-in for MongoDB
        sandbox = mongomock.MongoClient()["practice"]
        names = [p.get("name") for p in get_db().players.find({}, {"name": 1, "_id": 0}) if p.get("name")]
        sandbox.players.insert_many([{"name": n} for n in names] or [{"name": n} for n in ("Player A", "Player B")])
        st.session_state.practice_db = sandbox
    db = st.session_state.practice_db
    ui.html("<div style='margin:0 0 10px; padding:10px 12px; background:#F4EAD2; border:1px solid #C49A45; font-size:14px; "
            "line-height:1.5;'><b>Practice mode</b> · a private sandbox. Nothing here changes the real stats, and it's "
            "cleared when you leave.</div>")
    st.button("Leave practice mode", key="leave_practice", on_click=cb_practice, args=(False,))
else:
    db = get_db()
players_col, games_col = db["players"], db["games"]

player_names = sorted({p["name"] for p in players_col.find({}, {"name": 1}) if p.get("name")})
live_game = games_col.find_one({"mode": "live", "status": "active"}, sort=[("_id", -1)])

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))


# Every button that changes the game uses an on_click callback: the change is saved before the
# page redraws, so each tap is one clean rerun (no st.rerun, no leftover buttons, quicker on phones).

def refresh_stats():
    """After a save: make every stat page show it right away (practice games aren't real stats)."""
    if not PRACTICE:
        clear_cache()


STALE = "The game changed before that tap was saved (a double tap, or another phone), so it was skipped. Check the screen and try again."


def seen(oid, actual):
    """How many events this phone's screen was showing (set when the screen is drawn)."""
    return st.session_state.get(f"lv_n_{oid}", actual)


def saved(game, events_now):
    """Rewrite the game's at-bats and refresh every stat page after a change."""
    ls.sync_atbats(db, game["game_id"], ge.replay(game["setup"], events_now))
    refresh_stats()


def cb_events(oid, events, message=None, screen="pitch", ack=None):
    game = games_col.find_one({"_id": oid})
    if not game or game.get("status") != "active":
        st.session_state["lv_error"] = "This game isn't live anymore."
        return
    current = game.get("events", [])
    if len(current) != seen(oid, len(current)):
        st.session_state["lv_error"] = STALE
        return
    try:
        ge.replay(game["setup"], current + list(events))
    except ge.GameError as e:
        st.session_state["lv_error"] = str(e)
        return
    # Only saves if the game still has exactly the events this screen showed (no double taps,
    # no second phone saving in between), so the same pitch can't be recorded twice.
    res = games_col.update_one({"_id": oid, "status": "active", "events": {"$size": len(current)}},
                               {"$push": {"events": {"$each": list(events)}}})
    if res.matched_count == 0:
        st.session_state["lv_error"] = STALE
        return
    saved(game, current + list(events))
    st.session_state["lv_screen"] = screen
    if ack is not None:
        st.session_state[f"ack_{oid}"] = ack
    if message:
        st.session_state["flash"] = message


def cb_event(oid, event, message=None):
    cb_events(oid, [event], message)


def cb_undo(oid):
    game = games_col.find_one({"_id": oid})
    if not game or game.get("status") != "active" or not game.get("events"):
        return
    if len(game["events"]) != seen(oid, len(game["events"])):
        st.session_state["lv_error"] = STALE
        return
    res = games_col.update_one({"_id": oid, "status": "active", "events": {"$size": len(game["events"])}},
                               {"$pop": {"events": 1}})
    if res.matched_count == 0:
        st.session_state["lv_error"] = STALE
        return
    saved(game, game["events"][:-1])
    st.session_state["lv_screen"] = "pitch"
    st.session_state["flash"] = "Undid the last entry."


def cb_screen(name, outcome=None):
    st.session_state["lv_screen"] = name
    if outcome:
        st.session_state["lv_outcome"] = outcome


def cb_ack(oid, n):
    st.session_state[f"ack_{oid}"] = n


if "lv_error" in st.session_state:
    st.error(st.session_state.pop("lv_error"))


# ================================================================ SETUP (no live game)
def cb_toggle(team, name):
    lst = st.session_state.setdefault(f"lu{team}", [])
    if name in lst:
        lst.remove(name)
    else:
        lst.append(name)


def cb_start(setup, team_lists, game_date):
    s = {"lineups": {1: setup["lineups"]["1"], 2: setup["lineups"]["2"]},
         "rotations": {1: setup["rotations"]["1"], 2: setup["rotations"]["2"]},
         "outs_per_half": setup["outs_per_half"], "all_time": setup["all_time"]}
    try:
        ge.validate_setup(s)
    except ge.GameError as e:
        st.session_state["lv_error"] = str(e)
        return
    if games_col.find_one({"mode": "live", "status": "active"}):
        st.session_state["lv_error"] = "A game is already live (started on another phone)."
        return
    existing = [g.get("game_id") for g in games_col.find({}, {"game_id": 1})]
    game_id = ls.next_game_id(existing)
    t1, t2 = team_lists
    games_col.insert_one({
        "game_id": game_id, "date": str(game_date), "mode": "live", "status": "active",
        # Kept in the old format so the other pages work; the all-time hitter is left out
        # of the team lists so the game doesn't count in his W/L.
        "team1": ", ".join(t1), "team2": ", ".join(t2),
        "team1_players": ",".join(t1), "team2_players": ", ".join(t2),
        "setup": setup, "events": [],
    })
    refresh_stats()
    for k in ("lu1", "lu2", "allt_name", "rot1", "rot2", "rot1_src", "rot2_src"):
        st.session_state.pop(k, None)
    st.session_state["flash"] = f"{ui.game_label(game_id)} started. Play ball."


def setup_screen():
    st.title("Scorekeeper", anchor=False)
    heading("Set the lineups", 28, top=4)

    lu = {1: st.session_state.setdefault("lu1", []), 2: st.session_state.setdefault("lu2", [])}
    for t in (1, 2):
        lu[t][:] = [n for n in lu[t] if n in player_names]
    allt = st.session_state.get("allt_name", "None")

    # Selected lineup buttons are filled navy; the CSS is generated for whichever are picked
    picked_css = []
    for t in (1, 2):
        ui.html(f"<div style='margin-top:14px; padding-top:12px; border-top:2px solid {ui.INK}; display:flex; "
                f"justify-content:space-between; align-items:baseline;'>{label(f'Team {t}')}"
                f"<span style='font-size:13px; color:{ui.MUTED};'>Tap in batting order</span></div>")
        with st.container(key=f"grid_lu{t}"):
            per_row = 4
            for start in range(0, len(player_names), per_row):
                cols = st.columns(per_row)
                for j, name in enumerate(player_names[start:start + per_row]):
                    i = start + j
                    key = f"lu_{t}_{i}"
                    taken = name in lu[3 - t] or name == allt
                    if name in lu[t]:
                        picked_css.append(f".st-key-{key} button {{ background:{ui.INK} !important; border-color:{ui.INK} !important; }}"
                                          f".st-key-{key} button p {{ color:{ui.CREAM} !important; }}")
                        text = f"{lu[t].index(name) + 1} · {name}"
                    else:
                        text = name
                    cols[j].button(text, key=key, disabled=taken, width="stretch",
                                   on_click=cb_toggle, args=(t, name))
    if picked_css:
        st.markdown(f"<style>{''.join(picked_css)}</style>", unsafe_allow_html=True)

    # All-time player
    ui.html(f"<div style='margin-top:18px; padding-top:12px; border-top:2px solid {ui.INK};'>"
            f"{label('All-time player · optional')}</div>")
    free = [n for n in player_names if n not in lu[1] and n not in lu[2]]
    c1, c2 = st.columns([3, 2], vertical_alignment="bottom")
    allt = c1.selectbox("Player", ["None"] + free, key="allt_name", label_visibility="collapsed")
    role = c2.segmented_control("Role", ["Hitter", "Pitcher"], default="Hitter", key="allt_role",
                                label_visibility="collapsed") or "Hitter"
    allt_name = None if allt == "None" else allt
    spot = None
    if allt_name and role == "Hitter":
        most = max(len(lu[1]), len(lu[2])) + 1
        spot = st.selectbox("Bats in both lineups at spot", list(range(1, most + 1)), index=most - 1, key="allt_spot")
        st.caption("Bats for both teams, never fields, and the game doesn't count in his W/L.")
    elif allt_name:
        st.caption("Pitches for both teams and never bats.")

    # Rotations (defaults to the batting order; order can be changed by re-picking)
    ui.html(f"<div style='margin-top:18px; padding-top:12px; border-top:2px solid {ui.INK};'>{label('Pitching rotation')}</div>")
    rot = {}
    for t in (1, 2):
        options = lu[t] + ([allt_name] if allt_name and role == "Pitcher" else [])
        if st.session_state.get(f"rot{t}_src") != options:      # lineup changed: reset to the default order
            st.session_state[f"rot{t}"] = list(options)
            st.session_state[f"rot{t}_src"] = list(options)
        rot[t] = st.multiselect(f"Team {t}", options, key=f"rot{t}", placeholder="Pick in rotation order")

    # Outs + date + start
    ui.html(f"<div style='margin-top:18px; padding-top:12px; border-top:2px solid {ui.INK};'></div>")
    c1, c2 = st.columns([3, 2], vertical_alignment="center")
    c1.markdown(label("Outs per half-inning"), unsafe_allow_html=True)
    outs = c2.segmented_control("Outs", [2, 3], default=3, key="setup_outs", label_visibility="collapsed") or 3
    c1, c2 = st.columns([2, 3], vertical_alignment="bottom")
    game_date = c1.date_input("Date", value=datetime.now(LOCAL_TZ).date(), key="setup_date")
    lineups = {1: list(lu[1]), 2: list(lu[2])}
    all_time = None
    if allt_name:
        all_time = {"name": allt_name, "role": role.lower()}
        if role == "Hitter":
            for t in (1, 2):
                lineups[t].insert(min(spot - 1, len(lineups[t])), allt_name)
    setup = {"lineups": {"1": lineups[1], "2": lineups[2]},
             "rotations": {"1": list(rot[1]), "2": list(rot[2])},
             "outs_per_half": int(outs), "all_time": all_time}
    c2.button("Play ball", type="primary", width="stretch",
              on_click=cb_start, args=(setup, (list(lu[1]), list(lu[2])), game_date))


# ================================================================ LIVE GAME
PITCH_TAG = {"B": ("#E0E8F2", "#7F9BBE"), "S": ("#F6E1DA", "#C9826F"), "F": ("#ECE9E2", "#B5AE9F")}


def batter_block(s, game):
    allt = (game["setup"].get("all_time") or {})
    tag = " · all-time" if allt.get("role") == "hitter" and allt.get("name") == s.batter else ""
    tags = "".join(f"<span style='padding:1px 5px; border:1px solid {PITCH_TAG[c][1]}; background:{PITCH_TAG[c][0]}; "
                   f"font-family:{ui.MONO}; font-size:12px; font-weight:600;'>{c}</span>" for c in s.pa_pitches)
    return (f"<div style='margin-top:8px; padding:14px 0; border-top:1px solid {ui.RULE}; border-bottom:1px solid {ui.RULE}; "
            f"display:grid; grid-template-columns:1fr auto; align-items:end; gap:10px;'>"
            f"<div style='display:flex; flex-direction:column; gap:4px;'>{label('At bat' + tag)}"
            f"<span style='font-family:{ui.SERIF}; font-size:30px; font-weight:500; line-height:1;'>{escape(s.batter)}</span>"
            f"<span style='font-size:14px; color:{ui.MUTED};'>vs {escape(s.pitcher)} · {ls.batter_line(s, s.batter)}</span></div>"
            f"<div style='display:flex; flex-direction:column; align-items:flex-end; gap:6px;'>"
            f"<span style='font-family:{ui.MONO}; font-size:34px; font-weight:500; line-height:1;'>{s.balls}–{s.strikes}</span>"
            f"<div style='display:flex; gap:4px; min-height:20px;'>{tags}</div></div></div>")


def on_deck_note(s):
    nxt = s.on_deck
    on_base = [b for b, r in s.runners().items() if r.name == nxt and not r.ghost]
    extra = (f" · on {ls.ordinal(on_base[0])}, so a ghost runner takes his base when he bats." if on_base else "")
    return f"<p style='margin:10px 0 6px; font-size:13px; color:{ui.MUTED};'>On deck: <strong style='color:{ui.INK};'>{escape(nxt)}</strong>{extra}</p>"


def fielders(s, game):
    """Who can be charged with an error: the fielding team plus the pitcher, never the all-time hitter."""
    allt = game["setup"].get("all_time") or {}
    team = [n for n in game["setup"]["lineups"][str(s.fielding_team)] if not (allt.get("role") == "hitter" and n == allt.get("name"))]
    if s.pitcher not in team:
        team.append(s.pitcher)
    return team


def pitchers_for(s, game):
    allt = game["setup"].get("all_time") or {}
    team = [n for n in game["setup"]["lineups"][str(s.fielding_team)] if not (allt.get("role") == "hitter" and n == allt.get("name"))]
    for n in game["setup"]["rotations"][str(s.fielding_team)]:
        if n not in team:
            team.append(n)
    return team


# ---------------- screens

def pitch_screen(s, game):
    ui.html(on_deck_note(s))
    with st.container(key="grid_pitch"):
        c1, c2 = st.columns(2)
        oid = game["_id"]
        c1.button("Ball", key="pitch_B", width="stretch", on_click=cb_event, args=(oid, {"type": "pitch", "result": "B"}))
        c2.button("Strike", key="pitch_S", width="stretch", on_click=cb_event, args=(oid, {"type": "pitch", "result": "S"}))
        c1, c2 = st.columns(2)
        c1.button("Foul", key="pitch_F", width="stretch", on_click=cb_event, args=(oid, {"type": "pitch", "result": "F"}))
        c2.button("In play", key="pitch_X", type="primary", width="stretch", on_click=cb_screen, args=("inplay",))

    with st.container(key="grid_nav"):
        c1, c2, c3, c4 = st.columns(4)
        for col, name in ((c1, "Runner"), (c2, "Pitcher"), (c3, "Game")):
            col.button(name, key=f"nav_{name}", width="stretch", on_click=cb_screen, args=(name.lower(),))
        with c4.container(key="undo"):
            st.button("Undo", width="stretch", disabled=not game.get("events"),
                      on_click=cb_undo, args=(game["_id"],))


def menu_screen(s, game, which):
    heading({"runner": "Runner on base", "pitcher": "Change pitcher", "game": "Game settings"}[which], 26, top=10)
    {"runner": runner_menu, "pitcher": pitcher_menu, "game": game_menu}[which](s, game)
    st.write("")
    st.button("Back to pitches", key="menu_back", width="stretch", on_click=cb_screen, args=("pitch",))


def runner_menu(s, game):
    runners = s.runners()
    if not runners:
        st.caption("Nobody's on base.")
        return
    opts = {f"{ls.ordinal(b)} · {r.name}": b for b, r in sorted(runners.items())}
    pick = st.radio("Runner", list(opts), key="rm_runner")
    base = opts[pick]
    kind = st.radio("What happened", ["Stole", "Caught stealing", "Picked off"], key="rm_kind", horizontal=True)
    to = None
    if kind == "Stole":
        # A runner can only steal up to the next occupied base (he can't pass the runner ahead)
        targets = []
        for b in range(base + 1, 4):
            if s.bases[b]:
                break
            targets.append(b)
        else:
            targets.append("H")
        if not targets:
            st.caption(f"The runner on {ls.ordinal(base + 1)} has to move first.")
            return
        names = {b: ("Home" if b == "H" else ls.ordinal(b)) for b in targets}
        to = st.radio("Stole", targets, format_func=lambda b: names[b], key=f"rm_to_{base}", horizontal=True)
    code = {"Stole": "SB", "Caught stealing": "CS", "Picked off": "PO"}[kind]
    name = runners[base].name
    extra = {}
    if code in ("CS", "PO"):
        extra = out_box(s, game, f"rm_{base}_{code}_{len(game.get('events', []))}")
    msg = f"{name} {'stole ' + ('home' if to == 'H' else ls.ordinal(to)) if code == 'SB' else kind.lower()}."
    st.button("Save", key="rm_save", type="primary", width="stretch", on_click=cb_event,
              args=(game["_id"], {"type": "runner", "kind": code, "base": base, "to": to, **extra}, msg))


def pitcher_menu(s, game):
    opts = pitchers_for(s, game)
    st.caption(f"Now pitching: {s.pitcher}")
    new = st.radio("New pitcher", opts, index=opts.index(s.pitcher) if s.pitcher in opts else 0, key="pm_pick")
    st.button("Change pitcher", key="pm_save", type="primary", width="stretch", disabled=new == s.pitcher,
              on_click=cb_event, args=(game["_id"], {"type": "pitcher", "name": new}, f"{new} is now pitching."))


def game_menu(s, game):
    if s.last_inning:
        st.caption(f"Last inning: the {ls.ordinal(s.last_inning)}.")
        st.button("Clear last inning", key="gm_clear", width="stretch", on_click=cb_event,
                  args=(game["_id"], {"type": "last_inning", "inning": None}, "Last inning cleared."))
    else:
        st.button(f"Make the {ls.ordinal(s.inning)} the last inning", key="gm_last", width="stretch",
                  on_click=cb_event, args=(game["_id"], {"type": "last_inning", "inning": s.inning},
                                           f"The {ls.ordinal(s.inning)} is the last inning."))
    pending = s.pending_outs_limit or s.outs_limit
    def cb_outs(oid, key, current):
        v = st.session_state.get(key)
        if v and v != current:
            cb_event(oid, {"type": "outs", "value": int(v)}, f"{v}-out half-innings from the next half.")
    key = f"gm_outs_{pending}"
    st.segmented_control("Outs per half-inning (from next half)", [2, 3], default=pending, key=key,
                         on_change=cb_outs, args=(game["_id"], key, pending))
    st.divider()
    confirm = st.checkbox("End the game now", key="gm_end_confirm")
    with st.container(key="danger"):
        st.button("End game", key="gm_end", width="stretch", disabled=not confirm,
                  on_click=cb_event, args=(game["_id"], {"type": "end"}))


HOW_RUNNER = {"Normal throw": "throw", "Hit runner": "runner", "Hit the sign": "sign", "Tagged": "tag"}
HOW_BATTER = {"Normal throw": "throw", "Hit runner": "runner", "Tagged": "tag"}


def out_box(s, game, key, batter=False):
    """Optional 'how was he out / who threw it' picker shown under a player who's out."""
    how_opts = HOW_BATTER if batter else HOW_RUNNER
    with st.container(key=f"outbox_{key}"):
        ui.html(f"<div style='display:flex; justify-content:space-between;'>{label('How he was out')}"
                f"<span style='font-size:12px; color:{ui.MUTED};'>Optional</span></div>")
        how = st.pills("How", list(how_opts), key=f"how_{key}", label_visibility="collapsed")
        by = st.pills("Thrown by", fielders(s, game), key=f"by_{key}",
                      format_func=lambda n: f"{n} (P)" if n == s.pitcher else n)
    return {"how": how_opts.get(how), "by": by}


@st.dialog("Ground out")
def go_dialog(s, game):
    n = len(game.get("events", []))
    ends = s.outs + 1 >= s.outs_limit
    ui.html(f"<span style='display:inline-block; padding:2px 8px; border:1px solid #B5AE9F; background:#ECE9E2; "
            f"font-family:{ui.MONO}; font-size:12px; font-weight:600;'>GO · {escape(s.batter)}</span>")
    heading(f"{escape(s.batter)} is out", 24, top=6)
    st.caption("That ends the half-inning." if ends else f"{s.outs + 1} out after this.")
    detail = out_box(s, game, f"go_{n}", batter=True)
    with st.container(key="grid_go"):
        c1, c2 = st.columns([1, 2])
    if c1.button("Back", key="go_back", width="stretch"):
        st.session_state["lv_screen"] = "inplay"
        st.rerun()
    if c2.button("Save ground out", key="go_save", type="primary", width="stretch"):
        event = {"type": "play", "outcome": "GO", "outs_detail": {"B": detail}}
        cb_event(game["_id"], event, f"{s.batter}: ground out.")
        st.rerun()


OUTCOME_GROUPS = [
    ("Hits", [("1B", "Single"), ("2B", "Double"), ("3B", "Triple"), ("HR", "Home run")]),
    ("Outs", [("GO", "Ground out"), ("PO", "Pop out"), ("LO", "Line out"), ("FC", "Fielder's ch.")]),
    ("Multiple outs & sacrifices", [("SF", "Sac fly"), ("DP", "Double play"), ("TP", "Triple play")]),
    ("Fielding", [("E", "Reached on error")]),
]
NEEDS_CONFIRM = {"1B", "2B", "3B", "GO", "PO", "LO", "FC", "SF", "DP", "TP", "E"}


def possible(s, game, outcome):
    try:
        trial = ge.replay(game["setup"], game.get("events", []))
        ge.apply(trial, {"type": "play", "outcome": outcome})
        return True
    except ge.GameError:
        return outcome == "SF" and s.bases[3] is not None and s.outs + 1 < s.outs_limit


def inplay_screen(s, game):
    heading(f"What did {escape(s.batter)} do?", 28, top=6)
    css = []
    for title, items in OUTCOME_GROUPS:
        ui.html(f"<div style='margin-top:10px;'>{label(title)}</div>")
        with st.container(key=f"grid_oc_{title[:4]}"):
            cols = st.columns(4)
            for j, (code, full) in enumerate(items):
                fill, edge = (("#F4EAD2", "#C49A45") if code == "HR" else ("#E3EFE7", "#7FA98F") if code in ge.HITS
                              else ("#E0E8F2", "#7F9BBE") if code == "E" else ("#ECE9E2", "#B5AE9F"))
                css.append(f".st-key-oc_{code} button {{ background:{fill} !important; border-color:{edge} !important; }}")
                if code in NEEDS_CONFIRM and (s.runners() or code == "E"):
                    cb, args = cb_screen, ("runners", code)
                elif code == "GO":
                    cb, args = cb_screen, ("go",)
                else:
                    cb, args = cb_event, (game["_id"], {"type": "play", "outcome": code},
                                          f"{s.batter}: {ls.OUTCOME_NAMES[code].lower()}.")
                cols[j].button(code, key=f"oc_{code}", help=full, width="stretch",
                               disabled=not possible(s, game, code), on_click=cb, args=args)
    st.markdown(f"<style>{''.join(css)}</style>", unsafe_allow_html=True)
    st.write("")
    st.button("Back to pitches", width="stretch", on_click=cb_screen, args=("pitch",))


def runners_screen(s, game):
    outcome = st.session_state.get("lv_outcome")
    ui.html(f"<span style='display:inline-block; padding:2px 8px; border:1px solid #7FA98F; background:#E3EFE7; "
            f"font-family:{ui.MONO}; font-size:12px; font-weight:600;'>{outcome} · {escape(s.batter)}</span>")
    heading("Where did everyone end up?", 26, top=8)
    st.caption("Filled in with the usual result. Tap to change.")

    try:
        default = ge.default_dest(s, outcome)
    except ge.GameError as e:
        st.error(str(e))
        default = {"B": 1}
    n = len(game.get("events", []))
    dest, details = {}, {}
    rows = [(b, s.bases[b]) for b in (3, 2, 1) if s.bases[b]] + [("B", None)]
    for who, r in rows:
        if who == "B":
            name, sub = s.batter, "batter"
            opts = [("Out", "out"), ("1st", 1), ("2nd", 2), ("3rd", 3), ("Scored", "H")]
        else:
            name, sub = r.name + (" (ghost)" if r.ghost else ""), f"was on {ls.ordinal(who)}"
            opts = [("Out", "out"), (f"Held {ls.ordinal(who)}" if who == 3 else "Held", who)]
            opts += [(ls.ordinal(b), b) for b in range(who + 1, 4)] + [("Scored", "H")]
        labels = [o[0] for o in opts]
        value_of = dict(opts)
        default_label = next((lab for lab, v in opts if v == default.get(who)), labels[0])
        ui.html(f"<div style='display:flex; justify-content:space-between; align-items:baseline; margin-top:10px;'>"
                f"<span style='font-size:16px; font-weight:600;'>{escape(name)}</span>"
                f"<span style='font-size:13px; color:{ui.MUTED};'>{sub}</span></div>")
        pick = st.segmented_control(name, labels, default=default_label, key=f"rd_{who}_{outcome}_{n}",
                                    label_visibility="collapsed") or default_label
        dest[who] = value_of[pick]
        if dest[who] == "out":
            details[str(who)] = out_box(s, game, f"{who}_{outcome}_{n}", batter=(who == "B"))

    event = {"type": "play", "outcome": outcome, "dest": {str(k): v for k, v in dest.items()}}
    if details:
        event["outs_detail"] = details
    fl = fielders(s, game)
    if outcome == "E":
        who = st.pills("Error charged to", fl, key=f"rd_err_{n}")
        event["error_fielder"] = who
    elif st.checkbox("There was an error on the play", key=f"rd_haserr_{n}"):
        event["error_fielder"] = st.pills("Error charged to", fl, key=f"rd_err_{n}")

    # Preview the result
    problem = None
    if outcome == "E" and not event.get("error_fielder"):
        problem = "Pick who made the error."
    try:
        after = ge.replay(game["setup"], game.get("events", []) + [event])
        pa = after.plate_appearances[-1]
        runs = len(pa["runs"])
        summary = f"{runs} run{'s' if runs != 1 else ''} · {pa['rbi']} RBI for {escape(s.batter)}"
        score = f"{after.score[1]}–{after.score[2]}"
    except ge.GameError as e:
        problem = problem or str(e)
        summary, score = "", ""
    ui.html(f"<div style='margin-top:16px; padding-top:12px; border-top:2px solid {ui.INK}; display:flex; "
            f"justify-content:space-between; font-size:15px;'><span>{summary}</span>"
            f"<span style='font-family:{ui.MONO}; font-weight:600;'>{score}</span></div>")
    if problem:
        st.warning(problem)
    with st.container(key="grid_confirm"):
        c1, c2 = st.columns([1, 2])
        c1.button("Back", width="stretch", on_click=cb_screen, args=("inplay",))
        c2.button("Confirm", type="primary", width="stretch", disabled=bool(problem),
                  on_click=cb_event, args=(game["_id"], event, f"{s.batter}: {ls.OUTCOME_NAMES[outcome].lower()}."))


def half_prompt(s, game):
    last = s.half_log[-1]
    ui.html("<div style='height:14px;'></div>" + label(f"End of the {'top' if last['half'] == 'top' else 'bottom'} of the {ls.ordinal(last['inning'])}")
            + f"<div style='display:grid; grid-template-columns:1fr auto 1fr; align-items:center; padding:14px 0; margin-top:8px; "
              f"border-top:2px solid {ui.INK}; border-bottom:1px solid {ui.RULE};'><span>Team 1</span>"
              f"<span style='font-family:{ui.SERIF}; font-size:40px; font-weight:500; line-height:1;'>{s.score[1]}"
              f"<span style='margin:0 12px; color:{ui.MUTED};'>–</span>{s.score[2]}</span>"
              f"<span style='text-align:right;'>Team 2</span></div>"
              f"<p style='margin:8px 0 0; font-family:{ui.MONO}; font-size:13px; color:{ui.MUTED};'>"
              f"{last['runs']} R · {last['hits']} H · {last['errors']} E · {last['lob']} LOB · {last['pitches']} pitches</p>")
    heading(f"{'Top' if s.half == 'top' else 'Bottom'} of the {ls.ordinal(s.inning)}", 28, top=18)
    st.markdown(f"Team {s.batting_team} bats, leading off with **{s.batter}**.")
    opts = pitchers_for(s, game)
    pick = st.pills(f"Pitching for Team {s.fielding_team}", opts, default=s.pitcher, key=f"hp_p_{len(s.half_log)}") or s.pitcher
    last_inning = st.checkbox("Make this the last inning", value=bool(s.last_inning and s.last_inning <= s.inning),
                              key=f"hp_last_{len(s.half_log)}", disabled=bool(s.last_inning and s.last_inning <= s.inning))
    changes = []
    if pick != s.pitcher:
        changes.append({"type": "pitcher", "name": pick})
    if last_inning and not (s.last_inning and s.last_inning <= s.inning):
        changes.append({"type": "last_inning", "inning": s.inning})
    text = f"Start the {'top' if s.half == 'top' else 'bottom'} of the {ls.ordinal(s.inning)}"
    if changes:
        st.button(text, type="primary", width="stretch", on_click=cb_events,
                  args=(game["_id"], changes, None, "pitch", len(s.half_log)))
    else:
        st.button(text, type="primary", width="stretch", on_click=cb_ack, args=(game["_id"], len(s.half_log)))


def tied_screen(s, game):
    heading(f"Tied {s.score[1]}–{s.score[2]} after the {ls.ordinal(s.inning)}", 30, top=6)
    st.caption("The last inning is over and it's still tied.")
    ui.html(line_score(s))
    with st.container(key="grid_tied"):
        c1, c2 = st.columns(2)
        c1.button("End as draw", width="stretch", on_click=cb_event, args=(game["_id"], {"type": "end"}))
        c2.button("Play another inning", type="primary", width="stretch", on_click=cb_event,
                  args=(game["_id"], {"type": "continue", "one_inning": True},
                                                                       f"Another inning: the {ls.ordinal(s.inning + 1)} is now the last inning."))
    st.button("Undo last play", key="undo_tied", width="stretch", on_click=cb_undo, args=(game["_id"],))


def final_screen(s, game):
    if s.result == "draw":
        title, tag, tag_color = f"Draw, {s.score[1]}–{s.score[2]}", "Final · draw", ui.DRAW
    else:
        title = f"Team {s.result} wins, {max(s.score.values())}–{min(s.score.values())}"
        tag = f"Walk-off · bot {s.inning}" if s.walk_off else "Final"
        tag_color = ui.WIN
    ui.html(ui.tag(tag, tag_color))
    heading(title, 32, top=10)
    if s.walk_off and s.plate_appearances:
        pa = s.plate_appearances[-1]
        st.caption(f"{pa['batter']}: {ls.OUTCOME_NAMES[pa['outcome']].lower()} off {pa['pitcher']}.")
    ui.html(line_score(s))
    allt = game["setup"].get("all_time") or {}
    if allt.get("name"):
        st.caption(f"{allt['name']} {'batted' if allt.get('role') == 'hitter' else 'pitched'} for both teams, "
                   "so this game doesn't count in his W/L.")
    with st.container(key="grid_final"):
        c1, c2 = st.columns([1, 2])
        with c1.container(key="undo"):
            st.button("Undo play", width="stretch", on_click=cb_undo, args=(game["_id"],))
        c2.button("Save final", type="primary", width="stretch", on_click=cb_save_final, args=(game["_id"],))


def cb_save_final(oid):
    game = games_col.find_one({"_id": oid})
    s = ls.state_for(game)
    if s.status != "final":
        return
    res = games_col.update_one({"_id": oid, "status": "active"}, {"$set": {
        "status": "completed", "team1_score": s.score[1], "team2_score": s.score[2],
        "result": s.result, "line": {"1": s.line[1], "2": s.line[2]},
    }})
    if res.matched_count == 0:
        return          # already saved (double tap or another phone)
    ls.sync_atbats(db, game["game_id"], s)
    refresh_stats()
    st.session_state["flash"] = f"{ui.game_label(game['game_id'])} saved: {s.score[1]}–{s.score[2]}."


def live_screen(game):
    s = ls.state_for(game)
    st.session_state[f"lv_n_{game['_id']}"] = len(game.get("events", []))
    if st.session_state.get("lv_game") != game["_id"]:
        st.session_state["lv_game"] = game["_id"]
        st.session_state["lv_screen"] = "pitch"
    ui.html(scoreboard(s))

    new_half = (s.status == "live" and s.half_log and s._half_pitches == 0 and s.outs == 0 and not s.runners()
                and st.session_state.get(f"ack_{game['_id']}") != len(s.half_log))
    if s.status in ("final", "tied"):
        name = s.status
    elif new_half:
        name = "half"
    else:
        name = st.session_state.get("lv_screen", "pitch")

    # Each screen gets its own freshly keyed container inside a placeholder, so Streamlit swaps
    # the whole screen instead of leaving buttons from the previous screen behind.
    body = st.empty()
    with body.container(key=f"screen_{name}_{len(game.get('events', []))}"):
        if name == "final":
            final_screen(s, game)
        elif name == "tied":
            tied_screen(s, game)
        elif name == "half":
            half_prompt(s, game)
        else:
            ui.html(diamond(s) + batter_block(s, game))
            if name == "inplay":
                inplay_screen(s, game)
            elif name == "go":
                inplay_screen(s, game)
                go_dialog(s, game)
            elif name == "runners":
                runners_screen(s, game)
            elif name in ("runner", "pitcher", "game"):
                menu_screen(s, game, name)
            else:
                pitch_screen(s, game)


# ================================================================ PAGE
if live_game:
    live_screen(live_game)
else:
    setup_screen()

    # ---------------- Players ---------------- #
    heading("Players", 28, top=40)
    with st.form("add_player_form", border=False, clear_on_submit=True):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        new_name = c1.text_input("Add a player", placeholder="Name").strip()
        if c2.form_submit_button("Add player", width="stretch"):
            if not new_name:
                st.error("Name cannot be empty.")
            elif new_name.lower() in {n.lower() for n in player_names}:
                st.warning(f"{new_name} is already on the roster.")
            else:
                players_col.insert_one({"name": new_name})
                refresh_stats()
                st.session_state["flash"] = f"{new_name} added."
                st.rerun()
    if player_names:
        ui.html(f"<div style='margin-top:8px;'>{ui.player_links(player_names, min_width=140)}</div>")