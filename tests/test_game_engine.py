import pytest

from game_engine import replay, default_dest, GameError

T1 = ["Edward", "Arath", "Angel"]
T2 = ["Carl", "Uriel", "Vera"]


def setup(outs=3, l1=None, l2=None, r1=None, r2=None, all_time=None):
    return {
        "lineups": {1: l1 or T1, 2: l2 or T2},
        "rotations": {1: r1 or T1, 2: r2 or T2},
        "outs_per_half": outs,
        "all_time": all_time,
    }


def P(*results):            # pitches
    return [{"type": "pitch", "result": r} for r in results]


def play(outcome, dest=None, **kw):
    e = {"type": "play", "outcome": outcome}
    if dest:
        e["dest"] = dest
    e.update(kw)
    return [e]


K = P("S", "S", "S")
BB = P("B", "B", "B", "B")


def three_outs():
    return K + K + K


def names(state):
    return {b: (r.name + ("*" if r.ghost else "")) if r else None for b, r in state.bases.items()}


# ---------------------------------------------------------------- count rules

def test_foul_with_two_strikes_keeps_count():
    s = replay(setup(), P("S", "F", "F", "F", "F"))
    assert (s.balls, s.strikes, s.outs) == (0, 2, 0)
    s = replay(setup(), P("F", "F", "S"))
    assert s.outs == 1 and s.strikes == 0          # foul, foul, strike three


def test_walk_and_strikeout_from_pitches():
    s = replay(setup(), BB)
    assert s.plate_appearances[-1]["outcome"] == "BB" and names(s)[1] == "Edward"
    s = replay(setup(), K)
    assert s.plate_appearances[-1]["outcome"] == "K" and s.outs == 1
    assert s.plate_appearances[-1]["pitches"] == "SSS"


def test_bases_loaded_walk_forces_run_with_rbi():
    s = replay(setup(l1=["A", "B", "C", "D"], r2=["Carl"]), BB * 4)
    assert s.score[1] == 1
    pa = s.plate_appearances[-1]
    assert pa["rbi"] == 1 and pa["runs"][0]["player"] == "A" and pa["runs"][0]["earned"]


def test_walk_only_moves_forced_runners():
    # runner on 2nd only, walk: he stays
    ev = play("2B") + BB
    s = replay(setup(), ev)
    assert names(s) == {1: "Arath", 2: "Edward", 3: None}


def test_cannot_record_walk_as_a_play():
    with pytest.raises(GameError):
        replay(setup(), play("BB"))


# ---------------------------------------------------------------- outs / innings

def test_half_inning_flips_after_three_outs_and_rotation():
    s = replay(setup(), three_outs())
    assert (s.inning, s.half, s.outs) == (1, "bottom", 0)
    assert s.pitcher == "Edward"                 # Team 1's first pitcher
    s = replay(setup(), three_outs() * 2)
    assert (s.inning, s.half) == (2, "top")
    assert s.pitcher == "Uriel"                  # Team 2's rotation moved on (Carl pitched the 1st)


def test_batting_order_carries_over_innings():
    s = replay(setup(), three_outs() * 2)
    assert s.batter == "Edward"                  # 3 outs by 3 batters: order wraps
    s = replay(setup(), K + K + play("1B") + K + three_outs())
    assert s.batter == "Arath"                   # Edward, Arath, Angel, Edward made the outs/hit


def test_two_out_halves():
    s = replay(setup(outs=2), K + K)
    assert s.half == "bottom"


def test_double_play_ends_two_out_half():
    s = replay(setup(outs=2), play("1B") + play("DP"))
    assert s.half == "bottom" and s.score[1] == 0


def test_changing_outs_applies_next_half():
    s = replay(setup(), K + [{"type": "outs", "value": 2}] + K)
    assert s.half == "top" and s.outs == 2       # still a 3-out half
    s = replay(setup(), K + [{"type": "outs", "value": 2}] + K + K + K + K)
    assert s.inning == 2 and s.half == "top"     # bottom 1 was a 2-out half


def test_too_many_outs_rejected():
    with pytest.raises(GameError):
        replay(setup(), K + K + play("1B") + play("DP"))


def test_runs_do_not_count_on_inning_ending_force_out():
    # runner on 3rd, two outs, ground out: no run
    s = replay(setup(), play("3B") + K + K + play("GO"))
    assert s.score[1] == 0 and s.half == "bottom"


def test_sac_fly_cannot_be_last_out():
    with pytest.raises(GameError):
        replay(setup(), play("3B") + K + K + play("SF"))


# ---------------------------------------------------------------- runner movement

def test_single_defaults_and_override():
    s = replay(setup(), play("2B") + play("1B"))
    assert s.score[1] == 0 and names(s) == {1: "Arath", 2: None, 3: "Edward"}
    s = replay(setup(), play("2B") + play("1B", {2: "H"}))
    assert s.score[1] == 1 and s.plate_appearances[-1]["rbi"] == 1


def test_sac_fly_scores_runner_from_third_and_can_be_changed():
    s = replay(setup(), play("3B") + play("SF"))
    assert s.score[1] == 1 and s.outs == 1 and s.plate_appearances[-1]["rbi"] == 1
    s = replay(setup(), play("3B") + play("SF", {3: 3}))
    assert s.score[1] == 0


def test_tag_up_on_deep_pop_out():
    s = replay(setup(), play("1B") + play("PO", {1: 2}))
    assert names(s)[2] == "Edward" and s.outs == 1


def test_fielders_choice_default_and_pick():
    s = replay(setup(), play("1B") + play("1B") + play("FC"))
    # runners 1st (Arath) and 2nd (Edward); lead forced runner (2nd) is out by default
    assert s.outs == 1 and names(s) == {1: "Angel", 2: "Arath", 3: None}
    s = replay(setup(), play("1B") + play("1B") + play("FC", {1: "out", 2: 3}))
    assert names(s) == {1: "Angel", 2: None, 3: "Edward"}


def test_double_and_triple_play():
    s = replay(setup(), play("1B") + play("DP"))
    assert s.outs == 2 and s.runners() == {}
    s = replay(setup(), play("1B") + play("1B") + play("TP"))
    assert s.half == "bottom"


def test_dest_validation():
    with pytest.raises(GameError):
        replay(setup(), play("1B") + play("1B", {1: 1}))     # batter and runner both on 1st
    with pytest.raises(GameError):
        replay(setup(), play("2B") + play("1B", {2: 1}))     # backwards


def test_hit_but_thrown_out_stretching():
    s = replay(setup(), play("1B", {"B": "out"}))
    assert s.outs == 1 and s.hits[1] == 1


# ---------------------------------------------------------------- ghost runners

def test_ghost_runner_three_man_lineup():
    # Edward 1B, Arath 1B, Angel 1B -> loaded; Edward is up but on 3rd
    s = replay(setup(), play("1B") + play("1B") + play("1B"))
    assert s.batter == "Edward"
    s = replay(setup(), play("1B") + play("1B") + play("1B") + P("B"))
    assert names(s)[3] == "Edward*"          # ghost holds his base


def test_ghost_run_credited_to_player():
    ev = play("1B") + play("1B") + play("1B") + play("1B")   # Edward bats again, singles
    s = replay(setup(), ev)
    run = s.plate_appearances[-1]["runs"][0]
    assert run["player"] == "Edward" and run["ghost"] and s.score[1] == 1
    assert names(s)[1] == "Edward"           # Edward himself is now on 1st


def test_all_time_hitter_bats_for_both():
    st = setup(l1=T1 + ["Jason"], l2=T2 + ["Jason"], all_time={"name": "Jason", "role": "hitter"})
    s = replay(st, K + K + play("1B") + play("1B"))
    assert s.plate_appearances[-1]["batter"] == "Jason" and s.plate_appearances[-1]["team"] == 1
    s = replay(st, K + K + K + K + K + K + play("1B"))
    # bottom 1: Carl, Uriel, Vera out... order: K,K,K top (Edward, Arath, Angel); bottom Carl, Uriel, Vera K
    # top 2: Jason leads off for Team 1
    assert s.plate_appearances[-1]["batter"] == "Jason" and s.plate_appearances[-1]["team"] == 1


def test_setup_rules():
    with pytest.raises(GameError):   # same player on both teams without being all-time
        replay(setup(l1=T1 + ["Carl"]), [])
    with pytest.raises(GameError):   # all-time hitter can't pitch
        replay(setup(l1=T1 + ["Jason"], l2=T2 + ["Jason"], r1=T1 + ["Jason"],
                     all_time={"name": "Jason", "role": "hitter"}), [])
    # all-time pitcher pitches for both, bats for neither
    s = replay(setup(r1=["Jason"], r2=["Jason"], all_time={"name": "Jason", "role": "pitcher"}), K)
    assert s.pitch_log[0][0] == "Jason"


def test_pitcher_cannot_be_batting_team_player():
    with pytest.raises(GameError):
        replay(setup(), [{"type": "pitcher", "name": "Arath"}])   # Arath bats for Team 1


# ---------------------------------------------------------------- errors / earned runs

def test_reached_on_error_then_scores_is_unearned():
    s = replay(setup(), play("E", error_fielder="Carl") + play("2B", {1: "H"}))
    run = s.plate_appearances[-1]["runs"][0]
    assert run["player"] == "Edward" and not run["earned"]
    assert s.plate_appearances[0]["rbi"] == 0 and s.errors[2] == 1


def test_runs_after_inning_should_have_ended_are_unearned():
    # 2 outs, error (should have been out 3), then a 2-run homer: both unearned, still 2 RBI
    ev = K + K + play("E", error_fielder="Uriel") + play("HR")
    s = replay(setup(), ev)
    pa = s.plate_appearances[-1]
    assert s.score[1] == 2 and pa["rbi"] == 2
    assert all(not r["earned"] for r in pa["runs"])


def test_earned_runs_normally():
    s = replay(setup(), play("1B") + play("HR"))
    assert all(r["earned"] for r in s.plate_appearances[-1]["runs"])


def test_error_on_other_play_makes_runs_unearned_and_counts_error():
    s = replay(setup(), play("2B") + play("1B", {2: "H"}, error_fielder="Vera"))
    run = s.plate_appearances[-1]["runs"][0]
    assert not run["earned"] and s.errors[2] == 1


def test_inherited_runner_charged_to_previous_pitcher():
    ev = play("1B") + [{"type": "pitcher", "name": "Uriel"}] + play("HR")
    s = replay(setup(), ev)
    runs = s.plate_appearances[-1]["runs"]
    by_player = {r["player"]: r["pitcher"] for r in runs}
    assert by_player == {"Edward": "Carl", "Arath": "Uriel"}


def test_pitches_counted_per_pitcher_after_change():
    ev = P("B", "S") + [{"type": "pitcher", "name": "Vera"}] + P("S", "S")
    s = replay(setup(), ev)
    assert [p[0] for p in s.pitch_log] == ["Carl", "Carl", "Vera", "Vera"]
    assert s.plate_appearances[-1]["pitcher"] == "Vera"


# ---------------------------------------------------------------- steals

def test_stolen_base_and_steal_of_home():
    s = replay(setup(), play("1B") + [{"type": "runner", "kind": "SB", "base": 1}])
    assert names(s)[2] == "Edward"
    s = replay(setup(), play("3B") + [{"type": "runner", "kind": "SB", "base": 3, "to": "H"}])
    assert s.score[1] == 1 and s.runner_events[-1]["runs"][0]["earned"]


def test_caught_stealing_final_out_same_batter_leads_off():
    ev = K + K + play("1B") + P("B", "S") + [{"type": "runner", "kind": "CS", "base": 1}]
    s = replay(setup(), ev)
    assert s.half == "bottom"
    # Angel was batting when Edward... order: Edward K, Arath K, Angel 1B, Edward batting (B,S) -> CS
    s2 = replay(setup(), ev + K + K + K)
    assert s2.half == "top" and s2.inning == 2
    assert s2.batter == "Edward" and (s2.balls, s2.strikes) == (0, 0)
    assert [p for p in s2.pitch_log if p[1] == "Edward" and p[0] == "Carl"][-2:] == [("Carl", "Edward", "B"), ("Carl", "Edward", "S")]


def test_caught_stealing_not_final_out_keeps_count():
    s = replay(setup(), play("1B") + P("B", "S") + [{"type": "runner", "kind": "CS", "base": 1}])
    assert s.outs == 1 and (s.balls, s.strikes) == (1, 1) and s.batter == "Arath"


def test_steal_into_occupied_base_rejected():
    with pytest.raises(GameError):
        replay(setup(), play("2B") + play("1B", {2: 2}) + [{"type": "runner", "kind": "SB", "base": 1}])


# ---------------------------------------------------------------- game end

def lead_events(top_runs, bottom_runs):
    """One inning where Team 1 scores top_runs on solo HRs and Team 2 bottom_runs."""
    return play("HR") * top_runs + three_outs() + play("HR") * bottom_runs + three_outs()


def test_walk_off_solo_and_two_run_homer():
    # tie 0-0 into bottom 2 (last inning), solo HR ends it 1-0
    ev = three_outs() * 2 + [{"type": "last_inning", "inning": 2}] + three_outs() + play("HR")
    s = replay(setup(), ev)
    assert s.status == "final" and s.result == "2" and s.walk_off and s.score == {1: 0, 2: 1}
    # Team 2 down 0-1... make it 4-4 then a 2-run HR -> 6-4
    ev = play("HR") * 4 + three_outs() + play("HR") * 4 + three_outs()
    ev += [{"type": "last_inning", "inning": 2}] + three_outs() + play("1B") + play("HR")
    s = replay(setup(), ev)
    assert s.score == {1: 4, 2: 6} and s.walk_off


def test_non_homer_walk_off_stops_at_winning_run():
    # tied 0-0, bottom of the last, bases loaded, double: only the winning run counts -> 1-0
    ev = three_outs() + [{"type": "last_inning", "inning": 1}] + play("1B") + play("1B") + play("1B") + play("2B")
    s = replay(setup(), ev)
    assert s.status == "final" and s.score == {1: 0, 2: 1}
    assert s.plate_appearances[-1]["rbi"] == 1 and sum(s.line[2]) == 1
    # down 1, bases loaded, triple: tying + winning run count -> 2-1
    ev = play("HR") + three_outs() + [{"type": "last_inning", "inning": 1}] + play("1B") * 3 + play("3B")
    s = replay(setup(), ev)
    assert s.score == {1: 1, 2: 2} and s.plate_appearances[-1]["rbi"] == 2
    # grand slam when tied still counts all four
    ev = three_outs() + [{"type": "last_inning", "inning": 1}] + play("1B") * 3 + play("HR")
    s = replay(setup(), ev)
    assert s.score == {1: 0, 2: 4}


def test_non_homer_runs_count_normally_before_last_inning():
    ev = three_outs() + play("1B") * 3 + play("2B")
    s = replay(setup(), ev)
    assert s.score[2] == 2 and s.status == "live"


def test_walk_off_on_bases_loaded_walk_and_on_error():
    ev = three_outs() + [{"type": "last_inning", "inning": 1}] + play("1B") + play("1B") + play("1B") + BB
    s = replay(setup(), ev)
    assert s.status == "final" and s.score == {1: 0, 2: 1}
    ev = three_outs() + [{"type": "last_inning", "inning": 1}] + play("3B") + play("E", error_fielder="Arath")
    s = replay(setup(), ev)
    assert s.status == "final" and s.result == "2"


def test_home_team_ahead_after_top_of_last_skips_bottom():
    ev = three_outs() + play("HR") + three_outs() + [{"type": "last_inning", "inning": 2}] + three_outs()
    s = replay(setup(), ev)
    assert s.status == "final" and s.result == "2" and not s.walk_off


def test_away_team_wins_after_bottom_of_last():
    ev = [{"type": "last_inning", "inning": 1}] + play("HR") + three_outs() + three_outs()
    s = replay(setup(), ev)
    assert s.status == "final" and s.result == "1"


def test_tie_after_last_inning_draw_or_continue():
    ev = [{"type": "last_inning", "inning": 1}] + three_outs() * 2
    s = replay(setup(), ev)
    assert s.status == "tied"
    with pytest.raises(GameError):
        replay(setup(), ev + K)
    s = replay(setup(), ev + [{"type": "end"}])
    assert s.status == "final" and s.result == "draw"
    assert len(s.line[1]) == 1 and len(s.line[2]) == 1   # no phantom extra inning in the line score
    s = replay(setup(), ev + [{"type": "continue", "one_inning": True}] + play("HR"))
    assert s.status == "live" and s.inning == 2 and s.score[1] == 1 and s.last_inning == 2


def test_extra_inning_is_the_new_last_inning():
    tied = [{"type": "last_inning", "inning": 1}] + three_outs() * 2 + [{"type": "continue", "one_inning": True}]
    # walk-off in the bottom of the extra inning ends it
    s = replay(setup(), tied + three_outs() + play("HR"))
    assert s.status == "final" and s.result == "2" and s.walk_off
    # still tied after the extra inning: asks again
    s = replay(setup(), tied + three_outs() * 2)
    assert s.status == "tied" and s.inning == 2
    # away team scores in the top, home team doesn't answer
    s = replay(setup(), tied + play("HR") + three_outs() * 2)
    assert s.status == "final" and s.result == "1"


def test_old_continue_without_flag_still_replays_the_same():
    """Games saved before one_inning existed keep going with no last inning, exactly as recorded."""
    ev = [{"type": "last_inning", "inning": 1}] + three_outs() * 2 + [{"type": "continue"}] + three_outs() * 4
    s = replay(setup(), ev)
    assert s.status == "live" and s.inning == 4 and s.last_inning is None


def test_end_anytime_and_events_after_final_rejected():
    s = replay(setup(), play("HR") + [{"type": "end"}])
    assert s.result == "1"
    with pytest.raises(GameError):
        replay(setup(), play("HR") + [{"type": "end"}] + K)


def test_last_inning_set_while_home_already_leading_in_bottom():
    ev = three_outs() + play("HR") + [{"type": "last_inning", "inning": 1}]
    s = replay(setup(), ev)
    assert s.status == "final" and s.result == "2" and not s.walk_off


# ---------------------------------------------------------------- undo & summaries

def test_undo_is_replay_without_last_event():
    ev = play("1B") + play("1B") + K + K + K       # ends top 1
    full = replay(setup(), ev)
    undone = replay(setup(), ev[:-1])
    assert full.half == "bottom"
    assert undone.half == "top" and undone.outs == 2 and undone.strikes == 2
    # 3-man lineup: Edward and Arath have batted again, so ghosts hold their bases
    assert names(undone) == {1: "Arath*", 2: "Edward*", 3: None}


def test_line_score_and_half_summary():
    ev = play("HR") + play("1B") + three_outs() + play("E", error_fielder="Edward") + three_outs()
    s = replay(setup(), ev)
    assert s.line == {1: [1, ], 2: [0]} or s.line[1][0] == 1
    top, bottom = s.half_log[0], s.half_log[1]
    assert (top["runs"], top["hits"], top["lob"]) == (1, 2, 1)
    assert bottom["errors"] == 1 and s.errors[1] == 1


def test_default_dest_preview_matches_mockup():
    # bases loaded, single: 3rd scores, 2nd to 3rd, 1st to 2nd, batter to 1st
    s = replay(setup(l1=["A", "B", "C", "D"]), play("1B") * 3)
    assert default_dest(s, "1B") == {"B": 1, 1: 2, 2: 3, 3: "H"}


# ---------------------------------------------------------------- how outs were made

def test_ground_out_thrower_recorded():
    s = replay(setup(), play("GO", outs_detail={"B": {"how": "runner", "by": "Carl"}}))
    assert s.plate_appearances[-1]["out_details"] == [{"player": "Edward", "from": "B", "how": "runner", "by": "Carl"}]


def test_runner_thrown_out_at_home_by_sign():
    ev = play("2B") + play("1B", {2: "out"}, outs_detail={"2": {"how": "sign", "by": "Vera"}})
    s = replay(setup(), ev)
    pa = s.plate_appearances[-1]
    assert s.outs == 1 and s.score[1] == 0 and pa["out_details"][0]["player"] == "Edward"
    assert pa["out_details"][0]["how"] == "sign" and pa["rbi"] == 0


def test_out_detail_only_for_players_who_were_out():
    with pytest.raises(GameError):
        replay(setup(), play("1B", outs_detail={"B": {"how": "tag", "by": "Carl"}}))
    with pytest.raises(GameError):
        replay(setup(), play("GO", outs_detail={"B": {"how": "teleport"}}))


def test_empty_out_detail_is_skipped():
    s = replay(setup(), play("GO", outs_detail={"B": {"how": None, "by": None}}))
    assert s.plate_appearances[-1]["out_details"] == []


def test_caught_stealing_how_and_by():
    ev = play("1B") + [{"type": "runner", "kind": "CS", "base": 1, "how": "runner", "by": "Uriel"}]
    s = replay(setup(), ev)
    assert (s.runner_events[-1]["how"], s.runner_events[-1]["by"]) == ("runner", "Uriel")


# ---------------------------------------------------------------- review fixes

def runner(kind, base, to=None, **kw):
    e = {"type": "runner", "kind": kind, "base": base}
    if to is not None:
        e["to"] = to
    e.update(kw)
    return [e]


def test_time_play_run_counts_on_a_hit():
    # Two outs, runner on 2nd; single, he scores, batter thrown out at 2nd for the third out
    ev = K + K + play("1B") + play("1B", {"B": "out", 1: "H"})
    s = replay(setup(l1=["A", "B", "C", "D"]), ev)
    assert s.score[1] == 1 and s.half == "bottom"
    assert s.plate_appearances[-1]["runs"][0]["player"] == "C"


def test_run_on_force_out_for_last_out_does_not_count():
    ev = K + K + play("3B") + BB + play("FC", {1: "out", 3: "H", "B": 1})
    s = replay(setup(l1=["A", "B", "C", "D", "E"]), ev)
    assert s.score[1] == 0 and s.half == "bottom"


def test_runners_cannot_pass_in_a_play():
    with pytest.raises(GameError):
        replay(setup(), play("1B") + play("1B", {1: 3, "B": 2}) + play("1B", {2: 2, 1: 3}))
    with pytest.raises(GameError):     # batter ends ahead of the runner from 1st
        replay(setup(), play("1B") + play("2B", {1: 1, "B": 2}))
    # several runners can still score, and an out runner can be passed
    s = replay(setup(), play("1B") + play("1B") + play("1B", {2: "out", 1: "H", "B": 2}))
    assert s.score[1] == 1 and names(s)[2] == "Angel"


def test_steal_cannot_pass_a_runner():
    base = play("1B") + play("1B")             # runners on 1st and 2nd
    with pytest.raises(GameError):
        replay(setup(), base + runner("SB", 1, 3))
    with pytest.raises(GameError):
        replay(setup(), base + runner("SB", 1, "H"))
    s = replay(setup(), base + runner("SB", 2, 3) + runner("SB", 1, 2))
    assert names(s) == {1: None, 2: "Arath", 3: "Edward"}


def test_events_are_numbered_in_order():
    s = replay(setup(), play("1B") + runner("SB", 1, 2) + K)
    order = sorted([(p["n"], "pa") for p in s.plate_appearances] + [(r["n"], "run") for r in s.runner_events])
    assert [k for _, k in order] == ["pa", "run", "pa"]