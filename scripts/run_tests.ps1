$env:BASE="http://127.0.0.1:8010"
$env:BASE_URL=$env:BASE
$env:GOOD="secret123"
python -m pytest -q -k "smoke_endpoints or http" -s
