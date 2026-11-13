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
    # agreement, but too heavy a favourite (-450, or -250 since the 11/13 cap at -200) or too close to a coin flip (52%) -> no lean
    assert gld.lean_side(0.85, -450, 340) is None
    assert gld.lean_side(0.74, -250, 205) is None and gld.lean_side(0.70, -200, 168)["book_american"] == -200
    assert gld.lean_side(0.53, -115, -105) is None
    # no price -> no lean
    assert gld.lean_side(0.66, None, 150) is None
    # walk-forward record: one lean per day, graded at the price
    rows = [{"date": "2026-11-01", "p_elo": 0.66, "ml_home": -180, "ml_away": 150, "y": 1.0},
            {"date": "2026-11-01", "p_elo": 0.60, "ml_home": -150, "ml_away": 126, "y": 0.0},   # lower score: not the day's lean
            {"date": "2026-11-02", "p_elo": 0.30, "ml_home": 160, "ml_away": -190, "y": 1.0},   # away favourite loses
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


def test_lean_forward_record_counts_only_live_settled_leans():
    import all_picks_tracker as t
    h = [{"source": "sport_lean", "sport": "NBA", "player_or_matchup": "GS @ HOU", "market": "ML_HOME", "book_american": -264,
          "date": "2026-11-11", "settled": True, "result": "won", "payout_units": 0.379, "outcome": {"final_score": "GS 101 @ HOU 112"}},
         {"source": "sport_lean", "sport": "NHL", "player_or_matchup": "PHI @ EDM", "market": "ML_HOME", "book_american": -192,
          "date": "2026-11-11", "settled": True, "result": "lost", "payout_units": -1.0},
         {"source": "sport_lean", "sport": "NHL", "player_or_matchup": "PIT @ SJ", "market": "ML_AWAY", "book_american": -142,
          "date": "2026-11-12", "settled": False},
         {"source": "sport_lean", "sport": "NBA", "player_or_matchup": "A @ B", "market": "ML_HOME", "book_american": -150,
          "date": "2026-11-12", "settled": True, "voided": True, "result": "won", "payout_units": 0.67},      # voided: not counted
         {"source": "pod", "sport": "NFL", "player_or_matchup": "X @ Y", "market": "ML_HOME", "date": "2026-11-09",
          "settled": True, "result": "won", "payout_units": 1.0}]                                             # not a lean
    b = t._sport_leans_block(h)
    assert (b["n_settled"], b["wins"], b["losses"], b["n_pending"]) == (2, 1, 1, 1) and abs(b["net_units"] + 0.621) < 1e-9
    assert b["by_sport"]["NBA"]["wins"] == 1 and b["by_sport"]["NHL"]["n_pending"] == 1
    assert b["first_date"] == "2026-11-11" and [r["team"] for r in b["recent"]] == ["PIT", "EDM", "HOU"]
    assert b["recent"][0]["result"] == "pending" and b["recent"][2]["final"] == "GS 101 @ HOU 112"
    assert "never part of the curated record" in b["definition"]


def test_sport_plays_history_separates_desk_picks_from_leans(tmp_path, monkeypatch):
    import all_picks_tracker as t
    import play_of_day as pod
    h = [{"source": "nfl_game_ml", "also_sources": ["pod", "sport_play"], "sport": "NFL", "player_or_matchup": "HOU @ CLE",
          "market": "ML_HOME", "book_american": 190, "date": "2026-11-15", "settled": True, "result": "won", "payout_units": 1.9},
         {"source": "nfl_game_ml", "sport": "NFL", "player_or_matchup": "SF @ DAL", "market": "ML_AWAY", "book_american": -205,
          "date": "2026-11-15", "settled": True, "result": "lost", "payout_units": -1.0},                      # a desk pick, not the sport play
         {"source": "sport_lean", "sport": "NBA", "player_or_matchup": "GS @ HOU", "market": "ML_HOME", "book_american": -264,
          "date": "2026-11-11", "settled": True, "result": "lost", "payout_units": -1.0},
         {"source": "sport_lean", "sport": "NHL", "player_or_matchup": "PHI @ EDM", "market": "ML_HOME", "book_american": -192,
          "date": "2026-11-12", "settled": False}]
    b = t._sport_plays_block(h)
    assert (b["desk_picks"]["wins"], b["desk_picks"]["losses"], b["desk_picks"]["net_units"]) == (1, 0, 1.9)
    assert (b["leans"]["wins"], b["leans"]["losses"], b["leans"]["n_pending"]) == (0, 1, 1)
    assert [(r["sport"], r["kind"], r["team"], r["result"]) for r in b["recent"]] == [
        ("NFL", "desk pick", "CLE", "won"), ("NHL", "lean", "EDM", "pending"), ("NBA", "lean", "HOU", "lost")]
    assert "never summed" in b["definition"]
    # the collector tags a desk-pick sport play as "sport_play" (after the desk row) and never as a lean
    today = "2026-11-08"
    monkeypatch.setattr(pod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(pod, "OUT", str(tmp_path / "play_of_day.json"))
    monkeypatch.setattr(pod, "_today_et", lambda: today)
    out = pod.run(now=_lean_fixture(tmp_path, today, nfl_pick=True))
    out.pop("generated_at")
    (tmp_path / "play_of_day.json").write_text(json.dumps(out))
    monkeypatch.setattr(t, "DATA_DIR", str(tmp_path))
    rows = t._collect_picks_from_sources()
    src = [(r["source"], r["sport"]) for r in rows if r.get("source") in ("sport_play", "sport_lean")]
    assert src == [("sport_play", "NFL"), ("sport_lean", "NBA")]
    desk_i = next(i for i, r in enumerate(rows) if r.get("source") == "nfl_game_ml" and r.get("player_or_matchup") == "NYJ @ KC")
    play_i = next(i for i, r in enumerate(rows) if r.get("source") == "sport_play")
    assert desk_i < play_i and not t_is_curated_source("sport_play") and not t_is_curated_source("sport_lean")


def t_is_curated_source(src):
    """Mirror of the ledger's curated-prefix rule, read from its source so the test fails if a prefix ever swallows these."""
    import re
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "all_picks_tracker.py")
    text = open(path, encoding="utf-8").read()
    m = re.search(r"_CURATED_PREFIXES = \(([^)]*)\)", text)
    prefixes = re.findall(r'"([^"]+)"', m.group(1))
    return any(src == p or src.startswith(p) for p in prefixes)


# ---------------------------------------------------------------- The Board (2026-11-12)
def _board_fixture(tmp_path, monkeypatch, today="2026-11-08", nfl_pick=True):
    import board
    import play_of_day as pod
    now = _lean_fixture(tmp_path, today, nfl_pick=nfl_pick)
    gld = json.loads((tmp_path / "game_lines_desk.json").read_text())
    obs = gld["sports"]["nba"]["board"][0]["quote"]["observed_at"]
    q = lambda eid: {"provenance": "book_snapshot", "book": "draftkings", "observed_at": obs,
                     "event_id": eid, "scheduled_start": "2026-11-09T01:00Z"}
    gld["sports"]["nba"]["board"] += [
        # model likes the home side, DraftKings the away side: a disagreement -> D 25, no bet
        {"event_id": "21", "matchup": "LAL @ DEN", "game_date": today, "commence": "2026-11-09T01:00Z", "pick": None,
         "p_home_elo": 0.60, "p_home_dk": 0.45, "p_home": 0.45, "ml_home": 120, "ml_away": -142, "quote": q("21")},
        # both lean home, but under 55%: outside the lean rule -> D 35, no bet
        {"event_id": "22", "matchup": "NY @ CHI", "game_date": today, "commence": "2026-11-09T01:00Z", "pick": None,
         "p_home_elo": 0.53, "p_home_dk": 0.52, "p_home": 0.52, "ml_home": -112, "ml_away": -108, "quote": q("22")},
        # a day-to-day star: on hold, no side at all
        {"event_id": "23", "matchup": "PHX @ GS", "game_date": today, "commence": "2026-11-09T01:00Z", "pick": None,
         "p_home_elo": 0.70, "p_home_dk": 0.66, "p_home": 0.66, "ml_home": -200, "ml_away": 168, "quote": q("23"),
         "pick_blocked": "availability uncertain -- GS: 5.1 pts of Day-To-Day value (Star)"},
    ]
    (tmp_path / "game_lines_desk.json").write_text(json.dumps(gld))
    (tmp_path / "espn_odds.json").write_text(json.dumps({"generated_at": obs, "games": [
        {"sport": "NBA", "event_id": "3", "market": {"total": 221.5, "over_price": -108, "under_price": -112, "spread": -4.5}}]}))
    for mod in (board, pod):
        monkeypatch.setattr(mod, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(board, "OUT", str(tmp_path / "board.json"))
    monkeypatch.setattr(board, "ALPHA_LOG", str(tmp_path / "board_alpha_log.json"))
    monkeypatch.setattr(pod, "OUT", str(tmp_path / "play_of_day.json"))
    monkeypatch.setattr(pod, "_today_et", lambda: today)
    return board, now


def test_board_grades_every_game_by_rule_and_only_abc_are_bets(tmp_path, monkeypatch):
    import verify_pricing as vp
    board, now = _board_fixture(tmp_path, monkeypatch)
    # the whole scoring rule
    # risk-adjusted (EV per unit of risk) for desk picks; raw EV only as the fallback
    assert board.score_pick("desk", 1, 6.0, None, 0.30) == {"grade": "A", "score": 100}
    assert board.score_pick("desk", 2, 40.0, None, 0.06) == {"grade": "B", "score": 68}   # big EV, big swings
    assert board.score_pick("desk", 2, 5.0, None, 0.90) == {"grade": "B", "score": 80}    # capped at the band
    assert board.score_pick("desk", 2, 5.0, None) == {"grade": "B", "score": 70}          # no risk number: raw EV
    dog, fav = board.risk(0.217, 440), board.risk(0.889, -440)
    assert dog["ev_pct"] > fav["ev_pct"] and fav["risk_adj"] > 2.5 * dog["risk_adj"]       # the longshot has more EV, less per unit of risk
    assert fav["favorite"] and not dog["favorite"] and abs(dog["pays"] - 4.4) < 1e-9
    assert board.risk(None, -110) is None and board.risk(0.5, None) is None and board.risk(1.2, -110) is None
    assert board.score_pick("lean", 4, -3.9, 0.55) == {"grade": "C", "score": 40}
    assert board.score_pick("lean", 4, -3.9, 0.80) == {"grade": "C", "score": 60}
    out = board.run(now=now)
    g = {x["matchup"]: x for x in out["games"]}
    nyj = g["NYJ @ KC"]
    assert nyj["grade"] == "B" and nyj["pick"]["team"] == "NYJ" and nyj["pick"]["risk"]["favorite"] is False
    assert nyj["score"] == int(round(65 + min(15, 15 * nyj["pick"]["risk"]["risk_adj"] / 0.30)))    # risk-adjusted, not raw EV
    assert g["BOS @ MIA"]["pick"]["risk"]["ev_pct"] < 0 and g["BOS @ MIA"]["pick"]["risk"]["favorite"]  # a lean: at the market's price
    assert g["BOS @ MIA"]["grade"] == "C" and g["BOS @ MIA"]["pick"]["kind"] == "lean" and 40 <= g["BOS @ MIA"]["score"] <= 60
    assert g["BOS @ MIA"]["odds"]["total"] == 221.5 and g["BOS @ MIA"]["odds"]["over_price"] == -108   # the real over/under prices
    d1, d2, hold = g["LAL @ DEN"], g["NY @ CHI"], g["PHX @ GS"]
    assert (d1["grade"], d1["score"], d1["pick"]) == ("D", 25, None) and d1["model_side"]["team"] == "DEN" and "lost this season" in d1["reason"]
    assert (d2["grade"], d2["score"], d2["pick"]) == ("D", 35, None) and d2["model_side"]["agrees_with_market"] is True
    assert (hold["grade"], hold["score"], hold["pick"], hold["model_side"]) == ("HOLD", None, None, None) and hold["hold"]
    # only A/B/C are bets: the flat list the guard checks and the ledger logs
    assert sorted((p["matchup"], p["grade"]) for p in out["picks"]) == [("BOS @ MIA", "C"), ("DAL @ IND", "B"), ("NYJ @ KC", "B")]
    assert all(vp.check_row(p, now) == [] for p in out["picks"])
    assert out["sports"]["NBA"]["games_today"] == 4 and out["sports"]["NBA"]["bets_today"] == 1
    assert out["sports"]["MLB"]["status"] == "off-season" and out["days"] == ["2026-11-08", "2026-11-09"]
    # a stale board has no bets at all (no live quote, no pick), and says nothing about alpha
    out = board.run(now=now + dt.timedelta(hours=9))
    assert out["picks"] == [] and out["alpha"]["picks"] == []
    assert all(x["grade"] is None and x["pick"] is None and x["model_side"] is None and "No live DraftKings quote" in x["reason"]
               for x in out["games"])                                    # an old price backs neither a bet nor a "no bet"


def test_alpha_is_the_top_scored_bets_and_locks_at_eleven(tmp_path, monkeypatch):
    board, now = _board_fixture(tmp_path, monkeypatch)                 # 10:00 ET
    out = board.run(now=now)
    a = out["alpha"]
    assert a["status"] == "provisional" and [(p["team"], p["grade"]) for p in a["picks"]] == [("NYJ", "B"), ("MIA", "C")]
    assert a["note"] and "not padded" in a["note"]                       # two bets: the list is not filled out to three
    assert not (tmp_path / "board_alpha_log.json").exists() and not any(p["is_alpha"] for p in out["picks"])
    out = board.run(now=now + dt.timedelta(hours=2))                     # 12:00 ET -> locks
    a = out["alpha"]
    assert a["status"] == "locked" and [p["team"] for p in a["picks"]] == ["NYJ", "MIA"] and all(p["locked"] for p in a["picks"])
    assert sorted(p["team"] for p in out["picks"] if p["is_alpha"]) == ["MIA", "NYJ"]
    assert [x["alpha_rank"] for x in out["games"] if x["matchup"] == "NYJ @ KC"] == [1]
    log = json.loads((tmp_path / "board_alpha_log.json").read_text())
    assert [p["book_american"] for p in log["days"]["2026-11-08"]["picks"]] == [440, -200]
    # the price moves and the desk pick disappears: the locked list does not change or re-price
    gld = json.loads((tmp_path / "game_lines_desk.json").read_text())
    gld["sports"]["nfl"]["board"][0]["pick"] = None
    gld["sports"]["nba"]["board"][0]["lean"]["book_american"] = -230
    (tmp_path / "game_lines_desk.json").write_text(json.dumps(gld))
    out = board.run(now=now + dt.timedelta(hours=2, minutes=20))
    assert [(p["team"], p["book_american"]) for p in out["alpha"]["picks"]] == [("NYJ", 440), ("MIA", -200)]


def test_board_bets_are_logged_on_game_day_only_never_curated_and_never_calibration_evidence(tmp_path, monkeypatch):
    import all_picks_tracker as t
    import prob_calibration as pc
    board, now = _board_fixture(tmp_path, monkeypatch)
    out = board.run(now=now + dt.timedelta(hours=2))
    out.pop("generated_at")
    (tmp_path / "board.json").write_text(json.dumps(out))
    monkeypatch.setattr(t, "DATA_DIR", str(tmp_path))
    rows = t._collect_picks_from_sources()
    tagged = sorted((r["source"], r["player_or_matchup"]) for r in rows if r.get("source") in ("board_pick", "board_alpha"))
    # today's two bets, each also an alpha pick; tomorrow's DAL @ IND desk pick (grade B, an edge at today's
    # price) is taken now, when the edge appears -- only leans wait for their game day
    assert tagged == [("board_alpha", "BOS @ MIA"), ("board_alpha", "NYJ @ KC"), ("board_pick", "BOS @ MIA"),
                      ("board_pick", "DAL @ IND"), ("board_pick", "NYJ @ KC")]
    future = next(r for r in rows if r.get("source") == "board_pick" and r["player_or_matchup"] == "DAL @ IND")
    assert future["board_grade"] == "B" and future["date"] == "2026-11-09" and future["board_price"] == 195
    # a lean for a later day is NOT taken early
    b2 = json.loads((tmp_path / "board.json").read_text())
    b2["picks"].append(dict(next(p for p in b2["picks"] if p["matchup"] == "BOS @ MIA"), matchup="X @ Y", game_date="2026-11-09",
                            event_id="99", is_alpha=False))
    (tmp_path / "board.json").write_text(json.dumps(b2))
    assert not [r for r in t._collect_picks_from_sources() if r.get("player_or_matchup") == "X @ Y"]
    desk_i = next(i for i, r in enumerate(rows) if r.get("source") == "nfl_game_ml" and r.get("player_or_matchup") == "NYJ @ KC")
    assert all(i > desk_i for i, r in enumerate(rows) if r.get("source") in ("board_pick", "board_alpha"))   # folds onto the desk row
    for src in ("board_pick", "board_alpha"):
        assert not t_is_curated_source(src)
        assert pc.judged({"source": src, "sport": "NBA", "market": "ML_HOME"}) is False       # a lean is not evidence about the model
    assert pc.judged({"source": "sport_lean", "sport": "NHL", "market": "ML_HOME"}) is False
    assert pc.judged({"source": "nhl_game_ml", "sport": "NHL", "market": "ML_HOME"}) is True  # a desk pick still is
    # results: grade from what the row is; alpha counted on its own; voided rows out
    h = [{"source": "nfl_game_ml", "also_sources": ["board_pick", "board_alpha"], "desk_verdict": "unproven", "sport": "NFL",
          "player_or_matchup": "NYJ @ KC", "market": "ML_AWAY", "book_american": 440, "date": "2026-11-08", "settled": True,
          "result": "lost", "payout_units": -1.0},
         {"source": "sport_lean", "also_sources": ["board_pick"], "sport": "NBA", "player_or_matchup": "BOS @ MIA", "market": "ML_HOME",
          "book_american": -200, "date": "2026-11-08", "settled": True, "result": "won", "payout_units": 0.5,
          "outcome": {"final_score": "BOS 99 @ MIA 110"}},
         {"source": "board_pick", "sport": "NHL", "player_or_matchup": "WSH @ NJ", "market": "ML_HOME", "book_american": -155,
          "date": "2026-11-09", "settled": False},
         {"source": "board_pick", "sport": "NHL", "player_or_matchup": "A @ B", "market": "ML_HOME", "book_american": -150,
          "date": "2026-11-09", "settled": True, "voided": True, "result": "won", "payout_units": 0.67},
         {"source": "nfl_game_ml", "sport": "NFL", "player_or_matchup": "X @ Y", "market": "ML_HOME", "date": "2026-11-08",
          "settled": True, "result": "won", "payout_units": 1.0}]                                # a desk pick the board never showed
    b = t._board_block(h)
    assert (b["all_bets"]["wins"], b["all_bets"]["losses"], b["all_bets"]["n_pending"]) == (1, 1, 1)
    assert (b["alpha"]["wins"], b["alpha"]["losses"]) == (0, 1)
    assert b["by_grade"]["B"]["losses"] == 1 and b["by_grade"]["C"]["wins"] == 1 and b["by_grade"]["A"]["n_settled"] == 0
    assert [(r["team"], r["grade"], r["is_alpha"], r["result"]) for r in b["recent"]] == [
        ("NJ", "C", False, "pending"), ("NYJ", "B", True, "lost"), ("MIA", "C", False, "won")]
    assert b["by_day"]["2026-11-08"]["wins"] == 1 and "not" in b["definition"]


# ---------------------------------------------------------------- independent review fixes (2026-11-12)
def test_board_record_uses_the_price_the_board_showed_not_an_earlier_logged_price():
    import all_picks_tracker as t
    # a desk pick logged days earlier at +440; the board showed +380 on game day and locked it as Alpha at +360
    h = [{"source": "nfl_game_ml", "also_sources": ["board_pick", "board_alpha"], "desk_verdict": "unproven", "sport": "NFL",
          "player_or_matchup": "NYJ @ KC", "market": "ML_AWAY", "book_american": 440, "board_price": 380, "alpha_price": 360,
          "board_grade": "C", "date": "2026-11-08", "settled": True, "result": "won", "payout_units": 4.4},
         {"source": "board_pick", "sport": "NBA", "player_or_matchup": "BOS @ MIA", "market": "ML_HOME", "book_american": -200,
          "board_price": -200, "board_grade": "C", "date": "2026-11-08", "settled": True, "result": "lost", "payout_units": -1.0}]
    b = t._board_block(h)
    assert b["all_bets"]["net_units"] == 2.8          # +3.80 (the board's price) - 1.00, not +4.40 - 1.00
    assert b["alpha"]["net_units"] == 3.6             # the locked Alpha price
    assert b["by_grade"]["C"]["wins"] == 1 and b["by_grade"]["B"]["n_settled"] == 0      # the stamped grade, not the desk's
    nyj = next(r for r in b["recent"] if r["team"] == "NYJ")
    assert nyj["book_american"] == 360 and nyj["payout_units"] == 3.6 and nyj["grade"] == "C"
    # the ledger source carries the two guards the review asked for
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "all_picks_tracker.py"), encoding="utf-8").read()
    assert 'if p.get("source") in ("sport_lean", "board_pick", "board_alpha"):\n            return False' in src       # never curated
    assert 'for k in ("board_price", "board_grade", "board_score", "alpha_price"):' in src                              # stamped on fold


def test_alpha_lock_fails_closed_and_a_non_draftkings_quote_is_never_a_bet(tmp_path, monkeypatch):
    board, now = _board_fixture(tmp_path, monkeypatch)
    lock = tmp_path / "board_alpha_log.json"
    lock.write_text('{"days": {"2026-11-01": {"picks": [')          # truncated write / bad merge
    out = board.run(now=now + dt.timedelta(hours=2))                 # 12:00 ET: would normally lock
    assert out["alpha"]["status"] == "provisional" and "could not be read" in out["alpha"]["note"]
    assert lock.read_text() == '{"days": {"2026-11-01": {"picks": ['  # untouched: earlier days are not erased
    assert not any(p["is_alpha"] for p in out["picks"])              # nothing is tagged Alpha off an unlocked list
    lock.unlink()
    # another provider's price is a real price, but the board says DraftKings: no grade, no bet
    gld = json.loads((tmp_path / "game_lines_desk.json").read_text())
    gld["sports"]["nba"]["board"][0]["quote"]["book"] = "espn bet"
    (tmp_path / "game_lines_desk.json").write_text(json.dumps(gld))
    out = board.run(now=now)
    g = next(x for x in out["games"] if x["matchup"] == "BOS @ MIA")
    assert g["pick"] is None and g["grade"] is None and g["live_quote"] is False and g["quote_issue"] == "not_draftkings"
    assert all(p["matchup"] != "BOS @ MIA" for p in out["picks"])
    # today stays on the board after its last game starts (the locked list and results still belong to it)
    for sp in gld["sports"].values():
        sp["board"] = [r for r in sp["board"] if r.get("game_date") != "2026-11-08"]
    (tmp_path / "game_lines_desk.json").write_text(json.dumps(gld))
    out = board.run(now=now)
    assert out["days"][0] == "2026-11-08" and out["counts"]["games_today"] == 0


def test_alpha_tag_carries_the_locked_price_not_the_current_line(tmp_path, monkeypatch):
    import all_picks_tracker as t
    board, now = _board_fixture(tmp_path, monkeypatch)
    out = board.run(now=now + dt.timedelta(hours=2))                       # locks MIA at -200
    assert [(p["team"], p["book_american"]) for p in out["alpha"]["picks"]] == [("NYJ", 440), ("MIA", -200)]
    # the line moves after the lock: the board row shows -215, the locked Alpha entry stays -200
    gld = json.loads((tmp_path / "game_lines_desk.json").read_text())
    gld["sports"]["nba"]["board"][0]["lean"]["book_american"] = -215
    gld["sports"]["nba"]["board"][0]["ml_home"] = -215
    (tmp_path / "game_lines_desk.json").write_text(json.dumps(gld))
    out = board.run(now=now + dt.timedelta(hours=2, minutes=30))
    out.pop("generated_at")
    (tmp_path / "board.json").write_text(json.dumps(out))
    monkeypatch.setattr(t, "DATA_DIR", str(tmp_path))
    rows = t._collect_picks_from_sources()
    pick = next(r for r in rows if r["source"] == "board_pick" and r["player_or_matchup"] == "BOS @ MIA")
    alpha = next(r for r in rows if r["source"] == "board_alpha" and r["player_or_matchup"] == "BOS @ MIA")
    assert pick["board_price"] == -215 and alpha["alpha_price"] == -200 and alpha["book_american"] == -200
    # before the lock (provisional) nothing is tagged Alpha
    (tmp_path / "board.json").write_text(json.dumps(dict(out, alpha=dict(out["alpha"], status="provisional"))))
    assert not [r for r in t._collect_picks_from_sources() if r["source"] == "board_alpha"]


def test_alpha_post_is_offered_only_for_a_locked_list_and_names_each_grade(tmp_path, monkeypatch):
    import re
    board, now = _board_fixture(tmp_path, monkeypatch)
    out = board.run(now=now)                                            # 10:00 ET: provisional
    assert out["alpha"]["status"] == "provisional" and out["alpha"]["post"] is None
    out = board.run(now=now + dt.timedelta(hours=2))                    # locked
    post = out["alpha"]["post"]
    assert post["fits"] and post["chars"] == len(post["text"]) <= 280 and post["n_picks"] == 2
    assert "1. NFL NYJ ML +440 (forward test)" in post["text"] and "2. NBA MIA ML -200 (lean)" in post["text"]
    assert "A lean is not a proven edge." in post["text"] and "not betting advice" in post["text"]
    assert sorted(re.findall(r"(?<![\w/.])[+-]\d{3,}\b", post["text"])) == ["+440", "-200"]
    # five long picks: the lowest-ranked is dropped before any caveat is
    a = dict(out["alpha"], picks=[dict(out["alpha"]["picks"][0], rank=i + 1, team="T" * 30) for i in range(5)])
    p = board.alpha_post(a, "2026-11-08", None)
    assert p["fits"] and p["n_picks"] < 5 and "not betting advice" in p["text"]


def test_play_of_day_ranks_edges_by_risk_adjusted_ev_not_raw_ev():
    import play_of_day as pod
    dog = {"sport": "NFL", "tier": 2, "model_prob": 0.217, "book_american": 440, "ev_pct": 17.2}
    fav = {"sport": "NFL", "tier": 2, "model_prob": 0.889, "book_american": -440, "ev_pct": 9.2}
    assert sorted([dog, fav], key=pod._rank_key)[0] is fav               # ~3x better per unit of risk
    # tier still comes first, and a lean is never ranked on reward
    lean = {"sport": "NBA", "tier": 4, "model_prob": 0.7, "book_american": -240, "ev_pct": -3.9, "lean_score": 0.69}
    assert sorted([lean, dog], key=pod._rank_key)[0] is dog
    # no probability: falls back to raw EV, never crashes
    a = {"sport": "NFL", "tier": 2, "model_prob": None, "book_american": 150, "ev_pct": 6.0}
    b = {"sport": "NFL", "tier": 2, "model_prob": None, "book_american": 150, "ev_pct": 4.0}
    assert sorted([b, a], key=pod._rank_key)[0] is a
    assert pod.risk_adj(0.5, None) is None and abs(pod.risk_adj(0.889, -440) - 0.2362) < 1e-3


def test_board_results_carry_closing_line_value_only_after_the_start(tmp_path, monkeypatch):
    import all_picks_tracker as t
    started = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%MZ")
    later = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=5)).strftime("%Y-%m-%dT%H:%MZ")
    (tmp_path / "dk_lines_nba.json").write_text(json.dumps({"events": {
        "1": {"commence": started, "close": {"ml_home": -250, "ml_away": 205}},     # we took -200: beat the close
        "2": {"commence": later, "close": {"ml_home": -150, "ml_away": 130}}}}))    # not started: no CLV yet
    for sp in ("nfl", "nhl"):
        (tmp_path / f"dk_lines_{sp}.json").write_text(json.dumps({"events": {}}))
    monkeypatch.setattr(t, "DATA_DIR", str(tmp_path))
    h = [{"source": "board_pick", "also_sources": ["board_alpha"], "sport": "NBA", "player_or_matchup": "BOS @ MIA",
          "market": "ML_HOME", "event_id": "1", "book_american": -200, "board_price": -200, "alpha_price": -190,
          "date": "2026-11-13", "settled": True, "result": "won", "payout_units": 0.5},
         {"source": "board_pick", "sport": "NBA", "player_or_matchup": "A @ B", "market": "ML_AWAY", "event_id": "2",
          "book_american": 130, "board_price": 130, "date": "2026-11-13", "settled": False}]
    b = t._board_block(h)
    assert b["all_bets"]["n_clv"] == 1 and b["all_bets"]["beat_close_pct"] == 100.0
    assert abs(b["all_bets"]["avg_clv_pts"] - round((250 / 350 - 200 / 300) * 100, 2)) < 1e-9       # +4.76 pts
    assert b["alpha"]["avg_clv_pts"] > b["all_bets"]["avg_clv_pts"]                                  # the locked -190 is better still
    assert b["all_bets"]["avg_clv_ev_pct"] > 0
    r = {x["matchup"]: x for x in b["recent"]}
    assert r["BOS @ MIA"]["close_price"] == -250 and r["A @ B"]["clv_pts"] is None


def test_board_hold_and_line_move():
    import board
    assert board.hold_pct(-110, -110) == 4.76 and board.hold_pct(None, -110) is None
    assert abs(board.hold_pct(-200, 170) - (200 / 300 + 100 / 270 - 1) * 100) < 0.01
    mv = board.line_move({"ml_home": -150, "ml_away": 130, "at": "2026-11-13T07:00:00"}, -200, 170)
    assert mv["open_ml_home"] == -150 and mv["move_home_pts"] > 5          # money came in on the home side
    assert board.line_move({}, -200, 170) is None and board.line_move({"ml_home": None, "ml_away": 130}, -200, 170) is None


def test_recap_post_is_the_last_fully_graded_alpha_day_losses_included():
    import board
    R = {"first_date": "2026-11-12",
         "alpha": {"n_settled": 5, "wins": 4, "losses": 1, "net_units": 1.119},
         "by_day": {"2026-11-12": {"alpha": {"wins": 4, "losses": 1, "net_units": 1.119}},
                    "2026-11-13": {"alpha": {"wins": 0, "losses": 0, "net_units": 0}}},
         "recent": [{"date": "2026-11-13", "sport": "NBA", "team": "OKC", "book_american": -283, "grade": "C", "is_alpha": True, "result": "pending"},
                    {"date": "2026-11-12", "sport": "NBA", "team": "PHX", "book_american": -229, "grade": "C", "is_alpha": True, "result": "won", "final": "CHA 96 @ PHX 101"},
                    {"date": "2026-11-12", "sport": "NHL", "team": "BUF", "book_american": -155, "grade": "C", "is_alpha": True, "result": "lost", "final": "BUF 2 @ CHI 3"},
                    {"date": "2026-11-12", "sport": "NHL", "team": "DAL", "book_american": -175, "grade": "C", "is_alpha": False, "result": "lost"}]}
    p = board.recap_post(R, "2026-11-14")            # 11/13 is not fully graded: the recap is 11/12
    assert p["day"] == "2026-11-12" and p["fits"]
    assert "4-1, +1.12u" in p["text"] and "L NHL BUF ML -155 (BUF 2 @ CHI 3)" in p["text"]      # the loss is in it
    assert "DAL" not in p["text"]                                                             # not an Alpha pick
    assert "All were leans, not proven edges." in p["text"] and "not betting advice" in p["text"]
    assert board.recap_post(None, "2026-11-14") is None and board.recap_post({"recent": []}, "2026-11-14") is None




def test_recap_never_drops_a_pick_to_fit():
    import board
    picks = [{"date": "2026-11-12", "sport": "NHL", "team": f"TEAM{i}", "book_american": -155, "grade": "C", "is_alpha": True,
              "result": "lost" if i == 4 else "won", "final": "LONGAWAYNAME 100 @ LONGHOMENAME 101"} for i in range(5)]
    R = {"first_date": "2026-11-12", "alpha": {"n_settled": 5, "wins": 4, "losses": 1, "net_units": 1.1},
         "by_day": {"2026-11-12": {"alpha": {"wins": 4, "losses": 1, "net_units": 1.1}}}, "recent": picks}
    p = board.recap_post(R, "2026-11-13")
    assert p["fits"]
    assert all(f"TEAM{i}" in p["text"] for i in range(5)) and "L TEAM4 -155" in p["text"]       # the loss is never cut


def test_espn_odds_keeps_spread_prices():
    import espn_odds as eo
    ev = {"id": "401873053", "date": "2026-11-15T18:00Z", "competitions": [{
        "competitors": [{"homeAway": "home", "team": {"abbreviation": "DET"}}, {"homeAway": "away", "team": {"abbreviation": "NE"}}],
        "status": {"type": {"state": "pre"}},
        "odds": [{"provider": {"name": "Draft Kings"}, "spread": -3.0, "overUnder": 49.5,
                  "moneyline": {"home": {"close": {"odds": "-155"}}, "away": {"close": {"odds": "+130"}}},
                  "total": {"over": {"close": {"odds": "-112"}}, "under": {"close": {"odds": "-108"}}},
                  "pointSpread": {"home": {"close": {"line": "-3", "odds": "-102"}}, "away": {"close": {"line": "+3", "odds": "-118"}}}}]}]}
    orig = eo._get
    eo._get = lambda u: {"events": [ev]}
    try:
        rows = eo.fetch_sport("nfl")
    finally:
        eo._get = orig
    m = rows[0]["market"]
    assert (m["spread_home_line"], m["spread_home_price"], m["spread_away_line"], m["spread_away_price"]) == (-3.0, -102, 3.0, -118)
    assert m["ml_home"] == -155 and m["spread"] == -3.0


def test_board_shows_the_desks_open_picks_against_the_current_line(tmp_path, monkeypatch):
    board, now = _board_fixture(tmp_path, monkeypatch)
    gld = json.loads((tmp_path / "game_lines_desk.json").read_text())
    gld["sports"]["nfl"]["forward_test"] = {"picks": [
        {"matchup": "DAL @ IND", "market": "ML_HOME", "logged_price": 220, "close_price": 195, "close_final": False, "clv_pts": 3.32},
        {"matchup": "NYJ @ KC", "market": "ML_AWAY", "logged_price": 440, "close_price": 440, "close_final": True, "clv_pts": 0.0}]}
    (tmp_path / "game_lines_desk.json").write_text(json.dumps(gld))
    out = board.run(now=now)
    g = {x["matchup"]: x for x in out["games"]}
    assert g["DAL @ IND"]["desk_logged"] == [{"market": "ML_HOME", "logged_price": 220, "now_price": 195, "clv_pts": 3.32, "team": "IND"}]
    assert g["NYJ @ KC"]["desk_logged"] == []          # a closed (final) pick is graded elsewhere, not shown as open



def test_desk_clv_headline_counts_played_games_only(tmp_path, monkeypatch):
    import game_lines_desk as gld
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).strftime("%Y-%m-%dT%H:%MZ")
    future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).strftime("%Y-%m-%dT%H:%MZ")
    (tmp_path / "all_picks_ledger.json").write_text(json.dumps({"picks": [
        {"source": "nfl_game_ml", "event_id": "1", "market": "ML_HOME", "book_american": -150, "settled": True, "result": "lost"},
        {"source": "nfl_game_ml", "event_id": "2", "market": "ML_HOME", "book_american": 110, "settled": False}]}))
    monkeypatch.setattr(gld, "DATA_DIR", str(tmp_path))
    lines = {"1": {"commence": past, "close": {"ml_home": -150, "ml_away": 130}},        # played: flat to the close
             "2": {"commence": future, "close": {"ml_home": -155, "ml_away": 130}}}     # open: market moved our way
    f = gld.forward_test("nfl", lines)
    assert f["n_clv"] == 1 and f["avg_clv_pts"] == 0.0                                 # the open pick does not inflate it
    assert f["open"]["n"] == 1 and f["open"]["avg_pts_vs_current"] > 10 and f["open"]["ahead"] == 1


def test_review_1113_alpha_grade_spread_pairing_and_event_keyed_desk_picks(tmp_path, monkeypatch):
    import all_picks_tracker as t
    import espn_odds as eo
    import board
    # 1. a B desk pick locked as a C-lean Alpha pick: the Alpha record says C, the board-bet record keeps B
    for sp in ("nfl", "nba", "nhl"):
        (tmp_path / f"dk_lines_{sp}.json").write_text(json.dumps({"events": {}}))
    monkeypatch.setattr(t, "DATA_DIR", str(tmp_path))
    h = [{"source": "nfl_game_ml", "also_sources": ["board_pick", "board_alpha"], "desk_verdict": "unproven", "sport": "NFL",
          "player_or_matchup": "NE @ DET", "market": "ML_HOME", "book_american": 110, "board_price": 110, "board_grade": "B",
          "alpha_price": -155, "alpha_grade": "C", "alpha_score": 43, "date": "2026-11-15", "settled": True, "result": "won", "payout_units": 1.1}]
    b = t._board_block(h)
    assert b["recent"][0]["grade"] == "C" and b["recent"][0]["book_american"] == -155 and b["by_grade"]["B"]["wins"] == 1
    assert "when its edge first appeared" in b["definition"]
    # 2. spread line + price from one snapshot; a 0 line survives
    ev = {"id": "9", "date": "2026-11-15T18:00Z", "competitions": [{
        "competitors": [{"homeAway": "home", "team": {"abbreviation": "DET"}}, {"homeAway": "away", "team": {"abbreviation": "NE"}}],
        "status": {"type": {"state": "pre"}},
        "odds": [{"provider": {"name": "Draft Kings"}, "moneyline": {"home": {"close": {"odds": "-155"}}, "away": {"close": {"odds": "+130"}}},
                  "pointSpread": {"home": {"close": {"line": "-3"}, "open": {"line": "-2.5", "odds": "-110"}},
                                  "away": {"close": {"line": "0", "odds": "-105"}}}}]}]}
    orig = eo._get
    eo._get = lambda u: {"events": [ev]}
    try:
        m = eo.fetch_sport("nfl")[0]["market"]
    finally:
        eo._get = orig
    assert (m["spread_home_line"], m["spread_home_price"]) == (-2.5, -110)          # not "-3 (-110)"
    assert (m["spread_away_line"], m["spread_away_price"]) == (0.0, -105)            # pick'em kept
    # 4. two games with the same pairing: each card shows only its own desk pick
    bd, now = _board_fixture(tmp_path, monkeypatch)
    gld = json.loads((tmp_path / "game_lines_desk.json").read_text())
    gld["sports"]["nfl"]["forward_test"] = {"picks": [
        {"matchup": "DAL @ IND", "event_id": "elsewhere", "market": "ML_HOME", "logged_price": 220, "close_price": 195, "close_final": False, "clv_pts": 3.3}]}
    (tmp_path / "game_lines_desk.json").write_text(json.dumps(gld))
    out = bd.run(now=now)
    assert next(x for x in out["games"] if x["matchup"] == "DAL @ IND")["desk_logged"] == []


def test_board_lineup_flags_backup_goalies_non_regular_qbs_and_big_absences():
    import board
    g = board.lineup({"goalies": {"away": {"projected": "D. Garand", "status": "confirmed", "primary": "I. Shesterkin", "back_to_back": False},
                                  "home": {"projected": "T. Demko", "status": "expected", "primary": "T. Demko", "back_to_back": True}}})
    assert g["kind"] == "goalies" and g["away"]["flag"] and "BACKUP" in g["away"]["text"] and "(confirmed)" in g["away"]["text"]
    assert not g["home"]["flag"] and "B2B" in g["home"]["text"]
    # the store spells a name with an accent, ESPN without: the same goalie is not a backup
    g = board.lineup({"goalies": {"home": {"projected": "L. Merilainen", "status": "expected", "primary": "L. Meril\u00e4inen"}}})
    assert g["home"]["flag"] is False
    q = board.lineup({"qbs": {"home": {"qb": "J.J. McCarthy", "regular": "Jameis Winston", "status": "active", "certain": False},
                              "away": {"qb": "Jayden Daniels", "regular": "Jayden Daniels", "status": "active", "certain": True}}})
    assert q["home"]["flag"] and "not the regular (Jameis Winston)" in q["home"]["text"] and "uncertain" in q["home"]["text"]
    assert not q["away"]["flag"]
    a = board.lineup({"avail": {"home": {"abnormal": 4.2, "listed": [{"name": "Star", "status": "Out", "value": 7.3},
                                                                     {"name": "Bench", "status": "Out", "value": 0.4}]},
                                "away": {"abnormal": 0, "listed": []}}})
    assert a["home"]["text"] == "Injury list: Star" and a["home"]["flag"] and a["away"]["text"] == "no rotation player listed"
    assert board.lineup({}) is None

