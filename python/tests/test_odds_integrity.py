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


def test_picks_export_never_ships_record_elo_or_unflagged_fair_prices(tmp_path, monkeypatch):
    import picks_export as pe
    import verify_pricing as vp
    now = dt.datetime.now(dt.timezone.utc)
    (tmp_path / "today.json").write_text(json.dumps({"play_of_day": {
        "matchup": "NYY @ BOS", "label": "BOS_ML", "model_prob": 0.55, "market_price": -120,
        "edge_pct": 3.0, "odds_observed_at": (now - dt.timedelta(minutes=10)).isoformat(),
        "commence_time": (now + dt.timedelta(hours=3)).isoformat()}}))
    (tmp_path / "nba_state.json").write_text(json.dumps({"games": [
        # record-Elo only (no vetted p_home_display) -> must not be exported
        {"home_team": "MIA", "away_team": "DET", "p_home_win": 0.916, "home_record": "5-1",
         "away_record": "1-5", "state": "pre", "fair_home_american": -1090},
        {"home_team": "BOS", "away_team": "MIL", "p_home_display": 0.62, "p_source": "dk_no_vig",
         "home_record": "3-2", "away_record": "2-3", "state": "pre"}]}))
    (tmp_path / "player_pot.json").write_text(json.dumps({"top_5": [
        {"sport": "LOL", "label": "x OVER 3.5 Kills", "prob": 0.62, "fair_american": -163}]}))
    monkeypatch.setattr(pe, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pe, "JSON_PATH", str(tmp_path / "out.json"))
    monkeypatch.setattr(pe, "CSV_PATH", str(tmp_path / "out.csv"))
    out = pe.run()
    rows = {r["source_file"] + ":" + str(r["player_or_team"]): r for r in out["picks"]}
    assert not any(r["player_or_team"] == "MIA" for r in out["picks"])
    pod = rows["today.json:NYY @ BOS"]
    assert pod["book_american"] == -120 and pod["is_pick"] and pod["price_basis"] == "sportsbook"
    assert rows["nba_state.json:BOS"]["is_pick"] is False and rows["nba_state.json:BOS"]["fair_american"] == -163
    assert rows["player_pot.json:None"]["is_pick"] is False
    assert all(not vp.check_row(r, now) for r in out["picks"])


def test_cfb_edges_need_a_fresh_board_and_carry_its_time(tmp_path, monkeypatch):
    import cfb_model as cm
    real = json.load(open(cm.ODDS_PATH, encoding="utf-8"))
    games = [g for g in real.get("games") or [] if str(g.get("sport")).upper() == "NCAAF"][:40]
    later = (dt.datetime.utcnow() + dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%MZ")
    for g in games:
        g["status"], g["commence_time"] = "pre", later
    monkeypatch.setattr(cm, "OUT", str(tmp_path / "cfb.json"))
    for age, fresh in ((300, False), (20, True)):
        ts = (dt.datetime.utcnow() - dt.timedelta(minutes=age)).isoformat(timespec="seconds")
        (tmp_path / "odds.json").write_text(json.dumps({"generated_at": ts, "games": games}))
        monkeypatch.setattr(cm, "ODDS_PATH", str(tmp_path / "odds.json"))
        out = cm.run()
        if not out.get("games"):
            pytest.skip("no CFB ratings / board in this checkout")
        assert out["board_fresh"] is fresh
        if not fresh:
            assert out["edges"] == []
        assert all(e["odds_observed_at"] == ts for e in out["edges"])


def test_alpha_site_tweet_email_share_one_snapshot(tmp_path, monkeypatch):
    """A DK-priced pick day through the real composers: tweet text, tweet
    payload and email subject all carry the DK price, never the model's fair."""
    import alpha_tweet as at
    import alpha_email as ae
    import verify_pricing as vp
    rec = {"todays": {"date": "2026-11-05", "player_or_matchup": "NYY @ BOS", "market": "ML_HOME",
                      "sport": "MLB", "model_prob": 0.6, "model_prob_calibrated": 0.58,
                      "fair_american": -150, "book_american": -125, "rule": "v2"},
           "record": {"wins": 1, "losses": 0}, "history": []}
    (tmp_path / "alpha_pick_record.json").write_text(json.dumps(rec))
    for m in (at, ae):
        monkeypatch.setattr(m, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(at, "REC", str(tmp_path / "alpha_pick_record.json"))
    monkeypatch.setattr(at, "OUT", str(tmp_path / "alpha_tweet.json"))
    monkeypatch.setattr(ae, "OUT", str(tmp_path / "alpha_email.json"))
    monkeypatch.setattr(ae, "EMAIL_DIR", str(tmp_path / "emails"))
    tw = at.run()
    em = ae.compose()
    assert tw["picks"][0]["odds"] == "-125" and "-150" not in tw["tweet"]
    assert "@ -125" in em["subject"]
    assert vp.check_alpha_snapshot(rec, tw, em) == []
    assert vp._snapshot_self_test() == []


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


def test_board_prior_rejects_espn_placeholder_lines(tmp_path, monkeypatch):
    """ESPN files -100000/+5000 'DraftKings' lines on lopsided college games;
    de-vigged they read as a 98% market. They are no market at all."""
    import board_prior as bp
    snap = {"generated_at": "2026-11-05T17:00:00",
            "games": [{"sport": "NCAAB", "event_id": "1", "matchup": "BELL @ IU", "status": "pre",
                       "market": {"ml_home": -100000, "ml_away": 5000, "book": "draftkings"}},
                      {"sport": "NCAAB", "event_id": "2", "matchup": "WAKE @ VAN", "status": "pre",
                       "market": {"ml_home": -2800, "ml_away": 1300, "book": "draftkings"}},
                      {"sport": "NCAAB", "event_id": "3", "matchup": "A @ B", "status": "pre",
                       "market": {"ml_home": -150, "ml_away": 130, "book": "draftkings"}}]}
    (tmp_path / "espn_odds.json").write_text(json.dumps(snap))
    (tmp_path / "game_lines_desk.json").write_text("{}")
    monkeypatch.setattr(bp, "DATA_DIR", str(tmp_path))
    prior = bp.BoardPrior("ncaab")
    f1, f2, f3 = prior.for_event("1"), prior.for_event("2"), prior.for_event("3")
    assert f1["p_home_display"] is None and f1["dk_ml_home"] is None and f1.get("dk_placeholder")
    assert f2["p_home_display"] is not None          # -2800 is within the cap: a thin but real market
    assert 0.5 < f3["p_home_display"] < 0.6


# ---------------------------------------------------------------- cross-sport Play of the Day (2026-11-05)
def _pod_fixture(tmp_path, today, obs_minutes_ago=30, nfl_pick=True):
    now = dt.datetime(2026, 11, 8, 15, 0, tzinfo=dt.timezone.utc)
    obs = (now - dt.timedelta(minutes=obs_minutes_ago)).isoformat(timespec="seconds").replace("+00:00", "")
    q = lambda eid, start: {"provenance": "book_snapshot", "book": "draftkings", "observed_at": obs,
                            "event_id": eid, "scheduled_start": start}
    nfl_rows = [
        {"event_id": "1", "matchup": "NYJ @ KC", "commence": "2026-11-08T18:00Z", "p_home": 0.78, "ml_home": -500, "ml_away": 440,
         "game_date": today, "quote": q("1", "2026-11-08T18:00Z"),
         "pick": {"side": "away", "market": "ML_AWAY", "team": "NYJ", "prob": 0.22, "book_american": 440, "fair_american": 355, "ev": 0.17} if nfl_pick else None},
        {"event_id": "2", "matchup": "DAL @ IND", "commence": "2026-11-09T18:00Z", "p_home": 0.37, "ml_home": 195, "ml_away": -238,
         "game_date": "2026-11-09", "quote": q("2", "2026-11-09T18:00Z"),
         "pick": {"side": "home", "market": "ML_HOME", "team": "IND", "prob": 0.37, "book_american": 195, "fair_american": 171, "ev": 0.05}},
    ]
    gld = {"sports": {"nfl": {"verdict": "UNPROVEN: the blend edges the close", "proven": False, "board": nfl_rows},
                      "nba": {"verdict": "NO EDGE: the model adds nothing", "proven": False, "w_used": 0.0,
                              "board": [{"event_id": "3", "matchup": "BOS @ MIA", "game_date": today, "pick": None,
                                         "ml_home": -120, "ml_away": 100, "p_home": 0.52, "quote": q("3", "2026-11-09T00:30Z")}]}}}
    cfb = {"board_fresh": True, "games": [], "edges": [
        {"matchup": "FSU @ BC", "side": "HOME", "team": "BC", "market": "cfb_model_ml_home", "event_id": "9", "game_date": today,
         "commence_time": "2026-11-08T20:00Z", "calibrated_prob": 0.40, "book_implied_devig": 0.33, "book_american": 200,
         "fair_american": 150, "edge_pct": 30.0, "odds_observed_at": obs}]}
    (tmp_path / "game_lines_desk.json").write_text(json.dumps(gld))
    (tmp_path / "cfb_model.json").write_text(json.dumps(cfb))
    (tmp_path / "today.json").write_text(json.dumps({"no_games": True, "games": []}))
    return now


def test_play_of_day_prefers_major4_today_and_labels_tier(tmp_path, monkeypatch):
    import play_of_day as pod
    import verify_pricing as vp
    today = "2026-11-08"
    now = _pod_fixture(tmp_path, today)
    monkeypatch.setattr(pod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pod, "OUT", str(tmp_path / "play_of_day.json"))
    monkeypatch.setattr(pod, "_today_et", lambda: today)
    out = pod.run(now=now)
    play = out["play"]
    # the NFL forward-test play beats a higher-EV college edge (major-4 first, tier first)
    assert play["sport"] == "NFL" and play["team"] == "NYJ" and play["tier"] == 2
    assert play["book_american"] == 440 and play["desk_verdict"] == "UNPROVEN" and play["is_pick"] is True
    assert "forward-test" in play["tier_label"]
    assert out["next_play"]["game_date"] == "2026-11-09" and out["next_play"]["team"] == "IND"
    assert vp.check_row(play, now) == []                       # the guard accepts it as a priced pick
    assert out["by_sport"]["NBA"]["verdict"] == "NO EDGE"


def test_play_of_day_no_play_when_quote_stale_or_desk_no_edge(tmp_path, monkeypatch):
    import play_of_day as pod
    today = "2026-11-08"
    now = _pod_fixture(tmp_path, today, obs_minutes_ago=600)   # 10h-old DK quote
    monkeypatch.setattr(pod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pod, "OUT", str(tmp_path / "play_of_day.json"))
    monkeypatch.setattr(pod, "_today_et", lambda: today)
    out = pod.run(now=now)
    assert out["play"] is None
    reasons = " | ".join(out["no_play_reasons"])
    assert "NFL" in reasons and "NO EDGE" in reasons and "no picks by rule" in reasons
    # with no major-4 pick, the college edge is the (labelled, tier-3) fallback; the NO EDGE NBA desk never is
    now = _pod_fixture(tmp_path, today, nfl_pick=False)
    out = pod.run(now=now)
    assert out["play"]["sport"] == "NCAAF" and out["play"]["tier"] == 3 and "experimental" in out["play"]["tier_label"]
    assert all(c["sport"] != "NBA" for c in out["candidates_today"])


def test_ledger_harvests_the_cross_sport_pod_after_the_desk_row(tmp_path, monkeypatch):
    import all_picks_tracker as t
    today = "2026-11-08"
    _pod_fixture(tmp_path, today)
    (tmp_path / "play_of_day.json").write_text(json.dumps({"play": {
        "sport": "NFL", "matchup": "NYJ @ KC", "market": "ML_AWAY", "model_prob": 0.22, "ev_pct": 17.0,
        "fair_american": 355, "book_american": 440, "game_date": today, "event_id": "1", "desk_verdict": "UNPROVEN", "tier": 2,
        "quote": {"provenance": "book_snapshot", "observed_at": "2026-11-08T14:30:00"}}}))
    monkeypatch.setattr(t, "DATA_DIR", str(tmp_path))
    rows = t._collect_picks_from_sources()
    desk = [i for i, r in enumerate(rows) if r.get("source") == "nfl_game_ml" and r.get("player_or_matchup") == "NYJ @ KC"]
    podr = [i for i, r in enumerate(rows) if r.get("source") == "pod" and r.get("player_or_matchup") == "NYJ @ KC"]
    assert desk and podr and desk[0] < podr[0]          # desk row first: the add-guard folds the POD onto it
    assert rows[podr[0]]["book_american"] == 440 and rows[podr[0]]["event_id"] == "1"


# ---------------------------------------------------------------- NBA availability model (2026-11-11)
def _nba_game(d, h, a, home_players, away_players, gid):
    """players: {athlete_id: (minutes, game_score)}"""
    p = [[1, k, m, int(gs * 10)] for k, (m, gs) in home_players.items()] + \
        [[0, k, m, int(gs * 10)] for k, (m, gs) in away_players.items()]
    return {"id": gid, "d": d, "h": h, "a": a, "p": p}


def test_nba_game_score_matches_hollinger():
    import nba_avail as na
    names = ["MIN", "PTS", "FG", "3PT", "FT", "REB", "AST", "TO", "STL", "BLK", "OREB", "DREB", "PF", "+/-"]
    vals = ["31", "22", "8-16", "4-7", "2-2", "8", "3", "0", "1", "0", "3", "5", "2", "-23"]
    mins, gs = na.game_score(names, vals)
    # 22 + .4*8 - .7*16 - .4*(2-2) + .7*3 + .3*5 + 1 + .7*3 + .7*0 - .4*2 - 0
    assert mins == 31 and abs(gs - 19.9) < 1e-6


def test_nba_availability_is_walk_forward_and_sees_a_missing_star():
    import nba_avail as na
    star = {"S": (36, 28.0)}
    role = {f"H{i}": (24, 8.0) for i in range(7)}
    away = {f"A{i}": (30, 10.0) for i in range(8)}
    games = []
    for i in range(12):                                   # the star plays 12 straight
        games.append(_nba_game(f"2026-11-{i + 1:02d}", "HOM", "AWY", {**star, **role}, away, f"g{i}"))
    games.append(_nba_game("2026-11-14", "HOM", "AWY", role, away, "g12"))      # star sits
    feats, st = na.history_features(games)
    # while he plays, nothing is missing; the game he sits shows value missing for the HOME side
    assert abs(feats[("2026-11-10", "AWY", "HOM")]["avail"]) < 1e-9
    f = feats[("2026-11-14", "AWY", "HOM")]
    assert f["l_home"] > 12 and f["avail"] < -12          # away - home: negative = bad for home
    # walk-forward: the first game has no history, so no roster and no value missing
    assert feats[("2026-11-01", "AWY", "HOM")]["l_home"] == 0
    # live projection from an injury report: Out counts fully, Day-To-Day at half and blocks
    out = na.project(st, "HOM", "2026-11-16", {"S": {"status": "Out", "name": "Star"}})
    dtd = na.project(st, "HOM", "2026-11-16", {"S": {"status": "Day-To-Day", "name": "Star"}})
    assert out["missing_value"] > 12 and out["certain"] is True
    assert abs(dtd["missing_value"] - out["missing_value"] / 2) < 0.02 and dtd["certain"] is False
    # a player who is not on this season's roster is ignored
    assert na.project(st, "HOM", "2026-11-16", {"ZZ": {"status": "Out", "name": "Nobody"}})["missing_value"] == 0
    assert st.b2b("HOM", "2026-11-15") is True and st.b2b("HOM", "2026-11-17") is False


# ---------------------------------------------------------------- Pages build serves what the pages fetch (2026-11-11)
def test_pages_config_serves_every_markdown_file_a_page_fetches():
    """_config.yml excludes *.md from the published site (CLAUDE.md, the launch
    kit, TODOs). A page that fetches a Markdown file needs that file's basename
    in `include`, and the optional-front-matter plugin must be off or GitHub
    Pages renders it to .html and the .md URL 404s."""
    import re
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    cfg = open(os.path.join(root, "_config.yml"), encoding="utf-8").read()
    m = re.search(r"^include:\n((?:\s+-\s+.*\n?)+)", cfg, re.M)
    included = set(re.findall(r"-\s+\"?([^\"\n]+?)\"?\s*$", m.group(1), re.M)) if m else set()
    assert re.search(r"^optional_front_matter:\n\s+enabled:\s*false", cfg, re.M), "Markdown would be rendered to .html"
    fetched = set()
    pages = [f for f in os.listdir(root) if f.endswith(".html")]
    pages += [os.path.join("js", f) for f in os.listdir(os.path.join(root, "js")) if f.endswith(".js")]
    for f in pages:
        src = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
        for path in re.findall(r"""(?:fetch\(\s*|href=|src=|path:\s*)["'`]([^"'`?#]+\.md)""", src):
            if not path.startswith(("http:", "https:", "//")):
                fetched.add(os.path.basename(path))
    assert fetched, "expected brief.html / daily-summary.html to fetch Markdown"
    assert fetched <= included, f"fetched but not served by the Pages build: {sorted(fetched - included)}"


# ---------------------------------------------------------------- Play of the Day share text (2026-11-11)
def test_play_of_day_post_quotes_a_price_only_for_todays_play(tmp_path, monkeypatch):
    """The copy-ready post is a draft a person sends. It may state a price only
    for today's actionable play, with the tier and when the price was seen; a
    no-play day (and the 'next' line) never carries a price."""
    import re
    import play_of_day as pod
    today = "2026-11-08"
    monkeypatch.setattr(pod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pod, "OUT", str(tmp_path / "play_of_day.json"))
    monkeypatch.setattr(pod, "_today_et", lambda: today)
    price = re.compile(r"(?<![\w/.])[+-]\d{3,}\b")
    out = pod.run(now=_pod_fixture(tmp_path, today))
    post = out["post"]
    assert post["kind"] == "play" and post["fits"] and post["chars"] == len(post["text"]) <= 280
    assert "NYJ moneyline +440 at DraftKings" in post["text"] and "Sun 11/8" in post["text"]
    assert "Forward test: this desk has not proven an edge." in post["text"]       # the tier always travels with the price
    assert "Price seen 9:30 AM ET." in post["text"] and "not betting advice" in post["text"]
    assert price.findall(post["text"]) == ["+440"]                                 # exactly the play's price, nothing else
    # stale quote -> no play: says so, names the NO EDGE desk, and carries no price at all
    out = pod.run(now=_pod_fixture(tmp_path, today, obs_minutes_ago=600))
    post = out["post"]
    assert out["play"] is None and post["kind"] == "no_play" and post["fits"]
    assert post["text"].startswith("No Play of the Day") and "NBA (1 game)" in post["text"] and "We don't force a bet." in post["text"]
    assert price.findall(post["text"]) == [] and "Next on the board" in post["text"]
    assert "posts automatically" in post["note"]


# ---------------------------------------------------------------- page scripts parse (2026-11-11)
def test_every_inline_page_script_parses():
    """An unescaped apostrophe inside a single-quoted JS string in alpha-pick.html
    (2026-11-05) killed that page's whole script block and nothing caught it.
    tools/check_inline_js.js parses (never runs) every inline script and js file."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    r = subprocess.run([node, os.path.join(root, "tools", "check_inline_js.js"), root], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-2000:]


# ---------------------------------------------------------------- page references resolve (2026-11-11)
def test_every_local_page_reference_is_served():
    """A link, script, image or fetch target on a page must be a file the Pages
    build serves: tracked, not excluded by _config.yml, no "_" or "." segment.
    (404.html shipped pointing at a favicon that does not exist.)"""
    import subprocess
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    if not os.path.isdir(os.path.join(root, ".git")):
        pytest.skip("not a git checkout")
    r = subprocess.run([sys.executable, os.path.join(root, "tools", "check_site_refs.py")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-2000:]



# ---------------------------------------------------------------- per-sport plays + model leans (2026-11-11)
def test_lean_rule_only_takes_a_favourite_the_model_and_the_market_agree_on():
    import game_lines_desk as gld
    # model 66% home, DK -180/+150 (no-vig ~61.6% home): both favour home, inside -300 -> lean home
    ln = gld.lean_side(0.66, -180, 150)
    assert ln["side"] == "home" and ln["market"] == "ML_HOME" and ln["book_american"] == -180
    assert abs(ln["score"] - min(0.66, ln["prob_dk"])) < 1e-4
    assert ln["ev_at_dk_no_vig"] < 0                       # at the market's own probability a lean is -EV: the margin
    # the model likes the underdog: that is a disagreement, never a lean (the lean study: those bets lose)
    assert gld.lean_side(0.35, -180, 150) is None
    # agreement, but too heavy a favourite (-450) or too close to a coin flip (52%) -> no lean
    assert gld.lean_side(0.85, -450, 340) is None
    assert gld.lean_side(0.53, -115, -105) is None
    # no price -> no lean
    assert gld.lean_side(0.66, None, 150) is None
    # walk-forward record: one lean per day, graded at the price
    rows = [{"date": "2026-11-01", "p_elo": 0.66, "ml_home": -180, "ml_away": 150, "y": 1.0},
            {"date": "2026-11-01", "p_elo": 0.60, "ml_home": -150, "ml_away": 126, "y": 0.0},   # lower score: not the day's lean
            {"date": "2026-11-02", "p_elo": 0.30, "ml_home": 170, "ml_away": -205, "y": 1.0},   # away favourite loses
            {"date": "2026-11-03", "p_elo": 0.35, "ml_home": -180, "ml_away": 150, "y": 1.0}]   # disagreement: no lean
    rec = gld.lean_backtest(rows)
    assert (rec["n"], rec["wins"], rec["losses"], rec["game_days"]) == (2, 1, 1, 3)
    assert abs(rec["units"] - (100 / 180 - 1)) < 0.01 and rec["expected_roi_pct_at_no_vig"] < 0


def _lean_fixture(tmp_path, today, nfl_pick):
    now = _pod_fixture(tmp_path, today, nfl_pick=nfl_pick)
    gld = json.loads((tmp_path / "game_lines_desk.json").read_text())
    nba = gld["sports"]["nba"]
    nba["lean"] = {"rule_text": "the favourite both agree on",
                   "backtest": {"n": 19, "wins": 11, "losses": 8, "units": -3.06, "roi_pct": -16.1,
                                "expected_roi_pct_at_no_vig": -4.0, "first_date": "2026-10-20", "last_date": "2026-11-07"}}
    row = nba["board"][0]
    row.update({"ml_home": -200, "ml_away": 168, "p_home": 0.641, "p_home_elo": 0.68, "commence": "2026-11-09T00:30Z",
                "lean": {"side": "home", "market": "ML_HOME", "team": "MIA", "score": 0.641, "prob_model": 0.68,
                         "prob_dk": 0.641, "book_american": -200, "fair_american": -179, "ev_at_dk_no_vig": -0.0385}})
    (tmp_path / "game_lines_desk.json").write_text(json.dumps(gld))
    (tmp_path / "cfb_model.json").write_text(json.dumps({"board_fresh": True, "games": [], "edges": []}))
    return now


def test_each_major_sport_gets_a_play_and_a_lean_is_featured_only_as_a_last_resort(tmp_path, monkeypatch):
    import re
    import play_of_day as pod
    import verify_pricing as vp
    today = "2026-11-08"
    monkeypatch.setattr(pod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pod, "OUT", str(tmp_path / "play_of_day.json"))
    monkeypatch.setattr(pod, "_today_et", lambda: today)
    # an NFL desk pick and an NBA lean on the same day: both are sport plays, the desk pick is featured
    now = _lean_fixture(tmp_path, today, nfl_pick=True)
    out = pod.run(now=now)
    sp = {x["sport"]: x for x in out["sport_plays"]}
    assert set(sp) == {"NFL", "NBA"}
    assert out["play"]["sport"] == "NFL" and out["play"]["tier"] == 2 and sp["NFL"]["featured"] and not sp["NBA"]["featured"]
    lean = sp["NBA"]
    assert lean["tier"] == 4 and lean["is_lean"] and lean["team"] == "MIA" and lean["book_american"] == -200
    assert "not a proven edge" in lean["why"] and lean["ev_pct"] < 0 and lean["lean_record"]["n"] == 19
    assert "model lean" in lean["tier_label"]
    assert vp.check_row(lean, now) == []                         # a lean still needs a live pre-start DK quote
    post = out["post"]
    assert post["kind"] == "plays" and post["fits"]
    assert "NFL: NYJ moneyline +440 (forward test)" in post["text"] and "NBA: MIA moneyline -200 (lean)" in post["text"]
    assert "A lean is not a proven edge." in post["text"]
    assert sorted(re.findall(r"(?<![\w/.])[+-]\d{3,}\b", post["text"])) == ["+440", "-200"]
    # the next dated play is never a lean
    assert out["next_play"]["tier"] != 4
    # no desk pick anywhere: the lean is the featured play, labelled, and the post says what it is
    now = _lean_fixture(tmp_path, today, nfl_pick=False)
    out = pod.run(now=now)
    assert out["play"]["tier"] == 4 and out["play"]["sport"] == "NBA" and out["no_play_reasons"] == []
    assert "Model lean, not a proven edge" in out["post"]["text"] and "agree on the favourite" in out["post"]["text"]
    # a stale quote kills the lean like any other play
    now = _lean_fixture(tmp_path, today, nfl_pick=False)
    out = pod.run(now=now + dt.timedelta(hours=9))
    assert out["play"] is None and out["sport_plays"] == []


def test_a_lean_is_logged_under_its_own_source_and_never_as_the_curated_pod(tmp_path, monkeypatch):
    import all_picks_tracker as t
    import play_of_day as pod
    today = "2026-11-08"
    monkeypatch.setattr(pod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pod, "OUT", str(tmp_path / "play_of_day.json"))
    monkeypatch.setattr(pod, "_today_et", lambda: today)
    out = pod.run(now=_lean_fixture(tmp_path, today, nfl_pick=False))      # featured play = the NBA lean
    assert out["play"]["tier"] == 4
    out.pop("generated_at")          # the fixture's clock is days old; the ledger skips sources older than 48h
    (tmp_path / "play_of_day.json").write_text(json.dumps(out))
    monkeypatch.setattr(t, "DATA_DIR", str(tmp_path))
    rows = t._collect_picks_from_sources()
    leans = [r for r in rows if r.get("source") == "sport_lean"]
    assert len(leans) == 1 and leans[0]["sport"] == "NBA" and leans[0]["market"] == "ML_HOME"
    assert leans[0]["book_american"] == -200 and leans[0]["date"] == today and leans[0]["desk_verdict"] == "lean"
    assert not [r for r in rows if r.get("source") == "pod"]         # a featured lean is not a "pod" pick


def test_nba_moneyline_is_graded_on_the_final_by_event_id():
    import all_picks_tracker as t
    games = [{"id": "77", "date": "2026-11-08", "home_abbrev": "MIA", "away_abbrev": "BOS", "home_score": 111, "away_score": 104},
             {"id": "78", "date": "2026-11-09", "home_abbrev": "BOS", "away_abbrev": "MIA", "home_score": 99, "away_score": 120}]
    win = {"sport": "NBA", "market": "ML_HOME", "player_or_matchup": "BOS @ MIA", "date": "2026-11-08", "event_id": "77"}
    assert t._grade_wnba_pick(win, {}, games) == "won" and "BOS 104 @ MIA 111" in win["outcome"]["verify"]
    lose = {"sport": "NBA", "market": "ML_AWAY", "player_or_matchup": "BOS @ MIA", "date": "2026-11-08", "event_id": "77"}
    assert t._grade_wnba_pick(lose, {}, games) == "lost"
    # no event id: the date + teams path finds the same game; a game that has not been played is not graded
    assert t._grade_wnba_pick({"sport": "NBA", "market": "ML_HOME", "player_or_matchup": "BOS @ MIA", "date": "2026-11-08"}, {}, games) == "won"
    assert t._grade_wnba_pick({"sport": "NBA", "market": "ML_HOME", "player_or_matchup": "LAL @ DEN", "date": "2026-11-08", "event_id": "90"}, {}, games) is None
