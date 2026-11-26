<#
.SYNOPSIS
  Go / no-go gate. Fails (exit code 1) while critical findings remain unresolved. Use in CI or before each wave.
.EXAMPLE
  .\Test-Preflight.ps1 -Findings ..\..\reports\findings.json -Waivers ..\..\config\waivers.json
#>
param(
  [string]$Findings = "$PSScriptRoot\..\..\reports\findings.json",
  [string]$Waivers  = "$PSScriptRoot\..\..\config\waivers.json"
)
$f = Get-Content $Findings -Raw | ConvertFrom-Json
$w = if (Test-Path $Waivers) { (Get-Content $Waivers -Raw | ConvertFrom-Json).waivers } else { @() }
$open = @($f | Where-Object { $_.severity -eq 'critical' } | Where-Object {
  $k = "$($_.id)|$($_.subject)"; -not ($w | Where-Object { $_.key -eq $k -and [datetime]$_.expires -gt (Get-Date) }) })
$f | Group-Object severity | Sort-Object Name | ForEach-Object { Write-Host ("{0,-9} {1}" -f $_.Name, $_.Count) }
if ($open.Count) {
  Write-Host "`nNO-GO: $($open.Count) critical finding(s) without an unexpired waiver:" -ForegroundColor Red
  $open | ForEach-Object { Write-Host "  [$($_.id)] $($_.subject)" -ForegroundColor Red }
  exit 1
}
Write-Host "`nGO: no unresolved critical findings." -ForegroundColor Green
exit 0
