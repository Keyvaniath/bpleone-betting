"""Regression tests for the 2026-11-03 odds-integrity incident (P0).

A -110 placeholder (and the model's own "fair" price) reached EV, ranking,
selection, settlement and the Alpha email. These tests pin the fail-closed
contract so it cannot silently recur. Run: python -m pytest python/tests -q
"""
import datetime as dt
import json
import os
import sys

import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import quotes  # noqa: E402

NOW = dt.datetime(2026, 11, 3, 18, 0, tzinfo=dt.timezone.utc)


def _snap(**over):
    g = {"sport": "NBA", "event_id": "401", "matchup": "PHI @ DET", "away": "PHI", "home": "DET",
         "commence_time": "2026-11-04T00:00Z", "status": "pre", "provider": "DraftKings",
         "market": {"ml_home": -110, "ml_away": -110, "total": 217.5, "over_price": -115,
                    "under_price": -105, "book": "draftkings"}}
    g.update(over.pop("game", {}))
    return {"generated_at": "2026-11-03T17:30:00", "games": [g], **over}


# ---------------------------------------------------------------- math ----
@pytest.mark.parametrize("a,d", [(150, 2.5), (-150, 1 + 100 / 150), (-110, 1 + 100 / 110),
                                 (100, 2.0), (-100, 2.0), (250, 3.5)])
def test_american_to_decimal(a, d):
    assert quotes.american_to_decimal(a) == pytest.approx(d)


@pytest.mark.parametrize("bad", [None, "x", 0, 50, -99, float("nan")])
def test_invalid_american_is_none_not_a_default(bad):
    assert quotes.american_to_decimal(bad) is None


def test_ev_binary():
    assert quotes.ev_binary(0.5, 2.0) == pytest.approx(0.0)
    assert quotes.ev_binary(0.6, quotes.american_to_decimal(-110)) == pytest.approx(0.6 * (1 + 100 / 110) - 1)
    # equivalent form p*(d-1) - (1-p)
    p, d = 0.42, 2.6
    assert quotes.ev_binary(p, d) == pytest.approx(p * (d - 1) - (1 - p))
    assert quotes.ev_binary(None, 2.0) is None and quotes.ev_binary(0.5, None) is None


def test_no_vig_needs_both_sides():
    assert quotes.no_vig_two_way(-110, -110) == pytest.approx(0.5)
    a = quotes.no_vig_two_way(-150, 130)
    assert a == pytest.approx((1 / 1.6666667) / (1 / 1.6666667 + 1 / 2.3), rel=1e-6)
    assert quotes.no_vig_two_way(-150, None) is None


def test_min_acceptable_price_is_model_derived():
    # p=0.6, 2% hurdle -> decimal 1.7 -> -143
    assert quotes.min_acceptable_american(0.6, 0.02) == -143
    assert quotes.min_acceptable_american(0.4, 0.0) == 150


# --------------------------------------------------------------- quotes ----
def test_moneyline_quote_has_full_provenance():
    q, why = quotes.find_quote("NBA", "PHI @ DET", "ML_HOME", _snap())
    assert why is None
    assert q["provenance"] == "book_snapshot" and q["book"] == "draftkings"
    assert q["american"] == -110 and q["event_id"] == "401"
    assert q["observed_at"] and q["snapshot_id"].startswith("espn_odds@")
    assert q["no_vig_prob"] == pytest.approx(0.5)


def test_real_minus_110_is_actionable():
    """-110 is a legitimate price: only synthetic PROVENANCE is rejected."""
    q, _ = quotes.find_quote("NBA", "PHI @ DET", "ML_AWAY", _snap())
    ok, why = quotes.actionable(q, NOW)
    assert ok and why is None and q["american"] == -110


def test_props_are_unsupported_not_defaulted():
    q, why = quotes.find_quote("NBA", "Jalen Brunson", "PRA_UNDER_40.5", _snap())
    assert q is None and why == quotes.R_UNSUPPORTED


def test_total_requires_exact_line():
    q, why = quotes.find_quote("NBA", "PHI @ DET", "UNDER_216.5", _snap())
    assert q is None and why == quotes.R_LINE_MISMATCH
    q, why = quotes.find_quote("NBA", "PHI @ DET", "UNDER_217.5", _snap())
    assert q["american"] == -105 and q["line"] == 217.5


def test_missing_event_is_no_quote():
    q, why = quotes.find_quote("NBA", "BOS @ NYK", "ML_HOME", _snap())
    assert q is None and why == quotes.R_NO_QUOTE


def test_invalid_book_price_is_rejected():
    q, why = quotes.find_quote("NBA", "PHI @ DET", "ML_HOME",
                               _snap(game={"market": {"ml_home": 50, "ml_away": -110}}))
    assert q is None and why == quotes.R_INVALID


def test_stale_started_and_synthetic_fail_closed():
    q, _ = quotes.find_quote("NBA", "PHI @ DET", "ML_HOME", _snap())
    assert quotes.actionable(q, NOW + dt.timedelta(hours=4)) == (False, quotes.R_STALE)
    q2, _ = quotes.find_quote("NBA", "PHI @ DET", "ML_HOME", _snap(game={"status": "in"}))
    assert quotes.actionable(q2, NOW) == (False, quotes.R_STARTED)
    q3, _ = quotes.find_quote("NBA", "PHI @ DET", "ML_HOME", _snap(game={"commence_time": "2026-11-03T18:02Z"}))
    assert quotes.actionable(q3, NOW) == (False, quotes.R_STARTED)
    for prov in ("synthetic", "model_fair", "venue_breakeven", "reconstructed"):
        assert quotes.actionable(dict(q, provenance=prov), NOW) == (False, quotes.R_NOT_BOOK)
    assert quotes.actionable(None, NOW) == (False, quotes.R_NO_QUOTE)


# ------------------------------------------------------- selection paths ----
@pytest.fixture
def datadir(tmp_path, monkeypatch):
    import todays_top_plays as ttp
    import alpha_pick_of_day as apod
    snap = _snap(generated_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
                 game={"commence_time": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=6)).strftime("%Y-%m-%dT%H:%MZ")})
    (tmp_path / "espn_odds.json").write_text(json.dumps(snap))
    (tmp_path / "slate_player_pot.json").write_text(json.dumps({"all_picks": [
        # a prop "priced" at a placeholder -110 -- must never be ranked
        {"sport": "NBA", "player": "Jalen Brunson", "market": "PRA_UNDER_40.5", "prob": 0.74,
         "fair_american": -110, "source": "nba_pra"}]}))
    (tmp_path / "slate_team_pot.json").write_text(json.dumps({"all_picks": [
        {"sport": "NBA", "matchup": "PHI @ DET", "market": "ML_HOME", "prob": 0.70,
         "fair_american": -233, "source": "nba_game"}]}))
    for m in (ttp, apod, quotes):
        monkeypatch.setattr(m, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ttp, "OUT", str(tmp_path / "todays_top_plays.json"))
    monkeypatch.setattr(apod, "OUT", str(tmp_path / "alpha_pick_of_day.json"))
    monkeypatch.setattr(quotes, "_SNAPSHOT", None)
    monkeypatch.setattr(ttp, "_PROVEN_NEG_CACHE", None, raising=False)
    return tmp_path


def test_top_plays_ranks_only_quoted_candidates(datadir):
    import todays_top_plays as ttp
    out = ttp.run()
    names = [c["player_or_matchup"] for c in out["top_25"]]
    assert "Jalen Brunson" not in names                       # the placeholder-priced prop
    proj = {p["player_or_matchup"]: p for p in out["projections"]}
    assert proj["Jalen Brunson"]["actionable"] is False
    assert proj["Jalen Brunson"]["reason"] == quotes.R_UNSUPPORTED
    assert out["funnel"]["rejected"].get(quotes.R_UNSUPPORTED) == 1
    ml = [c for c in out["top_25"] if c["player_or_matchup"] == "PHI @ DET"]
    assert ml, "the quoted moneyline must reach the board"
    c = ml[0]   # EV is computed at the QUOTED price, never the model's own -233
    assert c["book_american"] == -110 and c["decimal_odds"] == pytest.approx(1 + 100 / 110, abs=1e-3)
    assert c["quote"]["provenance"] == "book_snapshot"
    assert c["edge_pct"] == pytest.approx(round((c["prob"] * (1 + 100 / 110) - 1) * 100, 1), abs=0.1)


def test_alpha_never_selects_an_unquoted_candidate(datadir):
    import alpha_pick_of_day as apod
    (datadir / "todays_top_plays.json").write_text(json.dumps({"top_25": [
        {"sport": "NBA", "player_or_matchup": "Jalen Brunson", "market": "PRA_UNDER_40.5",
         "prob": 0.62, "fair_american": -110, "decimal_odds": 1.909, "src": "player"}]}))
    out = apod.run()
    assert out["alpha_pick"] is None
    assert out["diagnostics"]["rejected"].get(quotes.R_UNSUPPORTED) == 1


# ------------------------------------------------------------ settlement ----
def test_settlement_never_pays_a_placeholder(monkeypatch):
    import all_picks_tracker as t
    monkeypatch.setattr(t, "_grade_wnba_pick", lambda p, by, games: "won")
    old = (dt.datetime.now() - dt.timedelta(days=1)).isoformat(timespec="seconds")
    pick = {"pick_id": "x", "sport": "WNBA", "market": "PTS_OVER_10.5", "player_or_matchup": "a b",
            "recorded_at": old, "settled": False, "date": old[:10]}
    t._settle_picks([pick])
    assert pick.get("voided") is True and pick.get("payout_units") is None
    assert pick["voided_reason"].startswith("unpriced")


def test_intake_gate_blocks_synthetic_minus_110_only():
    import all_picks_tracker as t
    picks = [{"pick_id": "fake", "fair_american": -110, "prob": 0.74},      # -110 stamped on a 74% pick
             {"pick_id": "genuine_fair", "fair_american": -110, "prob": 0.524},
             {"pick_id": "book", "book_american": -110, "fair_american": -250, "prob": 0.71}]
    kept = {p["pick_id"] for p in t._block_unpriced(picks)}
    assert kept == {"genuine_fair", "book"}


# ------------------------------------------------------------ provenance ----
def test_provenance_classes():
    import all_picks_tracker as t
    pv = t._price_provenance
    q = {"provenance": "book_snapshot", "book": "draftkings", "observed_at": "2026-11-03T17:30:00",
         "snapshot_id": "espn_odds@x#1", "event_id": "1"}
    assert pv({"book_american": -120, "quote": q}, at_intake=True)["class"] == "A"
    assert pv({"book_american": -120})["kind"] == "book_untimestamped"            # no timestamp -> not A
    assert pv({"book_american": -120, "repriced": {"book": "bovada"}})["kind"] == "reconstructed"
    assert pv({"fair_american": -250, "market": "PRA_UNDER_40.5"})["kind"] == "model_fair"
    assert pv({"fair_american": -136, "market": "PP_batter_hrr_under_3.5"})["kind"] == "venue_breakeven"
    assert pv({})["kind"] == "unpriced"
    # a synthetic quote never makes class A, even with a timestamp
    assert pv({"book_american": -110, "quote": dict(q, provenance="synthetic")}, at_intake=True)["class"] == "B"


def test_reprice_moves_intake_A_to_B_and_keeps_original():
    import all_picks_tracker as t
    q = {"provenance": "book_snapshot", "book": "draftkings", "observed_at": "2026-11-03T17:30:00"}
    p = {"book_american": -120, "quote": q}
    p["price_provenance"] = t._price_provenance(p, at_intake=True)
    p.pop("quote")
    p["repriced"] = {"book": "draftkings", "book_snapshot_at": "2026-11-03T18:00:00"}
    assert t._backfill_provenance([p]) == 1
    assert p["price_provenance"]["kind"] == "reconstructed" and p["price_provenance_at_intake"]["class"] == "A"
    assert t._backfill_provenance([p]) == 0                                     # idempotent


def test_top25_collector_carries_the_quote(tmp_path, monkeypatch):
    """A board pick must reach the ledger with its book price + quote, never
    only the model's fair price (it would be graded at the model's number)."""
    import all_picks_tracker as t
    (tmp_path / "todays_top_plays.json").write_text(json.dumps({"top_25": [
        {"sport": "NBA", "player_or_matchup": "PHI @ DET", "market": "ML_HOME", "prob": 0.6,
         "fair_american": -150, "book_american": -110,
         "quote": {"provenance": "book_snapshot", "book": "draftkings", "observed_at": "2026-11-03T17:30:00"}}]}))
    monkeypatch.setattr(t, "DATA_DIR", str(tmp_path))
    rows = [r for r in t._collect_picks_from_sources() if r.get("source") == "top_25_board"]
    assert rows and rows[0]["book_american"] == -110
    assert rows[0]["price_provenance"]["class"] == "A"


# ------------------------------------------------------------- NFL feed ----
def test_next_week_query_and_rollover():
    import espn_odds as eo
    assert eo._next_week_query({"week": {"number": 8}, "season": {"type": 2}}) == "week=9&seasontype=2"
    assert eo._next_week_query({}) is None


def test_weekly_feed_merges_next_week(monkeypatch):
    """The bare NFL board holds last week's finals until midweek; next week's
    priced games must still reach espn_odds (2026-11-03: 0 -> 15 NFL lines)."""
    import espn_odds as eo

    def ev(i, state, ml=None):
        odds = [{"moneyline": {"home": {"close": {"odds": str(ml)}}, "away": {"close": {"odds": "+150"}}}}] if ml else []
        return {"id": str(i), "date": "2026-11-08T18:00Z", "competitions": [{
            "competitors": [{"homeAway": "home", "team": {"abbreviation": "KC"}},
                            {"homeAway": "away", "team": {"abbreviation": f"T{i}"}}],
            "odds": odds, "status": {"type": {"state": state}}}]}

    def fake_get(url):
        if "week=9" in url:
            return {"events": [ev(2, "pre", "-180"), ev(1, "post")]}       # overlap with the bare board
        return {"week": {"number": 8}, "season": {"type": 2}, "events": [ev(1, "post")]}

    monkeypatch.setattr(eo, "_get", fake_get)
    games = eo.fetch_sport("nfl")
    assert sorted(g["event_id"] for g in games) == ["1", "2"]                # merged, deduped by id
    nxt = [g for g in games if g["event_id"] == "2"][0]
    assert nxt["status"] == "pre" and nxt["market"]["ml_home"] == -180


# ---------------------------------------------------------- today status ----
def test_today_status_counts_only_what_is_on_disk(tmp_path, monkeypatch):
    import today_status as ts
    (tmp_path / "espn_odds.json").write_text(json.dumps(_snap()))
    (tmp_path / "game_lines_desk.json").write_text(json.dumps({"sports": {"nba": {
        "verdict": "NO EDGE: the model adds nothing", "proven": False,
        "board": [{"matchup": "PHI @ DET", "pick": None}]}}}))
    (tmp_path / "today.json").write_text(json.dumps({"no_games": True}))
    (tmp_path / "todays_top_plays.json").write_text(json.dumps({"funnel": {"n_input": 10, "rejected": {"unsupported_market": 9, "no_quote": 1}}}))
    (tmp_path / "alpha_pick_of_day.json").write_text(json.dumps({"alpha_pick": None}))
    monkeypatch.setattr(ts, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(ts, "OUT", str(tmp_path / "today_status.json"))
    out = ts.run()
    nba = [r for r in out["sports"] if r["sport"] == "NBA"][0]
    assert nba["games_on_board"] == 1 and nba["games_priced"] == 1 and nba["picks"] == 0
    assert "doesn't beat DraftKings" in nba["status"]
    mlb = [r for r in out["sports"] if r["sport"] == "MLB"][0]
    assert mlb["status"].startswith("Off-season")
    assert out["alpha"]["has_pick"] is False and "9 were player props" in out["alpha"]["reason"]


# ------------------------------------------------- remaining price paths ----
def test_arbitrage_never_publishes_the_demo():
    import arbitrage as ar
    out = ar.unavailable_artifact()
    assert out["available"] is False and out["arbs"] == [] and out["middles"] == []


def test_sharpe_ranking_skips_unpriced(tmp_path, monkeypatch):
    import sharpe_ranking as sr
    bb = tmp_path / "best_bets.json"
    bb.write_text(json.dumps({"bets": [{"model_prob": 0.6, "label": "no price"},
                                       {"model_prob": 0.6, "label": "priced", "book_american": -120}]}))
    monkeypatch.setattr(sr, "BB_PATH", str(bb))
    monkeypatch.setattr(sr, "OUT_PATH", str(tmp_path / "out.json"))
    out = sr.run()
    labels = [r["label"] for r in (out.get("rankings") or out.get("all") or [])]
    assert "no price" not in labels and "priced" in labels


def test_ml_reprice_no_longer_stamps_later_prices():
    import ml_reprice as mr
    pend = [{"pick_id": "p", "sport": "MLB", "market": "ML_HOME", "player_or_matchup": "NYY @ BOS",
             "fair_american": -110, "settled": False}]
    mr._SEED_CACHE = {}
    mr.apply_ledger(pend, lambda p: "home")
    assert pend[0].get("book_american") is None


def test_ml_reprice_one_shot_never_stamps_a_board_price(tmp_path, monkeypatch):
    """The one-shot run() read espn_odds.by_matchup (not status-filtered): a
    pending placeholder pick could be stamped with an in-play price."""
    import ml_reprice as mr
    led = {"picks": [{"pick_id": "p", "sport": "MLB", "market": "ML_HOME",
                      "player_or_matchup": "NYY @ BOS", "fair_american": -110, "settled": False}]}
    (tmp_path / "led.json").write_text(json.dumps(led))
    (tmp_path / "espn_odds.json").write_text(json.dumps(
        {"by_matchup": {"NYY @ BOS": {"ml_home": 450, "ml_away": -700}},
         "games": [{"sport": "MLB", "matchup": "NYY @ BOS", "status": "in",
                    "market": {"ml_home": 450, "ml_away": -700}}]}))
    for k, v in {"DATA_DIR": tmp_path, "LEDGER": tmp_path / "led.json", "SEED": tmp_path / "none.json",
                 "ARCHIVE": tmp_path / "arch.json", "MARKER": tmp_path / "marker.json"}.items():
        monkeypatch.setattr(mr, k, str(v))
    mr.run(force=True)
    out = json.loads((tmp_path / "led.json").read_text())["picks"][0]
    assert out.get("book_american") is None


_NFL_FINALS = [
    {"id": "9001", "date": "2026-11-08", "away_abbrev": "DEN", "home_abbrev": "CAR",
     "away_score": 20, "home_score": 17},
    {"id": "9002", "date": "2026-11-08", "away_abbrev": "NYJ", "home_abbrev": "KC",
     "away_score": 10, "home_score": 31},
]


def test_nfl_settles_by_event_id():
    import all_picks_tracker as t
    p = {"market": "ML_AWAY", "player_or_matchup": "DEN @ CAR", "date": "2026-11-07",
         "event_id": "9001"}           # UTC-dated a day off: the id still finds it
    assert t._grade_nfl_pick(p, {}, _NFL_FINALS) == "won"
    assert "9001" in p["outcome"]["verify"]


def test_nfl_refuses_empty_or_mismatched():
    import all_picks_tracker as t
    # empty matchup used to match the first game of the day
    assert t._grade_nfl_pick({"market": "ML_HOME", "player_or_matchup": "",
                              "date": "2026-11-08"}, {}, _NFL_FINALS) is None
    # event id that points at a different game -> data error, not a grade
    assert t._grade_nfl_pick({"market": "ML_HOME", "player_or_matchup": "DEN @ CAR",
                              "date": "2026-11-08", "event_id": "9002"}, {}, _NFL_FINALS) is None
    # substring: "KC" must not match "NYJ @ KC" for a pick on another game
    assert t._grade_nfl_pick({"market": "ML_HOME", "player_or_matchup": "J @ KC",
                              "date": "2026-11-08"}, {}, _NFL_FINALS) is None


def test_nfl_fallback_refuses_ambiguity():
    import all_picks_tracker as t
    twice = _NFL_FINALS + [{"date": "2026-11-09", "away_abbrev": "DEN", "home_abbrev": "CAR",
                            "away_score": 3, "home_score": 30}]
    assert t._grade_nfl_pick({"market": "ML_AWAY", "player_or_matchup": "DEN @ CAR",
                              "date": "2026-11-08"}, {}, twice) is None


def test_board_never_publishes_the_record_elo(monkeypatch):
    import board_prior as bp
    pr = bp.BoardPrior.__new__(bp.BoardPrior)
    pr.sport, pr.observed_at, pr.verdict = "nba", "2026-11-03T21:51:13", "NO EDGE: x"
    pr.dk = {"1": {"ml_home": -514, "ml_away": 391}}
    pr.desk = {}
    priced, unpriced = {"id": "1", "state": "pre"}, {"id": "2", "state": "pre"}
    p1 = bp.apply(priced, pr, 0.948)            # 7-game win-pct Elo said 94.8%
    assert priced["p_source"] == "dk_no_vig" and abs(p1 - 0.804) < 0.002
    p2 = bp.apply(unpriced, pr, 0.948)
    assert unpriced["p_home_display"] is None and unpriced["p_home_win_record_elo"] == 0.948
    for g, p in ((priced, p1), (unpriced, p2)):
        g["p_home_win"] = p
        bp.finalize(g, lambda x: round(-100 * x / (1 - x)) if x > 0.5 else round(100 * (1 - x) / x))
    assert unpriced["fair_home_american"] is None and priced["fair_home_american"] is not None


def test_board_prior_hides_dk_price_in_play():
    """(2026-11-04) in play the espn_odds snapshot can be DK's in-game line."""
    import board_prior as bp
    am = lambda p: -100 if p >= 0.5 else 100
    g = {"state": "in", "p_home_display": 0.6, "dk_ml_home": -191, "dk_ml_away": 160}
    bp.finalize(g, am)
    assert g["dk_ml_home"] is None and g["dk_ml_away"] is None
    assert g["dk_ml_home_last_seen"] == -191 and g["p_home_display"] is None
    pre = {"state": "pre", "p_home_display": 0.6, "dk_ml_home": -150, "dk_ml_away": 130}
    bp.finalize(pre, am)
    assert pre["dk_ml_home"] == -150 and pre["fair_home_american"] == -100


# ---- 2026-11-04: pricing guard, event-id quote join, desk gate, DK prop pricing ----

def _nfl_snap(now):
    return {"generated_at": now.isoformat(), "games": [{
        "sport": "NFL", "event_id": "401873037", "matchup": "JAX @ BAL", "status": "pre",
        "commence_time": (now + __import__("datetime").timedelta(hours=20)).isoformat(),
        "market": {"ml_home": 390, "ml_away": -520, "total": 39.5,
                   "over_price": -112, "under_price": -108, "book": "draftkings"}}]}


def test_find_quote_joins_full_names_by_event_id():
    import datetime as dt, quotes as Q
    now = dt.datetime.now(dt.timezone.utc)
    snap = _nfl_snap(now)
    full = "Jacksonville Jaguars @ Baltimore Ravens"
    q, why = Q.find_quote("NFL", full, "ML_HOME", snap)
    assert q is None and why == Q.R_NO_QUOTE          # the old miss
    q, why = Q.find_quote("NFL", full, "ML_HOME", snap, event_id="401873037")
    assert why is None and q["american"] == 390 and q["selection"] == "home"
    q, _ = Q.find_quote("NBA", full, "ML_HOME", snap, event_id="401873037")
    assert q is None                                   # sport must still agree


def test_verify_pricing_self_test_and_old_artifacts():
    import verify_pricing as vp
    assert vp.self_test() == []
    import datetime as dt
    now = dt.datetime(2026, 11, 4, 22, 0, tzinfo=dt.timezone.utc)
    # the 10/12 board shape: a "pick" with only the model's fair price
    assert vp.check_row({"matchup": "HOU @ SEA", "fair_american": -145}, now)
    assert not vp.check_row({"matchup": "HOU @ SEA", "fair_american": -145, "actionable": False}, now)


def test_best_bets_dk_prop_priced_at_quote_and_fails_closed():
    import datetime as dt, best_bets as bb
    now = dt.datetime.now(dt.timezone.utc)
    row = {"play": "UNDER", "market": "pitcher_strikeouts", "line": 5.5,
           "dk_over": -120, "dk_under": 100, "model_prob_over": 0.30, "model_prob_under": 0.70,
           "commence_time": (now + dt.timedelta(hours=3)).isoformat()}
    out = bb.price_dk_prop(row, (now - dt.timedelta(minutes=30)).isoformat(), now)
    if out is not None:                                # calibration may shrink it below +2%
        assert out["american"] == 100 and out["quote"]["provenance"] == "book_snapshot"
        assert out["ev"] >= bb.DK_PROP_EV_HURDLE
    stale = bb.price_dk_prop(row, (now - dt.timedelta(hours=5)).isoformat(), now)
    assert stale is None
    started = bb.price_dk_prop({**row, "commence_time": (now - dt.timedelta(minutes=1)).isoformat()},
                               now.isoformat(), now)
    assert started is None
    assert bb.price_dk_prop({**row, "dk_under": None}, now.isoformat(), now) is None


def test_failed_mlb_pull_never_publishes_the_demo_slate(tmp_path):
    """(2026-11-04) crash replay: network down -> CIN @ COL ML -110 became the POD."""
    import json, datetime as dt, pipeline as P
    demo = [dict(g, is_demo=True) for g in P.DEMO_SLATE]
    path = str(tmp_path / "today.json")
    m = P._production_manifest(demo, path)
    assert m["games"] == [] and m["play_of_day"] is None and m["fetch_error"] and not m["is_demo"]
    json.dump({"date": dt.date.today().isoformat(), "games": [{"matchup": "MIL @ CHC"}],
               "is_demo": False, "generated_at": "t0"}, open(path, "w"))
    m = P._production_manifest(demo, path)
    assert m["games"] == [{"matchup": "MIL @ CHC"}] and m["kept_from"] == "t0"
