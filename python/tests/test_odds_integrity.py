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
