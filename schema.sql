-- Extensions
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()

-- signals
CREATE TABLE IF NOT EXISTS signals (
  tenant_id  TEXT NOT NULL,
  market     TEXT NOT NULL,
  symbol     TEXT NOT NULL,
  timeframe  TEXT NOT NULL,
  ts         BIGINT NOT NULL,        -- ms since epoch
  payload    JSONB  NOT NULL,        -- e.g. {"signal":1}
  id         UUID   NOT NULL DEFAULT gen_random_uuid(),
  PRIMARY KEY (tenant_id, market, symbol, timeframe, ts)
);
SELECT create_hypertable('signals','ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_signals_lookup
  ON signals (tenant_id, market, symbol, timeframe, ts DESC);

-- ohlcv
CREATE TABLE IF NOT EXISTS ohlcv (
  tenant_id  TEXT NOT NULL,
  market     TEXT NOT NULL,
  symbol     TEXT NOT NULL,
  timeframe  TEXT NOT NULL,
  ts         BIGINT NOT NULL,        -- ms since epoch
  open       DOUBLE PRECISION NOT NULL,
  high       DOUBLE PRECISION NOT NULL,
  low        DOUBLE PRECISION NOT NULL,
  close      DOUBLE PRECISION NOT NULL,
  volume     DOUBLE PRECISION NOT NULL,
  PRIMARY KEY (tenant_id, market, symbol, timeframe, ts)
);
SELECT create_hypertable('ohlcv','ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ohlcv_lookup
  ON ohlcv (tenant_id, market, symbol, timeframe, ts DESC);
