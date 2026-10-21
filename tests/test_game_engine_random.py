"""Plays thousands of random games and checks the bookkeeping always adds up."""
import random

from game_engine import replay, apply, GameError, validate_setup

PLAYS = ["1B", "2B", "3B", "HR", "GO", "PO", "LO", "FC", "SF", "DP", "TP", "E"]


def random_setup(rng):
    pool = ["Angel", "Arath", "Carl", "Edward", "Jason", "Uriel", "Vera", "Mia"]
    rng.shuffle(pool)
    n = rng.choice([1, 2, 3, 4])
    t1, t2 = pool[:n], pool[n:2 * n]
    setup = {"lineups": {1: list(t1), 2: list(t2)}, "rotations": {1: list(t1), 2: list(t2)},
             "outs_per_half": rng.choice([2, 3])}
    extra = pool[2 * n] if len(pool) > 2 * n else None
    if extra and rng.random() < 0.4:
        if rng.random() < 0.5:
            setup["all_time"] = {"name": extra, "role": "hitter"}
            setup["lineups"][1].insert(rng.randrange(n + 1), extra)
            setup["lineups"][2].insert(rng.randrange(n + 1), extra)
        else:
            setup["all_time"] = {"name": extra, "role": "pitcher"}
            setup["rotations"][1].append(extra)
            setup["rotations"][2].append(extra)
    return setup


def random_event(rng, s):
    r = rng.random()
    if s.status == "tied":
        return rng.choice([{"type": "continue"}, {"type": "continue", "one_inning": True}, {"type": "end"}])
    if r < 0.55:
        return {"type": "pitch", "result": rng.choice("BSF")}
    if r < 0.85:
        e = {"type": "play", "outcome": rng.choice(PLAYS)}
        if rng.random() < 0.2:
            e["error_fielder"] = "someone"
        if rng.random() < 0.25:   # random runner override
            keys = ["B"] + [b for b in (1, 2, 3) if s.bases[b]]
            k = rng.choice(keys)
            e["dest"] = {k: rng.choice([1, 2, 3, "H", "out"])}
        return e
    if r < 0.92 and s.runners():
        base = rng.choice(list(s.runners()))
        return {"type": "runner", "kind": rng.choice(["SB", "SB", "CS", "PO"]), "base": base,
                "to": rng.choice([None, "H"])}
    if r < 0.95:
        return {"type": "pitcher", "name": rng.choice(s.setup["rotations"][s.fielding_team])}
    if r < 0.97:
        return {"type": "outs", "value": rng.choice([2, 3])}
    if r < 0.995:
        return {"type": "last_inning", "inning": s.inning + rng.choice([0, 0, 1])}
    return {"type": "end"}


def check_invariants(s, events):
    runs = s.plate_appearances and sum(len(p["runs"]) for p in s.plate_appearances) or 0
    runs += sum(len(e["runs"]) for e in s.runner_events)
    assert runs == s.score[1] + s.score[2]
    assert sum(s.line[1]) == s.score[1] and sum(s.line[2]) == s.score[2]
    if s.status == "live":
        assert 0 <= s.outs < s.outs_limit
        assert s.balls < 4 and s.strikes < 3
    ids = [id(r) for r in s.runners().values()]
    assert len(ids) == len(set(ids))
    for p in s.plate_appearances:
        assert p["rbi"] <= len(p["runs"])
        assert p["batter"] != p["pitcher"]
        for run in p["runs"]:
            assert run["pitcher"] in s.setup["rotations"][2 if p["team"] == 1 else 1]
    if s.status == "final":
        exp = "1" if s.score[1] > s.score[2] else "2" if s.score[2] > s.score[1] else "draw"
        assert s.result == exp
    # Replaying from scratch gives the same state (undo relies on this)
    again = replay(s.setup, events)
    assert again.score == s.score and again.outs == s.outs and again.inning == s.inning
    assert [r.name if r else None for r in again.bases.values()] == [r.name if r else None for r in s.bases.values()]


def test_random_games():
    rng = random.Random(7)
    games = 0
    for _ in range(3000):
        setup = random_setup(rng)
        validate_setup(setup)
        s = replay(setup, [])
        events = []
        for _ in range(rng.randint(20, 400)):
            if s.status == "final":
                break
            e = random_event(rng, s)
            trial = replay(setup, events)   # apply on a fresh copy so a rejected event changes nothing
            try:
                apply(trial, e)
            except GameError:
                continue
            events.append(e)
            s = trial
        check_invariants(s, events)
        games += 1
    assert games == 3000