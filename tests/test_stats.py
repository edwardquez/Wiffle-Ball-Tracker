import math

import pandas as pd
import pytest

import stats

PLAYERS = pd.DataFrame({"name": ["Edward", "Arath", "Angel", "Carl", "Uriel", "Vera", "Jason"]})


def old_game(game_id, oid, t1, t2, s1, s2, date="2025-06-25"):
    return {"_id": oid, "game_id": game_id, "date": date, "team1": ", ".join(t1), "team2": ", ".join(t2),
            "team1_players": ",".join(t1), "team2_players": ", ".join(t2),
            "team1_score": s1, "team2_score": s2, "status": "completed"}


def ab(oid, game_id, batter, pitcher, outcome, rbi=0, outs=0):
    return {"_id": oid, "game_id": game_id, "batter": batter, "pitcher": pitcher, "outcome": outcome,
            "rbi": rbi, "outs_recorded": outs, "strikes": 1, "balls": 1, "inning": "Top 1"}


def live_game(game_id, oid, events, all_time=None, l1=("Edward", "Arath", "Angel"), l2=("Carl", "Uriel", "Vera")):
    l1, l2 = list(l1), list(l2)
    shared = all_time["name"] if all_time and all_time["role"] == "hitter" else None
    t1 = [p for p in l1 if p != shared]
    t2 = [p for p in l2 if p != shared]
    return {"_id": oid, "game_id": game_id, "date": "2026-10-16", "mode": "live", "status": "completed",
            "team1": ", ".join(t1), "team2": ", ".join(t2), "team1_players": ",".join(t1),
            "team2_players": ", ".join(t2), "team1_score": None, "team2_score": None,
            "setup": {"lineups": {"1": l1, "2": l2}, "rotations": {"1": t1, "2": t2},
                      "outs_per_half": 3, "all_time": all_time},
            "events": events}


def P(*r):
    return [{"type": "pitch", "result": x} for x in r]


def play(outcome, dest=None, **kw):
    e = {"type": "play", "outcome": outcome, **kw}
    if dest:
        e["dest"] = dest
    return [e]


K = P("S", "S", "S")
BB = P("B", "B", "B", "B")


def league(games, atbats):
    return stats.League(PLAYERS, pd.DataFrame(games), pd.DataFrame(atbats))


# ---------------------------------------------------------------- hitting definitions

def test_walks_and_sac_flies_are_not_at_bats():
    # Jason vs Uriel: 3 walks and 2 outs -> 0-for-2, OBP .600
    rows = [ab(i, "Game_1", "Jason", "Uriel", o, outs=1 if o != "Walk" else 0)
            for i, o in enumerate(["Walk", "Walk", "Walk", "Ground Out", "Pop Out"])]
    lg = league([old_game("Game_1", 1, ["Edward"], ["Jason"], 1, 0)], rows)
    b = stats.batting(lg.pa).loc["Jason"]
    assert (b.PA, b.AB, b.H) == (5, 2, 0)
    assert b.AVG == 0 and b.OBP == pytest.approx(0.6)


def test_slg_obp_ops_with_sac_fly():
    rows = [ab(1, "G", "Carl", "Vera", "Single"), ab(2, "G", "Carl", "Vera", "Home Run", rbi=1),
            ab(3, "G", "Carl", "Vera", "Sacrifice Fly", rbi=1, outs=1), ab(4, "G", "Carl", "Vera", "Strike Out", outs=1)]
    lg = league([old_game("G", 1, ["Carl"], ["Vera"], 2, 0)], rows)
    b = stats.batting(lg.pa).loc["Carl"]
    assert b.AB == 3 and b.AVG == pytest.approx(2 / 3)
    assert b.OBP == pytest.approx(2 / 4)        # (H+BB)/(AB+BB+SF) = 2/(3+0+1)
    assert b.SLG == pytest.approx(5 / 3) and b.OPS == pytest.approx(0.5 + 5 / 3)
    assert b["K%"] == pytest.approx(0.25) and b.RBI == 2
    assert math.isnan(b.R)                     # older games don't know who scored


def test_error_and_fielders_choice_count_as_at_bats():
    rows = [ab(1, "G", "Vera", "Carl", "Reached on Error"), ab(2, "G", "Vera", "Carl", "Fielder's Choice", outs=1)]
    b = stats.batting(league([old_game("G", 1, ["Vera"], ["Carl"], 0, 0)], rows).pa).loc["Vera"]
    assert b.AB == 2 and b.H == 0


def test_no_at_bats_gives_blank_rates_not_zero():
    rows = [ab(1, "G", "Angel", "Carl", "Walk")]
    b = stats.batting(league([old_game("G", 1, ["Angel"], ["Carl"], 0, 0)], rows).pa).loc["Angel"]
    assert math.isnan(b.AVG) and b.OBP == 1


# ---------------------------------------------------------------- pitching

def test_old_games_use_rbi_allowed_as_er():
    rows = [ab(1, "G", "Carl", "Edward", "Home Run", rbi=2), ab(2, "G", "Vera", "Edward", "Ground Out", outs=1),
            ab(3, "G", "Uriel", "Edward", "Strike Out", outs=1), ab(4, "G", "Vera", "Edward", "Pop Out", outs=1)]
    p = stats.pitching(league([old_game("G", 1, ["Edward"], ["Carl"], 0, 2)], rows).pa).loc["Edward"]
    assert p.IP == 1 and p.ER == 2 and p.ERA == 18 and p.WHIP == 1 and p.K == 1
    assert math.isnan(p.R)              # runs allowed: not recorded for older games
    assert p.P == 8                     # pitches: 4 at-bats x (1 strike + 1 ball) as saved


def test_reached_on_error_is_not_a_hit_allowed():
    rows = [ab(1, "G", "Carl", "Edward", "Reached on Error"), ab(2, "G", "Carl", "Edward", "Ground Out", outs=1)]
    p = stats.pitching(league([old_game("G", 1, ["Edward"], ["Carl"], 0, 0)], rows).pa).loc["Edward"]
    assert p.H == 0


def test_live_earned_runs_unearned_and_inherited():
    # Top 1: Edward reaches on error (Carl), Arath HR -> 2 runs, both unearned for Carl? Edward's is
    # unearned (reached on error) and Arath's is earned (inning not yet "over": 0 outs + 1 phantom).
    ev = play("E", error_fielder="Carl") + play("HR")
    # then Angel singles, Uriel relieves, Edward (ghost-free: Edward batting again) homers:
    # Angel's run is charged to Carl (inherited), Edward's to Uriel
    ev += play("1B") + [{"type": "pitcher", "name": "Uriel"}] + play("HR")
    lg = league([live_game("Game_7", 7, ev)], [])
    p = stats.pitching(lg.pa, lg.runs, lg.pitches)
    assert p.loc["Carl", "R"] == 3 and p.loc["Carl", "ER"] == 2      # Edward (unearned), Arath, Angel
    assert p.loc["Uriel", "R"] == 1 and p.loc["Uriel", "ER"] == 1
    b = stats.batting(lg.pa, lg.runs)
    assert b.loc["Edward", "R"] == 2 and b.loc["Arath", "R"] == 1 and b.loc["Angel", "R"] == 1
    f = stats.fielding(lg.fielding)
    assert f.loc["Carl", "E"] == 1


def test_steal_of_home_run_counts_for_runner_and_pitcher():
    ev = play("3B") + [{"type": "runner", "kind": "SB", "base": 3, "to": "H"}]
    lg = league([live_game("Game_7", 7, ev)], [])
    assert stats.batting(lg.pa, lg.runs).loc["Edward", "R"] == 1
    assert stats.pitching(lg.pa, lg.runs, lg.pitches).loc["Carl", "ER"] == 1


def test_pitch_counts_and_strike_percent():
    ev = P("B", "S", "F", "B", "B", "B")      # walk: 6 pitches, 2 strikes
    lg = league([live_game("Game_7", 7, ev)], [])
    p = stats.pitching(lg.pa, lg.runs, lg.pitches).loc["Carl"]
    assert p.P == 6 and p.STR == 2 and p["STR%"] == pytest.approx(2 / 6)


def test_throw_outs_by_type():
    ev = play("GO", outs_detail={"B": {"how": "runner", "by": "Carl"}})
    ev += play("2B") + play("1B", {2: "out"}, outs_detail={"2": {"how": "sign", "by": "Vera"}})
    ev += [{"type": "runner", "kind": "CS", "base": 1, "how": "tag", "by": "Vera"}]
    lg = league([live_game("Game_7", 7, ev)], [])
    f = stats.fielding(lg.fielding, names=lg.names)
    assert f.loc["Carl", "TO"] == 1 and f.loc["Carl", "TO Hit runner"] == 1
    assert f.loc["Vera", "TO"] == 2 and f.loc["Vera", "TO Hit the sign"] == 1 and f.loc["Vera", "TO Tagged"] == 1
    assert f.loc["Edward", "TO"] == 0


# ---------------------------------------------------------------- old + live together

def test_live_rows_in_atbats_are_not_double_counted():
    ev = play("1B") + K
    g = live_game("Game_7", 7, ev)
    synced = [{"_id": 100, "game_id": "Game_7", "batter": "Edward", "pitcher": "Carl", "outcome": "Single",
               "rbi": 0, "outs_recorded": 0, "live": True}]
    lg = league([old_game("Game_1", 1, ["Edward"], ["Carl"], 1, 0), g],
                [ab(1, "Game_1", "Edward", "Carl", "Double")] + synced)
    b = stats.batting(lg.pa).loc["Edward"]
    assert b.PA == 2 and b.H == 2          # one old double + one live single, not three


def test_subset_by_game_and_matchup():
    rows = [ab(1, "A", "Edward", "Carl", "Single"), ab(2, "B", "Edward", "Vera", "Home Run", rbi=1)]
    lg = league([old_game("A", 1, ["Edward"], ["Carl"], 0, 0), old_game("B", 2, ["Edward"], ["Vera"], 1, 0)], rows)
    pa, *_ = lg.subset(games=["B"])
    assert stats.batting(pa).loc["Edward", "HR"] == 1 and stats.batting(pa).loc["Edward", "H"] == 1
    pa, *_ = lg.subset(batter="Edward", pitcher="Carl")
    assert stats.batting(pa).loc["Edward", "HR"] == 0


# ---------------------------------------------------------------- records

def test_records_half_win_draws_and_all_time_hitter():
    ev = play("HR") + K * 3 + K * 3 + [{"type": "end"}]
    g = live_game("Game_7", 7, ev, all_time={"name": "Jason", "role": "hitter"},
                  l1=("Edward", "Arath", "Jason"), l2=("Carl", "Uriel", "Jason"))
    g["team1_score"], g["team2_score"] = 1, 0
    games = pd.DataFrame([old_game("Game_1", 1, ["Edward", "Vera"], ["Carl", "Arath"], 2, 2), g])
    r = stats.records(games)
    assert (r.loc["Edward", "W"], r.loc["Edward", "D"], r.loc["Edward", "GP"]) == (1, 1, 2)
    assert r.loc["Edward", "Pct"] == pytest.approx(0.75)
    assert r.loc["Jason", "GP"] == 0 and r.loc["Jason", "Both"] == 1


def test_ip_text():
    assert stats.ip_text(47) == "15.2" and stats.ip_text(0) == "0.0"


def test_live_players_include_whole_lineups():
    lg = league([live_game("Game_7", 7, K)], [])
    assert lg.live_players == {"Edward", "Arath", "Angel", "Carl", "Uriel", "Vera"}


# ---------------------------------------------------------------- WAR

def _war_league():
    rows = [ab(1, "G", "Carl", "Edward", "Home Run", rbi=1), ab(2, "G", "Carl", "Edward", "Double"),
            ab(3, "G", "Vera", "Edward", "Strike Out", outs=1), ab(4, "G", "Vera", "Edward", "Ground Out", outs=1),
            ab(5, "G", "Edward", "Carl", "Walk"), ab(6, "G", "Edward", "Carl", "Strike Out", outs=1),
            ab(7, "G", "Edward", "Carl", "Pop Out", outs=1), ab(8, "G", "Vera", "Edward", "Pop Out", outs=1)]
    return league([old_game("G", 1, ["Edward"], ["Carl", "Vera"], 0, 1)], rows)


def test_war_parts_are_relative_to_average():
    lg = _war_league()
    for method in ("fip", "ra"):
        w = stats.war(lg, method)
        assert abs(w["Batting runs"].sum()) < 1e-9       # league average is zero by construction
        assert abs(w["Pitching runs"].sum()) < 1e-9
        assert w.loc["Carl", "Batting runs"] > 0 > w.loc["Vera", "Batting runs"]


def test_war_converts_runs_with_league_runs_per_game():
    lg = _war_league()
    assert stats.runs_per_win(lg) == 3.0                  # 1 run/game, floored at 3
    w = stats.war(lg)
    assert w.loc["Carl", "WAA"] == pytest.approx(w.loc["Carl", "Runs"] / 3.0)
    assert w.loc["Carl", "WAR"] == pytest.approx((w.loc["Carl", "Runs"] + w.loc["Carl", "Replacement runs"]) / 3.0)


def test_fip_ignores_balls_in_play_but_ra_does_not():
    lg = _war_league()
    fip, ra = stats.war(lg, "fip"), stats.war(lg, "ra")
    # Edward gave up a HR (bad in both); Carl gave up a walk but no runs
    assert fip.loc["Edward", "Pitching runs"] < 0 and ra.loc["Edward", "Pitching runs"] < 0
    assert ra.loc["Carl", "Pitching runs"] > 0


def test_fielding_runs_from_live_games():
    ev = play("GO", outs_detail={"B": {"how": "runner", "by": "Carl"}}) + play("E", error_fielder="Uriel")
    lg = league([live_game("Game_7", 7, ev)], [])
    w = stats.war(lg)
    assert w.loc["Carl", "Fielding runs"] > 0 > w.loc["Uriel", "Fielding runs"]
    assert abs(w["Fielding runs"].sum()) < 1e-9


def test_pitcher_charged_even_without_recording_an_out():
    rows = [ab(1, "G", "Carl", "Edward", "Home Run", rbi=1), ab(2, "G", "Vera", "Arath", "Strike Out", outs=1)]
    lg = league([old_game("G", 1, ["Edward", "Arath"], ["Carl", "Vera"], 0, 1)], rows)
    assert stats.war(lg, "ra").loc["Edward", "Pitching runs"] < 0
    assert stats.war(lg, "fip").loc["Edward", "Pitching runs"] < 0


def test_blend_is_pure_fip_with_only_old_games():
    lg = _war_league()
    assert stats.war(lg)["Pitching runs"].round(9).equals(stats.war(lg, "fip")["Pitching runs"].round(9))


def test_blend_moves_halfway_to_runs_allowed_with_all_live_innings():
    # one live game only: every inning is live -> 50/50, and the league still sums to zero
    ev = play("HR") + K + K + K + K + K + K
    lg = league([live_game("Game_7", 7, ev)], [])
    fip, ra, blend = stats.war(lg, "fip"), stats.war(lg, "ra"), stats.war(lg)
    mid = 0.5 * fip["Pitching runs"] + 0.5 * ra["Pitching runs"]
    assert blend["Pitching runs"].round(9).equals(mid.round(9))
    assert abs(blend["Pitching runs"].sum()) < 1e-9


# ---------------------------------------------------------------- review fixes

def test_caught_stealing_and_pickoffs_count_in_innings():
    # Top 1: single, caught stealing, two strikeouts -> Carl got 3 outs (1 of them on the bases)
    ev = play("1B") + [{"type": "runner", "kind": "CS", "base": 1}] + K + K
    lg = league([live_game("Game_7", 7, ev)], [])
    p = lg.pitching().loc["Carl"]
    assert p["OUTS"] == 3 and p["IP"] == pytest.approx(1.0)
    assert stats.pitching(lg.pa).loc["Carl", "OUTS"] == 2       # without runner outs (old way)
    assert lg.pitcher_outs["Carl"] == 3
    # one matchup: runner outs aren't the batter's, so they're left out
    assert lg.pitching(batter="Arath").loc["Carl", "OUTS"] == 1


def test_pickoff_only_pitcher_still_gets_a_line():
    ev = play("1B") + [{"type": "pitcher", "name": "Uriel"}, {"type": "runner", "kind": "PO", "base": 1}]
    lg = league([live_game("Game_7", 7, ev)], [])
    p = lg.pitching()
    assert p.loc["Uriel", "OUTS"] == 1 and p.loc["Uriel", "BF"] == 0


def test_all_time_pitcher_counts_in_both():
    ev = play("HR") + K * 3 + K * 3 + [{"type": "end"}]
    g = live_game("Game_7", 7, ev, all_time={"name": "Jason", "role": "pitcher"})
    g["setup"]["rotations"] = {"1": ["Edward", "Jason"], "2": ["Carl", "Jason"]}
    g["team1_score"], g["team2_score"] = 1, 0
    r = stats.records(pd.DataFrame([g]))
    assert r.loc["Jason", "Both"] == 1 and r.loc["Jason", "GP"] == 0


def test_scoring_feed_has_every_live_run_in_order():
    # Arath reaches on an error and Edward scores (0 RBI); Angel's double scores Arath; Carl steals home
    ev = (play("1B") + play("E", {1: "H", "B": 1}, error_fielder="Uriel") + play("2B", {1: "H", "B": 2})
          + K + K + K
          + play("3B") + [{"type": "runner", "kind": "SB", "base": 3, "to": "H"}])
    lg = league([live_game("Game_7", 7, ev)], [])
    sc = lg.scoring
    assert list(sc["player"]) == ["Arath", "Angel", "Carl"]
    assert list(sc["runs"]) == [1, 1, 1] and list(sc["rbi"]) == [0, 1, 0]
    assert list(sc["outcome"])[-1] == "SB home" and list(sc["team"]) == [1, 1, 2]


# ---------------------------------------------------------------- replacement level and seasons

def test_replacement_credit_adds_up_to_the_setting_per_game_played():
    lg = _war_league()                      # 3 players x 1 game
    w = stats.war(lg)
    rep_wins = w["Replacement runs"].sum() / stats.runs_per_win(lg)
    assert rep_wins == pytest.approx(stats.REPLACEMENT_WAR_PER_GAME * w["G"].sum())
    # the league is no longer centered on zero: it sits above it by the replacement credit
    assert w["WAR"].sum() == pytest.approx(rep_wins)
    assert w["WAA"].sum() == pytest.approx(0, abs=1e-9)


def test_hitter_who_never_pitches_gets_only_the_batting_half():
    # Vera bats but never pitches; Edward and Carl both bat and pitch
    lg = _war_league()
    w = stats.war(lg)
    credit = stats.REPLACEMENT_WAR_PER_GAME * stats.runs_per_win(lg)
    assert w.loc["Vera", "IP"] == 0
    pa_per_game = w["PA"].sum() / w["G"].sum()
    assert w.loc["Vera", "Replacement runs"] == pytest.approx(0.5 * credit * w.loc["Vera", "PA"] / pa_per_game)


def _two_seasons():
    rows = [ab(1, "A", "Edward", "Carl", "Home Run", rbi=1), ab(2, "A", "Carl", "Edward", "Strike Out", outs=1),
            ab(3, "B", "Edward", "Carl", "Strike Out", outs=1), ab(4, "B", "Carl", "Edward", "Double")]
    games = [old_game("A", 1, ["Edward"], ["Carl"], 1, 0, date="2025-06-01"),
             old_game("B", 2, ["Edward"], ["Carl"], 0, 1, date="2026-06-01")]
    return league(games, rows)


def test_career_war_is_the_sum_of_seasons():
    lg = _two_seasons()
    assert stats.seasons(lg) == [2026, 2025]
    by = stats.war_by_season(lg)
    career = stats.war(lg)
    for name in ("Edward", "Carl"):
        assert career.loc[name, "WAR"] == pytest.approx(by.loc[[name], "WAR"].sum())
        assert career.loc[name, "G"] == 2
    # each season is against its own league: Edward was the better hitter in 2025, Carl in 2026
    assert stats.war(lg, season=2025).loc["Edward", "Batting runs"] > 0
    assert stats.war(lg, season=2026).loc["Carl", "Batting runs"] > 0


def test_season_with_no_games_for_a_player_is_skipped():
    lg = _two_seasons()
    lg.games.loc[lg.games["game_id"] == "B", "team1_players"] = "Edward"
    by = stats.war_by_season(lg)
    assert set(by[by["Season"] == 2026].index) == {"Edward", "Carl"}
    assert "Vera" not in by.index


def test_old_games_pitch_counts_come_from_the_saved_count():
    rows = [ab(1, "G", "Vera", "Carl", "Strike Out", outs=1), ab(2, "G", "Uriel", "Carl", "Single")]
    rows[0]["strikes"], rows[0]["balls"] = 3, 2          # struck out on 3-2
    rows[1]["strikes"], rows[1]["balls"] = 1, 0          # singled on a 1-0 count (count before contact)
    p = league([old_game("G", 1, ["Vera", "Uriel"], ["Carl"], 0, 0)], rows).pitching().loc["Carl"]
    assert p["P"] == 6 and p["STR"] == 4 and p["STR%"] == pytest.approx(4 / 6)


# ---------------------------------------------------------------- Visualizations data

def test_runners_on_from_old_and_live_games():
    rows = [ab(1, "G", "Edward", "Carl", "Single"), ab(2, "G", "Arath", "Carl", "Home Run", rbi=2)]
    rows[0]["runners_on"], rows[1]["runners_on"] = 0, 1
    ev = play("1B") + play("HR")                  # live: Edward singles (bases empty), Arath homers (1 on)
    lg = league([old_game("G", 1, ["Edward", "Arath"], ["Carl"], 2, 0), live_game("Game_7", 7, ev)], rows)
    sp = stats.runner_splits(lg.pa)
    assert sp.loc["Arath", "PA on"] == 2 and sp.loc["Edward", "PA empty"] == 2
    assert sp.loc["Arath", "SLG on"] == 4.0


def test_outcome_mix_shares_add_to_one():
    rows = [ab(i, "G", "Edward", "Carl", o) for i, o in
            enumerate(["Strike Out", "Walk", "Single", "Home Run", "Ground Out", "Reached on Error"])]
    m = stats.outcome_mix(league([old_game("G", 1, ["Edward"], ["Carl"], 0, 0)], rows).pa).loc["Edward"]
    assert m["PA"] == 6 and m.drop("PA").sum() == pytest.approx(1)
    assert m["In play, no hit"] == pytest.approx(2 / 6)      # ground out + reached on error


def test_matchup_grid_cells():
    rows = [ab(1, "G", "Edward", "Carl", "Single"), ab(2, "G", "Edward", "Carl", "Strike Out", outs=1),
            ab(3, "G", "Edward", "Vera", "Walk")]
    v, n = stats.matchup_grid(league([old_game("G", 1, ["Edward"], ["Carl", "Vera"], 0, 0)], rows).pa)
    assert v.loc["Edward", "Carl"] == 0.5 and n.loc["Edward", "Carl"] == 2
    assert v.loc["Edward", "Vera"] == 1.0


def test_teammate_records_pairs():
    games = pd.DataFrame([old_game("A", 1, ["Edward", "Vera"], ["Carl", "Arath"], 3, 1),
                          old_game("B", 2, ["Edward", "Vera"], ["Carl", "Arath"], 2, 2),
                          old_game("C", 3, ["Edward", "Carl"], ["Vera", "Arath"], 0, 1)])
    t = stats.teammate_records(games).set_index(["a", "b"])
    assert (t.loc[("Edward", "Vera"), "GP"], t.loc[("Edward", "Vera"), "Pct"]) == (2, 0.75)
    assert t.loc[("Carl", "Edward"), "L"] == 1


def test_war_race_ends_at_career_war():
    lg = _two_seasons()
    games, values = stats.war_race(lg)
    assert list(games["n"]) == [1, 2]
    assert values.iloc[-1]["Edward"] == pytest.approx(stats.war(lg).loc["Edward", "WAR"])


def test_outcome_mix_for_pitchers():
    rows = [ab(1, "G", "Vera", "Carl", "Strike Out", outs=1), ab(2, "G", "Uriel", "Carl", "Home Run", rbi=1)]
    m = stats.outcome_mix(league([old_game("G", 1, ["Vera", "Uriel"], ["Carl"], 1, 0)], rows).pa, by="pitcher")
    assert m.loc["Carl", "PA"] == 2 and m.loc["Carl", "Strikeout"] == 0.5 and m.loc["Carl", "Home run"] == 0.5


def test_inning_runs_old_and_live():
    rows = [ab(1, "G", "Vera", "Carl", "Home Run", rbi=2), ab(2, "G", "Vera", "Carl", "Strike Out", outs=1),
            ab(3, "G", "Vera", "Carl", "Ground Out", outs=1), ab(4, "G", "Vera", "Carl", "Pop Out", outs=1)]
    for r in rows:
        r["inning"] = "Bottom 2"
    ev = play("HR") + K + K + K                    # live: Carl gives up a run in the 1st, 3 outs
    lg = league([old_game("G", 1, ["Vera"], ["Carl"], 2, 0), live_game("Game_7", 7, ev)], rows)
    rate, ip = stats.inning_runs(lg)
    assert ip.loc["Carl", 1] == 1 and rate.loc["Carl", 1] == 1.0
    assert ip.loc["Carl", 2] == 1 and rate.loc["Carl", 2] == 2.0
    assert stats.inning_number("Top 11") == 11 and stats.inning_number(None) is None


# ---------------------------------------------------------------- advanced stats

def _adv_league():
    rows = [ab(1, "G", "Edward", "Carl", "Home Run", rbi=1), ab(2, "G", "Edward", "Carl", "Walk"),
            ab(3, "G", "Edward", "Carl", "Strike Out", outs=1), ab(4, "G", "Edward", "Carl", "Single"),
            ab(5, "G", "Vera", "Edward", "Ground Out", outs=1), ab(6, "G", "Vera", "Edward", "Strike Out", outs=1),
            ab(7, "G", "Vera", "Edward", "Double", rbi=1), ab(8, "G", "Vera", "Edward", "Pop Out", outs=1)]
    return league([old_game("G", 1, ["Edward"], ["Carl", "Vera"], 1, 1)], rows)


def test_woba_iso_babip():
    b = _adv_league().advanced_batting()
    e = b.loc["Edward"]                      # HR, BB, K, 1B in 4 PA (3 AB)
    assert e["wOBA"] == pytest.approx((2.10 + 0.69 + 0.89) / 4)
    assert e["ISO"] == pytest.approx(e["SLG"] - e["AVG"])
    assert e["BABIP"] == pytest.approx(1 / 1)          # (H - HR) / (AB - K - HR + SF) = 1 / 1
    v = b.loc["Vera"]                        # GO, K, 2B, PO: BABIP = 1 / 3
    assert v["BABIP"] == pytest.approx(1 / 3)


def test_wrc_plus_is_centered_on_the_league():
    lg = _adv_league()
    b = lg.advanced_batting()
    weights = (b["wRC+"] * (b["AB"] + b["BB"] + b["SF"])).sum() / (b["AB"] + b["BB"] + b["SF"]).sum()
    assert weights == pytest.approx(100)              # PA-weighted average hitter = 100
    assert b.loc["Edward", "wRC+"] > 100 > b.loc["Vera", "wRC+"]


def test_fip_era_minus_kbb_opp_ops():
    p = _adv_league().advanced_pitching()
    lg_era = p["ER"].sum() * 9 / p["IP"].sum()
    # league FIP equals league ERA by construction
    assert (p["FIP"] * p["IP"]).sum() / p["IP"].sum() == pytest.approx(lg_era)
    assert p.loc["Carl", "ERA-"] == pytest.approx(100 * p.loc["Carl", "ERA"] / lg_era)
    assert p.loc["Edward", "K-BB%"] == pytest.approx((1 - 0) / 4)
    assert p.loc["Carl", "OPP_OPS"] > p.loc["Edward", "OPP_OPS"]


# ---------------------------------------------------------------- awards and records

def test_single_game_records_and_ties():
    rows = [ab(1, "A", "Edward", "Carl", "Home Run", rbi=1), ab(2, "A", "Edward", "Carl", "Home Run", rbi=2),
            ab(3, "B", "Vera", "Carl", "Home Run", rbi=1), ab(4, "B", "Vera", "Carl", "Home Run", rbi=1)]
    lg = league([old_game("A", 1, ["Edward"], ["Carl"], 3, 0), old_game("B", 2, ["Vera"], ["Carl"], 2, 0)], rows)
    rec = {label: holders for label, _, holders in stats.single_game_records(lg)}
    assert sorted(h[0] for h in rec["Most home runs"]) == ["Edward", "Vera"]       # tied at 2
    assert rec["Most RBI"] == [("Edward", "A", 3.0)]


def test_hitting_streak_skips_games_not_played():
    rows = [ab(1, "A", "Edward", "Carl", "Single"), ab(2, "C", "Edward", "Carl", "Single"),
            ab(3, "B", "Vera", "Carl", "Strike Out", outs=1), ab(4, "D", "Edward", "Carl", "Strike Out", outs=1)]
    games = [old_game(g, i, ["Edward", "Vera"], ["Carl"], 0, 0) for i, g in enumerate("ABCD", start=1)]
    s = {name: (longest, cur) for longest, name, cur in stats.hitting_streaks(league(games, rows))}
    assert s["Edward"] == (2, 0)          # A, (didn't bat in B), C -> 2; then hitless in D
    assert s["Vera"] == (0, 0)


def test_season_awards_and_milestones():
    lg = _two_seasons()
    aw = stats.season_awards(lg, 2026)
    assert aw["MVP"][0][0] in ("Edward", "Carl") and aw["_improved_from"] == 2025
    assert "Glove" not in aw                 # no live fielding data
    m = stats.milestones(lg)
    assert all(goal > cur for _, _, cur, goal in m)