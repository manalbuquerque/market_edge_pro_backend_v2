param(
  [string]$Port = "8010",
  [string]$ApiKeys = "secret123,anotherKey"
)
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = (Get-Location).Path
$env:DATABASE_URL = "postgresql+psycopg2://user:pass@127.0.0.1:5432/market_edge"
$env:APIKEY_ENABLED = "1"
$env:APIKEYS = $ApiKeys
$env:OBS_ENABLED = "1"

python -m uvicorn main1:app --port $Port --log-level info
