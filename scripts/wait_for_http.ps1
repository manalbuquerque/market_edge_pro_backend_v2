param(
  [Parameter(Mandatory=$true)][string]$Url,
  [int]$Tries = 60
)
for ($i=1; $i -le $Tries; $i++) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
    if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 400) { Write-Output "OK $Url"; exit 0 }
  } catch { }
  Start-Sleep -Seconds 1
}
Write-Error "Timeout waiting for $Url"; exit 1
