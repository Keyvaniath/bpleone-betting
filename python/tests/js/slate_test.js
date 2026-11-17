// (2026-11-16) node test for js/slate.js bet matching: run by python/tests/test_odds_integrity.py
const assert = require("assert");
global.window = {};
global.document = { hidden: false };
require("../../../js/slate.js");
const { betsFor, same } = window.EdgeSlate;

const board = {
  date_et: "2026-11-16",
  alpha: { status: "locked", picks: [
    { sport: "NBA", matchup: "POR @ MIN", team: "MIN", book_american: -135, grade: "C", rank: 4, game_date: "2026-11-16" }] },
  picks: [{ sport: "NHL", matchup: "LA @ BOS", team: "BOS", book_american: -148, grade: "C", game_date: "2026-11-17" }],
  results: { recent: [
    { date: "2026-11-16", sport: "NBA", matchup: "POR @ MIN", team: "MIN", book_american: -135, grade: "C", is_alpha: true, result: "won", final: "x" },
    { date: "2026-11-16", sport: "NFL", matchup: "LAC @ BAL", team: "LAC", book_american: 185, grade: "B", result: "pending" }] },
};

// today: Alpha list + the ledger rows, merged (MIN once, carrying the ledger result)
const d16 = betsFor(board, "2026-11-16");
assert.deepStrictEqual(d16.map((b) => `${b.team}:${b.result}:${b.alpha}`).sort(), ["LAC:pending:null", "MIN:won:4"]);
assert.ok(d16.every((b) => b.day === "2026-11-16"));

// tomorrow: the board's 11/16 Alpha list must NOT appear; only tomorrow's board pick
const d17 = betsFor(board, "2026-11-17");
assert.deepStrictEqual(d17.map((b) => b.team), ["BOS"]);

// a board dated tomorrow (after the first post-midnight run) keeps yesterday's bets via the ledger only
const d16b = betsFor(Object.assign({}, board, { date_et: "2026-11-17" }), "2026-11-16");
assert.deepStrictEqual(d16b.map((b) => b.team).sort(), ["LAC", "MIN"]);

// same(): back-to-back pairings never cross dates
const g17 = { sport: "NBA", matchup: "POR @ MIN", day: "2026-11-17" }, g16 = Object.assign({}, g17, { day: "2026-11-16" });
const minBet = d16.find((b) => b.team === "MIN");
assert.strictEqual(same(minBet, g16), true);
assert.strictEqual(same(minBet, g17), false);
assert.strictEqual(same(minBet, Object.assign({}, g16, { sport: "NHL" })), false);
console.log("slate ok");
