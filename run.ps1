# One-command demo on Windows PowerShell:  .\run.ps1
$ErrorActionPreference = 'Stop'
$py = if (Get-Command py -ErrorAction SilentlyContinue) { 'py -3' } else { 'python' }
Invoke-Expression "$py -m pip install --quiet matplotlib numpy"
Invoke-Expression "$py tools/generate_sample_data.py"
$env:PYTHONPATH = "src"
Invoke-Expression "$py -m tcp --source data/sample/source-tenant.json --target data/sample/target-tenant.json --out reports"
Write-Host "`nOpen reports\executive-summary.md and reports\diagrams\*.png" -ForegroundColor Green
