INSERT INTO signals (tenant_id,market,symbol,timeframe,ts,payload) VALUES
('default','CRYPTO','BTCUSDT','1m',1700000000000,'{"signal":1}'),
('default','CRYPTO','BTCUSDT','1m',1700000060000,'{"signal":0}')
ON CONFLICT DO NOTHING;

INSERT INTO ohlcv (tenant_id,market,symbol,timeframe,ts,open,high,low,close,volume) VALUES
('default','CRYPTO','BTCUSDT','1m',1700000000000,100,110,95,105,1234),
('default','CRYPTO','BTCUSDT','1m',1700000060000,105,112,101,108,987)
ON CONFLICT DO NOTHING;