-- EdgeStat D1 schema v2 -- multi-year foundation
-- Apply with: wrangler d1 execute edgestat-history --file=schema_v2.sql --remote

-- Add model_version column to picks (NULL allowed for legacy picks).
ALTER TABLE picks ADD COLUMN model_version TEXT;
CREATE INDEX IF NOT EXISTS idx_picks_model_version ON picks(model_version);

-- Source lifecycle: when each source was first seen, when it crossed n=20,
-- when it became A/B grade.
CREATE TABLE IF NOT EXISTS source_lifecycle (
  source           TEXT PRIMARY KEY,
  first_pick_at    TEXT,
  picks_total      INTEGER DEFAULT 0,
  settled_total    INTEGER DEFAULT 0,
  crossed_n20_at   TEXT,
  first_b_grade_at TEXT,
  first_a_grade_at TEXT,
  current_grade    TEXT,
  last_update_at   TEXT
);

-- Weight change audit log: every shift in self_learn_weights.json with reason.
CREATE TABLE IF NOT EXISTS weight_audit (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  source        TEXT NOT NULL,
  old_weight    REAL,
  new_weight    REAL,
  delta         REAL,
  reason        TEXT,        -- learned / user_override / gated_no_data / etc.
  n_settled     INTEGER,
  hit_rate      REAL,
  model_version TEXT,
  changed_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_source ON weight_audit(source);
CREATE INDEX IF NOT EXISTS idx_audit_changed_at ON weight_audit(changed_at);

-- Monthly snapshots metadata (R2 holds the actual data)
CREATE TABLE IF NOT EXISTS monthly_snapshots (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  month            TEXT NOT NULL UNIQUE,   -- YYYY-MM
  r2_key           TEXT NOT NULL,
  n_picks_snapshot INTEGER,
  n_settled        INTEGER,
  hit_rate         REAL,
  total_units      REAL,
  snapshot_at      TEXT NOT NULL
);
