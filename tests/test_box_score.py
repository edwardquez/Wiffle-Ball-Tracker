import random

from box_score import box_score_tables
from game_engine import replay, GameError
from tests.test_game_engine_random import random_event


def setup():
    return {"lineups": {1: ["Edward", "Arath", "Angel"], 2: ["Carl", "Uriel", "Vera"]},
            "rotations": {1: ["Edward", "Arath"], 2: ["Carl", "Uriel"]}, "outs_per_half": 3}


def P(*r):
    return [{"type": "pitch", "result": x} for x in r]


def test_simple_box_score():
    ev = (P("S") + [{"type": "play", "outcome": "HR"}]       # Edward homers on 0-1 (pitches "SX")
          + P("B", "B", "B", "B")                            # Arath walks
          + P("S", "S", "S")                                 # Angel strikes out
          + P("S", "S", "S")                                 # Edward strikes out
          + [{"type": "runner", "kind": "CS", "base": 1}])   # Arath caught stealing: third out
    s = replay(setup(), ev)
    t = box_score_tables(s)
    bat = {r["name"]: r for r in t["batting"][1]}
    assert (bat["Edward"]["PA"], bat["Edward"]["AB"], bat["Edward"]["H"], bat["Edward"]["R"], bat["Edward"]["RBI"]) == (2, 2, 1, 1, 1)
    assert (bat["Arath"]["BB"], bat["Arath"]["AB"], bat["Arath"]["PA"]) == (1, 0, 1)
    carl = t["pitching"][2][0]
    assert carl["name"] == "Carl" and carl["OUTS"] == 3 and carl["R"] == carl["ER"] == 1
    assert carl["P"] == 2 + 4 + 3 + 3                        # every pitch of every plate appearance
    assert (carl["H"], carl["BB"], carl["K"]) == (1, 1, 2)
    assert t["pitching"][1] == []                            # Team 1 hasn't pitched yet


def test_box_score_totals_match_the_game():
    """On many random games, the box score adds up to the scoreboard."""
    for seed in range(150):
        rng = random.Random(seed)
        s = replay(setup(), [])
        events = []
        for _ in range(200):
            if s.status == "final":
                break
            ev = random_event(rng, s)
            try:
                s = replay(setup(), events + [ev])
                events.append(ev)
            except GameError:
                continue
        t = box_score_tables(s)
        for team in (1, 2):
            assert sum(r["R"] for r in t["batting"][team]) == s.score[team]
            assert sum(r["H"] for r in t["batting"][team]) == s.hits[team]
            assert sum(r["R"] for r in t["pitching"][3 - team]) == s.score[team]