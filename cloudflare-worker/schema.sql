-- EdgeStat D1 schema -- Cloudflare Pro plan
-- Apply with: wrangler d1 execute edgestat-history --file=schema.sql --remote

-- =========================================================================
-- PICKS: every pick ever surfaced by any module
-- =========================================================================
CREATE TABLE IF NOT EXISTS picks (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  pick_id         TEXT NOT NULL UNIQUE,           -- source|sport|player|market|date
  source          TEXT NOT NULL,                  -- mlb_f5, pod, rlm_strong, etc.
  sport           TEXT NOT NULL,                  -- MLB, NHL, NBA, F1, GOLF
  player_or_matchup TEXT,
  market          TEXT,                           -- "OVER 4.0", "1_plus_hit", "HOME ML"
  p_predicted     REAL,                           -- model probability at pick time (for Brier)
  entry_odds      INTEGER,                        -- American odds at pick time
  closing_odds    INTEGER,                        -- filled at game start
  fair_odds       INTEGER,                        -- model's fair-price odds
  edge_pct        REAL,                           -- model_p vs market_p
  tier            TEXT,                           -- STRONG / STANDARD / NONE / ELITE
  outcome         TEXT DEFAULT 'PENDING',         -- WIN / LOSS / PUSH / PENDING / VOID
  payout_units    REAL,                           -- +X.XX (win) / -1.00 (loss) / 0 (push)
  date            TEXT NOT NULL,                  -- YYYY-MM-DD game date
  created_at      TEXT NOT NULL,                  -- ISO timestamp when pick was logged
  settled_at      TEXT,                           -- ISO timestamp when outcome recorded
  metadata        TEXT                            -- JSON blob for source-specific extras
);

CREATE INDEX IF NOT EXISTS idx_picks_source  ON picks(source);
CREATE INDEX IF NOT EXISTS idx_picks_date    ON picks(date);
CREATE INDEX IF NOT EXISTS idx_picks_outcome ON picks(outcome);
CREATE INDEX IF NOT EXISTS idx_picks_sport   ON picks(sport);

-- =========================================================================
-- LINE_SNAPSHOTS: time-series of book odds per game (for CLV)
-- =========================================================================
CREATE TABLE IF NOT EXISTS line_snapshots (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  matchup         TEXT NOT NULL,
  book            TEXT NOT NULL,                  -- bovada, draftkings, fanduel, etc.
  ts              TEXT NOT NULL,                  -- ISO timestamp
  home_ml         INTEGER,
  away_ml         INTEGER,
  total_line      REAL,
  total_over      INTEGER,
  total_under     INTEGER,
  home_rl         INTEGER,
  home_rl_pt      REAL,
  state           TEXT                            -- pre / live / final
);

CREATE INDEX IF NOT EXISTS idx_snaps_matchup ON line_snapshots(matchup);
CREATE INDEX IF NOT EXISTS idx_snaps_ts      ON line_snapshots(ts);

-- =========================================================================
-- BACKTEST_RUNS: persisted backtest results
-- =========================================================================
CREATE TABLE IF NOT EXISTS backtest_runs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  source_filter   TEXT,
  date_from       TEXT,
  date_to         TEXT,
  n_picks         INTEGER,
  n_settled       INTEGER,
  n_wins          INTEGER,
  hit_rate        REAL,
  net_units       REAL,
  roi_pct         REAL,
  avg_clv_pp      REAL,
  brier_score     REAL,
  run_at          TEXT NOT NULL
);
