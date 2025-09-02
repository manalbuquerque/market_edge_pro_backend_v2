Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Up { docker compose up -d }
function Down { docker compose down -v }
function Rebuild {
  docker compose down -v
  docker compose build --no-cache app
  docker compose up -d
}
function Logs { param([int]$Tail=200) docker logs mep-app --tail=$Tail -f }
function Health {
  param([string]$Base="http://127.0.0.1:8010")
  Invoke-WebRequest -UseBasicParsing "$Base/health" | Out-Host
  (Invoke-WebRequest -UseBasicParsing "$Base/metrics").Content |
    Select-String -Pattern "process_max_fds" | Out-Host
}
function Seed {
  Get-Content -Raw "seeds/ohlcv_seed.sql" | docker exec -i mep-db psql -U postgres -d market_edge -f -
}
function Psql { docker exec -it mep-db psql -U postgres -d market_edge }
function Test {
  param([string]$Base="http://127.0.0.1:8010",[string]$Good="secret123")
  $env:BASE=$Base; $env:BASE_URL=$Base; $env:GOOD=$Good
  python -m pytest -q -k "smoke_endpoints or http" -s
}
Export-ModuleMember -Function Up,Down,Rebuild,Logs,Health,Seed,Psql,Test
