CREATE TABLE IF NOT EXISTS ohlcv (
  tenant_id  TEXT NOT NULL,
  market     TEXT NOT NULL,
  symbol     TEXT NOT NULL,
  timeframe  TEXT NOT NULL,
  ts         BIGINT NOT NULL,
  open       DOUBLE PRECISION NOT NULL,
  high       DOUBLE PRECISION NOT NULL,
  low        DOUBLE PRECISION NOT NULL,
  close      DOUBLE PRECISION NOT NULL,
  volume     DOUBLE PRECISION NOT NULL,
  PRIMARY KEY(tenant_id,market,symbol,timeframe,ts)
);
DO $$
DECLARE i int;
BEGIN
  FOR i IN 0..19 LOOP
    INSERT INTO ohlcv
    (tenant_id,market,symbol,timeframe,ts,open,high,low,close,volume)
    VALUES ('t1','crypto','BTCUSDT','1m',
      EXTRACT(EPOCH FROM NOW())::bigint - (60 * (19 - i)),
      50000+i, 50010+i, 49990+i, 50005+i, 10+i)
    ON CONFLICT DO NOTHING;
  END LOOP;
END $$;
