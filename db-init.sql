CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS signals (
  tenant_id  TEXT   NOT NULL,
  market     TEXT   NOT NULL,
  symbol     TEXT   NOT NULL,
  timeframe  TEXT   NOT NULL,
  ts         BIGINT NOT NULL,
  payload    JSONB  NOT NULL,
  PRIMARY KEY (tenant_id, market, symbol, timeframe, ts)
);
SELECT create_hypertable('signals','ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_signals_lookup
  ON signals (tenant_id, market, symbol, timeframe, ts DESC);

CREATE TABLE IF NOT EXISTS ohlcv (
  tenant_id  TEXT   NOT NULL,
  market     TEXT   NOT NULL,
  symbol     TEXT   NOT NULL,
  timeframe  TEXT   NOT NULL,
  ts         BIGINT NOT NULL,
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