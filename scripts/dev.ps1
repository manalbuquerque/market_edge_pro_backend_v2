param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
Import-Module -Force "$PSScriptRoot\dev.psm1"
if (!$Args) { Get-Command -Module dev | Select Name | Out-Host; exit 0 }
$cmd=$Args[0]; $rest=$Args[1..($Args.Length-1)]
& $cmd @rest
