"""Plays the real Scorekeeper page (Streamlit AppTest, no browser) through the special situations:
ghost runners, all-time players, walk-offs, ties and extra innings, caught stealing for the last out,
pitching changes, errors, the ground-out popup, DP/TP/SF rules, undo, settings, two phones, refreshes
and practice mode. Uses an in-memory database (mongomock), so nothing real is touched.

    python -m pytest tests/test_scorekeeper_page.py      (takes a minute or two)
"""
import os
from pathlib import Path

import mongomock
import pytest
from streamlit.testing.v1 import AppTest

import db as dbm
import game_engine as ge

os.environ["ADMIN_PASSWORD"] = "pw"
os.environ.setdefault("MONGO_URI", "mongodb://test")
# Found by name, so numbering the page files (1_Scorekeeper.py, ...) doesn't break the tests
PAGE = str(next((Path(__file__).resolve().parent.parent / "pages").glob("*Scorekeeper.py")))
PLAYERS = ["Edward", "Jason", "Arath", "Carl", "Uriel", "Vera", "Angel"]
_mock = mongomock.MongoClient()


@pytest.fixture(autouse=True)
def fake_database():
    """Every test starts from a fresh in-memory database with the seven players."""
    for name in _mock.list_database_names():
        _mock.drop_database(name)
    _mock[dbm.DB_NAME].players.insert_many([{"name": n} for n in PLAYERS])
    real = dbm.MongoClient
    dbm.MongoClient = lambda *a, **k: _mock
    dbm._client.clear()
    yield
    dbm.MongoClient = real
    dbm._client.clear()


def db():
    return dbm.get_db()


def game():
    return db().games.find_one({"mode": "live"}, sort=[("_id", -1)])


def state():
    g = game()
    return ge.replay(g["setup"], g.get("events") or [])


def phone():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.text_input[0].input("pw"); at.button[0].click().run()
    return at


def errs(at):
    return [e.value for e in at.error] + [str(e.value)[:400] for e in at.exception]


def tap(at, label=None, key=None):
    if key:
        try:
            b = at.button(key=key)
        except KeyError:
            s = state()
            raise AssertionError(f"no {key}. Screen: {labels(at)} | {s.status} {s.half} {s.inning} outs {s.outs}")
    else:
        m = [b for b in at.button if b.label == label]
        if not m:
            raise AssertionError(f"no '{label}' button. On screen: {[b.label for b in at.button]}")
        b = m[0]
    if b.disabled:
        raise AssertionError(f"'{label or key}' is disabled")
    b.click().run()
    e = errs(at)
    if e:
        raise AssertionError(f"after '{label or key}': {e}")
    return at


def group(at, key_start, value):
    g = next(g for g in at.button_group if g.key and g.key.startswith(key_start))
    g.set_value(value).run()
    e = errs(at)
    if e:
        raise AssertionError(f"after picking {value} in {key_start}: {e}")


def back(at):
    if any(b.key == "menu_back" for b in at.button):
        tap(at, key="menu_back")


def labels(at):
    return [b.label for b in at.button]


def start(t1, t2, outs=3, allt=None, role="Hitter", rot=None):
    for g in db().games.find({"status": "active"}):
        db().games.update_one({"_id": g["_id"]}, {"$set": {"status": "abandoned"}})
    at = phone()
    for t, team in ((1, t1), (2, t2)):
        for n in team:
            next(b for b in at.button if b.key and b.key.startswith(f"lu_{t}_") and b.label.split(" · ")[-1] == n).click().run()
    if allt:
        at.selectbox(key="allt_name").set_value(allt).run()
        at.button_group(key="allt_role").set_value(role).run()
    at.button_group(key="setup_outs").set_value(outs).run()
    tap(at, "Play ball")
    return at


def pitches(at, seq):
    for c in seq:
        tap(at, key=f"pitch_{c}")


def play(at, code, dest=None, confirm=True):
    """In play -> outcome; on the runner screen set any non-default destinations, then confirm."""
    tap(at, key="pitch_X")
    tap(at, key=f"oc_{code}")
    if dest:
        for who, lab in dest.items():
            group(at, f"rd_{who}_{code}_", lab)
    if confirm and any(b.label == "Confirm" for b in at.button):
        tap(at, "Confirm")


def start_half(at):
    """Tap through the half-inning prompt if it's showing."""
    b = [b for b in at.button if (b.label or "").startswith("Start the ")]
    if b:
        b[0].click().run()
        assert not errs(at), errs(at)


def three_up(at, outs=3):
    for _ in range(outs):
        pitches(at, "SSS")
    start_half(at)


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


# ---------------------------------------------------------------- gameplay
def test_ghost_runner_a_1_player_team_s_batter_on_base_comes_up_again():
    """Ghost runner: a 1-player team's batter on base comes up again"""
    at = start(["Edward"], ["Carl"])
    pitches(at, "BBBB")                      # Edward walks; bats again with himself on 1st
    s = state()
    check(s.batter == "Edward" and s.bases[1].name == "Edward", "Edward should be on 1st and up")
    pitches(at, "B")
    s = state()
    check(s.bases[1].ghost, "runner on 1st should now be a ghost")
    play(at, "2B")
    s = state()
    check(s.bases[3] and s.bases[3].ghost and s.bases[2].name == "Edward" and not s.bases[2].ghost, f"after double: {s.bases}")


def test_all_time_hitter_bats_for_both_teams_and_can_t_field_or_pitch():
    """All-time hitter bats for both teams and can't field or pitch"""
    at = start(["Edward", "Arath"], ["Carl", "Uriel"], allt="Jason", role="Hitter")
    g = game()
    check("Jason" in g["setup"]["lineups"]["1"] and "Jason" in g["setup"]["lineups"]["2"], "Jason in both lineups")
    tap(at, key="nav_Pitcher")
    check("Jason" not in at.radio(key="pm_pick").options, "all-time hitter offered as pitcher")
    back(at)
    for _ in range(3):
        pitches(at, "SSS")
    start_half(at)
    s = state()
    check(s.pitcher != "Jason", "Jason pitching")


def test_all_time_pitcher_pitches_for_both_teams_and_never_bats():
    """All-time pitcher pitches for both teams and never bats"""
    at = start(["Edward", "Arath"], ["Carl", "Uriel"], allt="Jason", role="Pitcher")
    s = state()
    batters = set()
    for _ in range(4):
        for _ in range(3):
            batters.add(state().batter)
            pitches(at, "SSS")
        start_half(at)
    check("Jason" not in batters, "Jason batted")


def test_walk_off_single_only_the_winning_run_counts():
    """Walk-off single: only the winning run counts"""
    at = start(["Edward"], ["Carl", "Uriel", "Vera"], outs=3)
    pitches(at, "SSS" * 3); start_half(at)            # top 1: 0
    tap(at, key="nav_Game"); tap(at, key="gm_last")   # 1st is the last inning
    back(at)
    play(at, "1B")                                    # Carl 1st
    play(at, "1B", dest={"1": "2nd"})                 # Uriel 1st, Carl 2nd
    play(at, "1B", dest={"2": "Scored", "1": "Scored"})  # Vera singles, two cross
    s = state()
    check(s.status == "final" and s.score == {1: 0, 2: 1} and s.walk_off, f"walk-off single: {s.status} {s.score}")
    check("Save final" in labels(at), "no Save final")
    tap(at, "Save final")
    g = db().games.find_one({"game_id": game()["game_id"]})
    check(g["status"] == "completed" and g["team2_score"] == 1, f"saved {g.get('team2_score')}")


def test_walk_off_home_run_every_run_counts():
    """Walk-off home run: every run counts"""
    at = start(["Edward"], ["Carl", "Uriel"], outs=3)
    pitches(at, "SSS" * 3); start_half(at)
    tap(at, key="nav_Game"); tap(at, key="gm_last"); back(at)
    play(at, "1B")
    play(at, "HR")
    s = state()
    check(s.status == "final" and s.score[2] == 2, f"walk-off HR {s.score}")


def test_home_team_ahead_after_the_top_of_the_last_inning_game_ends_w():
    """Home team ahead after the top of the last inning: game ends without a bottom half"""
    at = start(["Edward"], ["Carl"], outs=2)
    pitches(at, "SSS" * 2); start_half(at)
    play(at, "HR"); pitches(at, "SSS" * 2); start_half(at)        # 0-1 after 1
    tap(at, key="nav_Game"); tap(at, key="gm_last"); back(at)   # 2nd is last
    pitches(at, "SSS" * 2)
    s = state()
    check(s.status == "final" and s.result == "2", f"{s.status} {s.result}")


def test_tie_after_the_last_inning_play_another_inning_the_game_can_s():
    """Tie after the last inning -> Play another inning -> the game can still end"""
    at = start(["Edward"], ["Carl"], outs=2)
    tap(at, key="nav_Game"); tap(at, key="gm_last"); back(at)
    pitches(at, "SSS" * 2); start_half(at)
    pitches(at, "SSS" * 2)
    check(state().status == "tied", "should be tied")
    check({"End as draw", "Play another inning", "Undo last play"} <= set(labels(at)), labels(at))
    tap(at, "Play another inning")
    start_half(at)
    s = state()
    check(s.inning == 2 and s.half == "top", f"inning {s.inning} {s.half}")
    pitches(at, "SSS" * 2); start_half(at)
    pitches(at, "SSS" * 2)
    s = state()
    check(s.status == "tied" and s.inning == 2, f"after a tied extra inning: {s.status} inning {s.inning}")
    check("Play another inning" in labels(at), labels(at))


def test_walk_off_in_the_bottom_of_an_extra_inning_ends_the_game():
    """Walk-off in the bottom of an extra inning ends the game"""
    at = start(["Edward"], ["Carl"], outs=2)
    tap(at, key="nav_Game"); tap(at, key="gm_last")
    pitches(at, "SSS" * 2); start_half(at); pitches(at, "SSS" * 2)
    tap(at, "Play another inning"); start_half(at)
    pitches(at, "SSS" * 2); start_half(at)
    play(at, "HR")
    s = state()
    check(s.status == "final" and s.walk_off and s.result == "2", f"{s.status} {s.result}")
    tap(at, "Save final")


def test_tie_end_as_draw_saves_as_a_draw():
    """Tie -> End as draw saves as a draw"""
    at = start(["Edward"], ["Carl"], outs=2)
    tap(at, key="nav_Game"); tap(at, key="gm_last"); back(at)
    pitches(at, "SSS" * 2); start_half(at); pitches(at, "SSS" * 2)
    tap(at, "End as draw")
    check(state().result == "draw", state().result)
    tap(at, "Save final")
    g = db().games.find_one({"game_id": game()["game_id"]})
    check(g["status"] == "completed" and g["result"] == "draw", g.get("result"))


def test_caught_stealing_for_the_3rd_out_the_batter_leads_off_next_in():
    """Caught stealing for the 3rd out: the batter leads off next inning with a fresh count"""
    at = start(["Edward", "Arath", "Angel"], ["Carl", "Uriel"])
    pitches(at, "SSS")                   # Edward K
    play(at, "1B")                       # Arath on 1st
    pitches(at, "SSS")                   # Angel K: 2 outs, Edward up
    s = state()
    if s.outs != 2 or not s.bases[1]:
        raise AssertionError(f"setup off: outs {s.outs} bases {s.bases}")
    tap(at, key="pitch_B")               # Edward up, 1-0
    tap(at, key="nav_Runner")
    at.radio(key="rm_kind").set_value("Caught stealing").run()
    tap(at, key="rm_save")
    start_half(at)
    s = state()
    check(s.half == "bottom", "half should be over")
    for _ in range(3):
        pitches(at, "SSS")
    start_half(at)
    s = state()
    check(s.batter == "Edward" and s.balls == 0 and s.strikes == 0, f"leadoff {s.batter} {s.balls}-{s.strikes}")


def test_pitching_change_in_the_middle_of_an_at_bat_keeps_the_count():
    """Pitching change in the middle of an at-bat keeps the count"""
    at = start(["Edward", "Arath"], ["Carl", "Uriel"])
    pitches(at, "BS")
    tap(at, key="nav_Pitcher")
    new = next(o for o in at.radio(key="pm_pick").options if o != state().pitcher)
    at.radio(key="pm_pick").set_value(new).run()
    tap(at, key="pm_save")
    s = state()
    check(s.pitcher == new and s.balls == 1 and s.strikes == 1, f"{s.pitcher} {s.balls}-{s.strikes}")
    pitches(at, "SS")
    pa = state().plate_appearances[-1]
    check(pa["pitcher"] == new and pa["outcome"] == "K", f"K credited to {pa['pitcher']}")


def test_reached_on_error_needs_a_fielder_error_with_runners_on():
    """Reached on error needs a fielder; error with runners on"""
    at = start(["Edward", "Arath"], ["Carl", "Uriel"])
    tap(at, key="pitch_X"); tap(at, key="oc_E")
    check(next(b for b in at.button if b.label == "Confirm").disabled, "Confirm enabled without a fielder")
    group(at, "rd_err_", next(g for g in at.button_group if g.key.startswith("rd_err_")).options[0])
    tap(at, "Confirm")
    s = state()
    check(s.bases[1] and s.errors[2] == 1, f"{s.bases} {s.errors}")
    play(at, "1B")
    s = state()
    check(s.bases[2] and s.bases[1], "runners after 1B")


def test_ground_out_with_nobody_on_opens_the_dialog_and_saves():
    """Ground out with nobody on opens the dialog and saves"""
    at = start(["Edward", "Arath"], ["Carl", "Uriel"])
    tap(at, key="pitch_X"); tap(at, key="oc_GO")
    check("Save ground out" in labels(at), f"dialog buttons missing: {labels(at)}")
    tap(at, "Save ground out")
    s = state()
    check(s.outs == 1 and s.plate_appearances[-1]["outcome"] == "GO", f"outs {s.outs}")


def test_ground_out_dialog_with_who_threw_it_details():
    """Ground out dialog with who-threw-it details"""
    at = start(["Edward", "Arath"], ["Carl", "Uriel"])
    tap(at, key="pitch_X"); tap(at, key="oc_GO")
    group(at, "how_go_", "Hit runner")
    group(at, "by_go_", "Uriel")
    tap(at, "Save ground out")
    pa = state().plate_appearances[-1]
    check(pa["out_details"] and pa["out_details"][0]["by"] == "Uriel" and pa["out_details"][0]["how"] == "runner", pa["out_details"])


def test_double_play_and_triple_play():
    """Double play and triple play"""
    at = start(["Edward", "Arath", "Angel", "Vera"], ["Carl", "Uriel"])
    play(at, "1B")
    play(at, "DP")
    s = state()
    check(s.outs == 2 and not any(s.bases.values()), f"DP: outs {s.outs} {s.bases}")
    start_half(at)
    pitches(at, "SSS" * 1)
    s = state()
    if s.half == "top":
        start_half(at)


def test_triple_play_with_two_on_and_nobody_out():
    """Triple play with two on and nobody out"""
    at = start(["Edward", "Arath", "Angel"], ["Carl", "Uriel"])
    play(at, "1B"); play(at, "1B")
    s = state()
    check(s.bases[1] and s.bases[2], f"{s.bases}")
    tap(at, key="pitch_X")
    check(not at.button(key="oc_TP").disabled, "TP disabled with 2 on, 0 out")
    tap(at, key="oc_TP"); tap(at, "Confirm")
    start_half(at)
    s = state()
    check(s.half == "bottom" and s.score[1] == 0, f"{s.half} {s.score}")


def test_sac_fly_allowed_with_a_runner_on_3rd_and_less_than_2_outs_no():
    """Sac fly: allowed with a runner on 3rd and less than 2 outs, not for the last out"""
    at = start(["Edward", "Arath", "Angel"], ["Carl", "Uriel"])
    play(at, "3B")
    tap(at, key="pitch_X")
    check(not at.button(key="oc_SF").disabled, "SF disabled with runner on 3rd, 0 out")
    tap(at, key="oc_SF"); tap(at, "Confirm")
    s = state()
    check(s.score[1] == 1 and s.outs == 1, f"{s.score} {s.outs}")
    pitches(at, "SSS")
    play(at, "3B")
    tap(at, key="pitch_X")
    check(at.button(key="oc_SF").disabled, "SF allowed for the 3rd out")


# ---------------------------------------------------------------- undo and settings
def test_undo_across_a_half_inning_goes_back_into_the_previous_half():
    """Undo across a half-inning goes back into the previous half"""
    at = start(["Edward"], ["Carl"], outs=2)
    pitches(at, "SSS" * 2)
    s = state(); check(s.half == "bottom", s.half)
    start_half(at)
    tap(at, "Undo")
    s = state()
    check(s.half == "top" and s.outs == 1 and s.strikes == 2, f"{s.half} {s.outs} {s.strikes}")
    pitches(at, "S")
    check(state().half == "bottom", "re-ending the half")
    start_half(at)
    check(not errs(at), errs(at))


def test_undo_the_very_first_pitch_then_undo_is_disabled():
    """Undo the very first pitch, then Undo is disabled"""
    at = start(["Edward"], ["Carl"])
    pitches(at, "B")
    tap(at, "Undo")
    check(next(b for b in at.button if b.label == "Undo").disabled, "Undo enabled with no events")


def test_undo_a_final_walk_off_play_then_keep_playing():
    """Undo a final (walk-off) play, then keep playing"""
    at = start(["Edward"], ["Carl"], outs=2)
    pitches(at, "SSS" * 2); start_half(at)
    tap(at, key="nav_Game"); tap(at, key="gm_last"); back(at)
    play(at, "HR")
    check(state().status == "final", "not final")
    tap(at, "Undo play")
    s = state()
    check(s.status == "live" and s.score[2] == 0, f"{s.status} {s.score}")
    pitches(at, "SSS")
    check(not errs(at), errs(at))


def test_changing_outs_per_half_mid_game_starts_with_the_next_half():
    """Changing outs per half mid-game starts with the next half"""
    at = start(["Edward", "Arath"], ["Carl", "Uriel"], outs=3)
    pitches(at, "SSS")
    tap(at, key="nav_Game")
    group(at, "gm_outs_", 2)
    back(at)
    pitches(at, "SSS")
    s = state()
    check(s.half == "top" and s.outs == 2, f"limit changed too early: {s.half} {s.outs}")
    pitches(at, "SSS"); start_half(at)
    pitches(at, "SSS" * 2)
    s = state()
    check(s.half == "top" and s.inning == 2, f"2-out halves not applied: {s.inning} {s.half} outs {s.outs}")


def test_make_last_inning_then_clear_it():
    """Make last inning then clear it"""
    at = start(["Edward"], ["Carl"], outs=2)
    tap(at, key="nav_Game"); tap(at, key="gm_last")
    check(state().last_inning == 1, "not set")
    tap(at, key="nav_Game"); tap(at, key="gm_clear")
    check(state().last_inning is None, "not cleared")
    back(at)
    pitches(at, "SSS" * 2); start_half(at); pitches(at, "SSS" * 2); start_half(at)
    check(state().status == "live" and state().inning == 2, "game should go on")


def test_end_game_early_from_game_settings_needs_the_checkbox_and_sav():
    """End game early from Game settings (needs the checkbox) and save"""
    at = start(["Edward"], ["Carl"])
    play(at, "HR")
    tap(at, key="nav_Game")
    check(at.button(key="gm_end").disabled, "End game enabled before the checkbox")
    at.checkbox(key="gm_end_confirm").check().run()
    tap(at, key="gm_end")
    tap(at, "Save final")
    g = db().games.find_one({"game_id": game()["game_id"]})
    check(g["status"] == "completed" and g["team1_score"] == 1 and g["result"] == "1", f"{g.get('result')}")


def test_steal_home_and_a_steal_can_t_pass_the_runner_ahead():
    """Steal home, and a steal can't pass the runner ahead"""
    at = start(["Edward", "Arath", "Angel"], ["Carl", "Uriel"])
    play(at, "1B"); play(at, "1B")                    # runners 1st and 2nd
    tap(at, key="nav_Runner")
    at.radio(key="rm_runner").set_value(next(o for o in at.radio(key="rm_runner").options if o.startswith("1st"))).run()
    check(not any(r.key == "rm_to_1" for r in at.radio), "runner on 1st offered a steal with 2nd taken")
    at.radio(key="rm_runner").set_value(next(o for o in at.radio(key="rm_runner").options if o.startswith("2nd"))).run()
    at.radio(key="rm_to_2").set_value("H").run()
    tap(at, key="rm_save")
    s = state()
    check(s.score[1] == 1 and s.bases[1] and not s.bases[2], f"{s.score} {s.bases}")


# ---------------------------------------------------------------- safety
def test_two_phones_or_a_double_tap_a_tap_from_a_screen_that_s_behind():
    """Two phones (or a double tap): a tap from a screen that's behind is skipped, not recorded twice"""
    a = start(["Edward"], ["Carl"])
    b = phone()                                   # second phone opens the same game
    pitches(a, "B")
    n = len(game()["events"])
    b.button(key="pitch_B").click().run()         # b's screen still showed 0 events
    check(len(game()["events"]) == n, "stale tap was recorded")
    check(any("changed before that tap" in e for e in [x.value for x in b.error]), f"no stale message: {[x.value for x in b.error]}")
    b.button(key="pitch_S").click().run()         # b is now up to date
    check(len(game()["events"]) == n + 1 and not b.error, "fresh tap after refresh failed")
    s = state(); check(s.balls == 1 and s.strikes == 1, f"{s.balls}-{s.strikes}")


def test_two_phones_undo_from_a_stale_screen_is_skipped():
    """Two phones: Undo from a stale screen is skipped"""
    a = start(["Edward"], ["Carl"])
    b = phone()
    pitches(a, "BB")
    b.run()
    pitches(a, "S")
    next(x for x in b.button if x.label == "Undo").click().run()
    s = state(); check(s.balls == 2 and s.strikes == 1, f"undo from stale phone removed something: {s.balls}-{s.strikes}")


def test_two_phones_both_press_play_ball():
    """Two phones: both press Play ball"""
    for g in db().games.find({"status": "active"}):
        db().games.update_one({"_id": g["_id"]}, {"$set": {"status": "abandoned"}})
    phones = [phone(), phone()]
    for at in phones:
        for t, n in ((1, "Edward"), (2, "Carl")):
            next(x for x in at.button if x.key and x.key.startswith(f"lu_{t}_") and x.label == n).click().run()
    phones[0].button(key=next(x.key for x in phones[0].button if x.label == "Play ball") or "x") if False else None
    next(x for x in phones[0].button if x.label == "Play ball").click().run()
    next(x for x in phones[1].button if x.label == "Play ball").click().run()
    check(db().games.count_documents({"status": "active"}) == 1, "two live games started")


def test_two_phones_both_press_save_final():
    """Two phones: both press Save final"""
    a = start(["Edward"], ["Carl"])
    play(a, "HR")
    tap(a, key="nav_Game"); a.checkbox(key="gm_end_confirm").check().run(); tap(a, key="gm_end")
    b = phone()
    next(x for x in a.button if x.label == "Save final").click().run()
    next(x for x in b.button if x.label == "Save final").click().run()
    check(not errs(b), errs(b))
    gid = game()["game_id"]
    check(db().games.count_documents({"game_id": gid}) == 1 and db().atbats.count_documents({"game_id": gid}) == 1, "duplicate save")


def test_refresh_mid_game_new_session_picks_up_exactly_where_it_was_m():
    """Refresh mid-game (new session) picks up exactly where it was, mid-count"""
    a = start(["Edward", "Arath"], ["Carl"])
    pitches(a, "BBS")
    b = phone()
    md = " ".join(m.value for m in b.markdown)
    check("2–1" in md, "count not shown after refresh")
    pitches(b, "B")
    check(state().balls == 3, "count after refresh")


def test_refresh_on_the_runners_screen_goes_back_to_pitches_without_r():
    """Refresh on the runners screen goes back to pitches without recording anything"""
    a = start(["Edward", "Arath"], ["Carl"])
    play(a, "1B")
    tap(a, key="pitch_X"); tap(a, key="oc_2B")
    n = len(game()["events"])
    b = phone()
    check("Ball" in labels(b), f"refreshed screen: {labels(b)}")
    check(len(game()["events"]) == n, "something was recorded")


def test_practice_mode_never_touches_the_real_games():
    """Practice mode never touches the real games"""
    for g in db().games.find({"status": "active"}):
        db().games.update_one({"_id": g["_id"]}, {"$set": {"status": "abandoned"}})
    before = (db().games.count_documents({}), db().atbats.count_documents({}), db().players.count_documents({}))
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    tap(at, "Try practice mode")
    for t, n in ((1, "Edward"), (2, "Carl")):
        next(x for x in at.button if x.key and x.key.startswith(f"lu_{t}_") and x.label == n).click().run()
    tap(at, "Play ball")
    play(at, "HR"); pitches(at, "SSS" * 3)
    after = (db().games.count_documents({}), db().atbats.count_documents({}), db().players.count_documents({}))
    check(before == after, f"real database changed: {before} -> {after}")
    tap(at, key="leave_practice")
    check(any(x.label == "Log in" for x in at.button) or at.text_input, "not back at login")