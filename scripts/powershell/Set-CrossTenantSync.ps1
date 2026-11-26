<#
.SYNOPSIS
  Configure the TARGET tenant to trust and receive identities from the SOURCE tenant (cross-tenant access + cross-tenant synchronization).
.DESCRIPTION
  Run while signed in to the TARGET tenant as a Security Administrator or Global Administrator.
  Supports -WhatIf. Uses Graph REST endpoints through Invoke-MgGraphRequest so it does not depend on beta SDK cmdlets.
  Creates/updates: partner configuration, inbound trust (MFA + compliant device + hybrid join), automatic redemption, inbound sync permission.
  You still create the sync *configuration* (job + attribute mapping + scoping group) in the source tenant: see docs/runbook.md section 4.
.EXAMPLE
  .\Set-CrossTenantSync.ps1 -SourceTenantId 00000000-0000-0000-0000-000000000000 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess, ConfirmImpact='High')]
param(
  [Parameter(Mandatory)][guid]$SourceTenantId,
  [switch]$TrustMfa = $true,
  [switch]$TrustCompliantDevice = $true,
  [switch]$TrustHybridJoinedDevice = $true
)
$ErrorActionPreference = 'Stop'
Connect-MgGraph -Scopes 'Policy.ReadWrite.CrossTenantAccess' -NoWelcome
$base = 'https://graph.microsoft.com/v1.0/policies/crossTenantAccessPolicy/partners'
$tid = $SourceTenantId.ToString()

$exists = $true
try { Invoke-MgGraphRequest -Method GET -Uri "$base/$tid" | Out-Null } catch { $exists = $false }

if (-not $exists) {
  if ($PSCmdlet.ShouldProcess($tid, 'Create cross-tenant access partner configuration')) {
    Invoke-MgGraphRequest -Method POST -Uri $base -Body (@{ tenantId = $tid } | ConvertTo-Json) -ContentType 'application/json' | Out-Null
    Write-Host "Created partner configuration for $tid" -ForegroundColor Green
  }
}

$policy = @{
  inboundTrust = @{
    isMfaAccepted = [bool]$TrustMfa
    isCompliantDeviceAccepted = [bool]$TrustCompliantDevice
    isHybridAzureADJoinedDeviceAccepted = [bool]$TrustHybridJoinedDevice
  }
  automaticUserConsentSettings = @{ inboundAllowed = $true; outboundAllowed = $false }
}
if ($PSCmdlet.ShouldProcess($tid, 'Set inbound trust and automatic redemption')) {
  Invoke-MgGraphRequest -Method PATCH -Uri "$base/$tid" -Body ($policy | ConvertTo-Json -Depth 5) -ContentType 'application/json' | Out-Null
  Write-Host 'Inbound trust + automatic redemption set' -ForegroundColor Green
}
if ($PSCmdlet.ShouldProcess($tid, 'Allow inbound cross-tenant synchronization')) {
  $sync = @{ userSyncInbound = @{ isSyncAllowed = $true } }
  try { Invoke-MgGraphRequest -Method PUT -Uri "$base/$tid/identitySynchronization" -Body ($sync | ConvertTo-Json -Depth 4) -ContentType 'application/json' | Out-Null }
  catch { Invoke-MgGraphRequest -Method PATCH -Uri "$base/$tid/identitySynchronization" -Body ($sync | ConvertTo-Json -Depth 4) -ContentType 'application/json' | Out-Null }
  Write-Host 'Inbound user synchronization allowed' -ForegroundColor Green
}
Write-Host "`nVerify in the portal: Entra ID > External Identities > Cross-tenant access settings > Organizational settings." -ForegroundColor Yellow
