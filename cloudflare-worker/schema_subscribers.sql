-- EdgeStat subscribers (premium entitlements). Apply with:
--   wrangler d1 execute edgestat --file=schema_subscribers.sql --remote
-- Entitlement is keyed by email (the verified Supabase identity == the Stripe
-- customer email). The worker /billing/* routes read/write this table.

CREATE TABLE IF NOT EXISTS subscribers (
  email                TEXT PRIMARY KEY,
  stripe_customer      TEXT,
  stripe_subscription  TEXT,
  status               TEXT NOT NULL DEFAULT 'inactive',  -- active | trialing | canceled | inactive
  current_period_end   INTEGER,                            -- unix seconds
  created_at           TEXT,
  updated_at           TEXT
);

-- Look up an entitlement by the Stripe customer id (subscription.* webhooks
-- carry the customer, not the email).
CREATE INDEX IF NOT EXISTS idx_subscribers_customer ON subscribers (stripe_customer);
