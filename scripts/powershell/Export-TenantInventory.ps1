<#
.SYNOPSIS
  Read-only export of an Entra ID tenant into the JSON schema the analyzer consumes.
.DESCRIPTION
  Run once against the SOURCE tenant and once against the TARGET tenant.
  Uses Microsoft Graph PowerShell with READ-ONLY scopes. Nothing is changed in the tenant.
.EXAMPLE
  .\Export-TenantInventory.ps1 -Role source -OutFile ..\..\data\live\source-tenant.json -Tier1AppNames "Core Banking Gateway","SWIFT Alliance Access SSO"
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidateSet('source','target')][string]$Role,
  [Parameter(Mandatory)][string]$OutFile,
  [string[]]$Tier1AppNames = @(),
  [string[]]$Tier2AppNames = @(),
  [string]$TenantId
)
$ErrorActionPreference = 'Stop'
if (-not (Get-Module -ListAvailable Microsoft.Graph.Authentication)) {
  throw "Install the SDK first:  Install-Module Microsoft.Graph -Scope CurrentUser"
}
$scopes = 'User.Read.All','Group.Read.All','Application.Read.All','Directory.Read.All','Policy.Read.All',
          'RoleManagement.Read.Directory','Organization.Read.All','Device.Read.All','AuditLog.Read.All','Reports.Read.All'
if ($TenantId) { Connect-MgGraph -Scopes $scopes -TenantId $TenantId -NoWelcome } else { Connect-MgGraph -Scopes $scopes -NoWelcome }

function Write-Step($m){ Write-Host ("[{0}] {1}" -f (Get-Date -Format HH:mm:ss), $m) -ForegroundColor Cyan }

Write-Step 'Tenant and domains'
$org = Get-MgOrganization
$domains = Get-MgDomain -All | ForEach-Object {
  [ordered]@{ name=$_.Id; isVerified=$_.IsVerified; isDefault=$_.IsDefault; authenticationType=$_.AuthenticationType }
}

Write-Step 'Privileged role members'
$privByUser = @{}
foreach ($role in Get-MgDirectoryRole -All) {
  foreach ($m in Get-MgDirectoryRoleMember -DirectoryRoleId $role.Id -All) {
    if (-not $privByUser.ContainsKey($m.Id)) { $privByUser[$m.Id] = @() }
    $privByUser[$m.Id] += $role.DisplayName
  }
}

Write-Step 'MFA registration (Reports API)'
$mfa = @{}
Get-MgReportAuthenticationMethodUserRegistrationDetail -All | ForEach-Object { $mfa[$_.Id] = [bool]$_.IsMfaRegistered }

Write-Step 'Applications, service principals and assignments'
$sps = Get-MgServicePrincipal -All -Property Id,AppId,DisplayName,PreferredSingleSignOnMode,SignInAudience,KeyCredentials,Tags
$apps = @(); $assignByUser = @{}
foreach ($sp in $sps | Where-Object { $_.Tags -contains 'WindowsAzureActiveDirectoryIntegratedApp' }) {
  $tier = if ($Tier1AppNames -contains $sp.DisplayName) {'tier1'} elseif ($Tier2AppNames -contains $sp.DisplayName) {'tier2'} else {'tier3'}
  $reg = Get-MgApplication -Filter "appId eq '$($sp.AppId)'" -ErrorAction SilentlyContinue | Select-Object -First 1
  $perms = @()
  foreach ($g in Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $sp.Id -All -ErrorAction SilentlyContinue) { $perms += $g.AppRoleId }
  $cert = $sp.KeyCredentials | Where-Object { $_.Usage -eq 'Verify' } | Sort-Object EndDateTime | Select-Object -Last 1
  $assigned = @(Get-MgServicePrincipalAppRoleAssignedTo -ServicePrincipalId $sp.Id -All -ErrorAction SilentlyContinue)
  foreach ($a in $assigned) { if (-not $assignByUser.ContainsKey($a.PrincipalId)) { $assignByUser[$a.PrincipalId]=@() }; $assignByUser[$a.PrincipalId] += $sp.AppId }
  $apps += [ordered]@{
    appId=$sp.AppId; displayName=$sp.DisplayName
    protocol = if ($sp.PreferredSingleSignOnMode -eq 'saml') {'saml'} elseif ($reg -and $reg.Web.RedirectUris) {'oidc'} else {'api'}
    criticality=$tier; signInAudience = if ($reg) { $reg.SignInAudience } else { 'AzureADMyOrg' }
    usesTenantSpecificClaims=$false   # set manually after claims review
    appPermissions=@($perms); assignedDepartments=@()
    ssoCertExpiresInDays = if ($cert) { [int]($cert.EndDateTime - (Get-Date)).TotalDays } else { $null }
    redirectUris = if ($reg) { @($reg.Web.RedirectUris) } else { @() }
  }
}

Write-Step 'Devices'
$devs = Get-MgDevice -All -Property Id,TrustType,IsManaged,DisplayName
$ownerDev = @{}
foreach ($d in $devs) {
  foreach ($o in Get-MgDeviceRegisteredOwner -DeviceId $d.Id -ErrorAction SilentlyContinue) {
    if (-not $ownerDev.ContainsKey($o.Id)) { $ownerDev[$o.Id] = @{aad=0;hyb=0} }
    if ($d.TrustType -eq 'AzureAd') { $ownerDev[$o.Id].aad++ } elseif ($d.TrustType -eq 'ServerAd') { $ownerDev[$o.Id].hyb++ }
  }
}

Write-Step 'Users (this is the slow part on large tenants)'
$props = 'id','displayName','mailNickname','userPrincipalName','mail','proxyAddresses','employeeId','department','userType','accountEnabled','onPremisesSyncEnabled','assignedLicenses'
$skus = @{}; Get-MgSubscribedSku -All | ForEach-Object { $skus[$_.SkuId] = $_.SkuPartNumber }
$users = Get-MgUser -All -Property $props | ForEach-Object {
  [ordered]@{
    id=$_.Id; displayName=$_.DisplayName; mailNickname=$_.MailNickname; userPrincipalName=$_.UserPrincipalName; mail=$_.Mail
    proxyAddresses=@($_.ProxyAddresses); employeeId=$_.EmployeeId; department=$_.Department; userType=$_.UserType
    accountEnabled=$_.AccountEnabled; onPremisesSyncEnabled=[bool]$_.OnPremisesSyncEnabled
    licenses=@($_.AssignedLicenses | ForEach-Object { $skus[$_.SkuId] })
    mfaRegistered=[bool]$mfa[$_.Id]
    entraJoinedDevices= if ($ownerDev[$_.Id]) { $ownerDev[$_.Id].aad } else { 0 }
    hybridJoinedDevices= if ($ownerDev[$_.Id]) { $ownerDev[$_.Id].hyb } else { 0 }
    privilegedRoles=@($privByUser[$_.Id]); apps=@($assignByUser[$_.Id] | Select-Object -Unique)
  }
}

Write-Step 'Conditional Access'
$tier1Ids = $apps | Where-Object criticality -eq 'tier1' | ForEach-Object appId
$ca = Get-MgIdentityConditionalAccessPolicy -All | ForEach-Object {
  $c = $_.Conditions; $g = $_.GrantControls
  $usersScope = if ($c.Users.IncludeUsers -contains 'All') {'All'} elseif ($c.Users.IncludeRoles.Count) {'Admins'} elseif ($c.Users.IncludeGuestsOrExternalUsers) {'Guests'} else {'Selected'}
  $appScope   = if ($c.Applications.IncludeApplications -contains 'All') {'All'} elseif (@($c.Applications.IncludeApplications | Where-Object { $tier1Ids -contains $_ }).Count) {'tier1'} else {'Selected'}
  $grants = @(); if ($g) { $grants += $g.BuiltInControls | ForEach-Object { "$_" } ; if ($g.AuthenticationStrength) { $grants += "authStrength:$($g.AuthenticationStrength.DisplayName -replace '\s','')" } }
  [ordered]@{
    name=$_.DisplayName; state=$_.State; users=$usersScope; apps=$appScope
    grantControls=@($grants | ForEach-Object { switch ($_) { 'compliantDevice' {'compliantDevice'} default { $_ } } })
    requireCompliantDevice = ($grants -contains 'compliantDevice')
    blocksLegacyAuth = (@($c.ClientAppTypes) -contains 'exchangeActiveSync' -and $grants -contains 'block')
    signInRiskBlock = if ($c.SignInRiskLevels -contains 'high') {'high'} elseif ($c.UserRiskLevels -contains 'high') {'high'} else {$null}
    locationCondition = if ($c.Locations.ExcludeLocations -contains 'AllTrusted') {'trusted-only'} else {$null}
    sessionControls = if ($_.SessionControls.SignInFrequency.IsEnabled) { "signInFrequency:$($_.SessionControls.SignInFrequency.Value)$($_.SessionControls.SignInFrequency.Type.ToString().Substring(0,1).ToLower())" } else {$null}
  }
}

$licenses = Get-MgSubscribedSku -All | ForEach-Object { [ordered]@{ sku=$_.SkuPartNumber; purchased=$_.PrepaidUnits.Enabled; assigned=$_.ConsumedUnits } }
$doc = [ordered]@{
  tenant=[ordered]@{ name=$org.DisplayName; tenantId=$org.Id; initialDomain=($domains | Where-Object { $_.name -like '*.onmicrosoft.com' } | Select-Object -First 1).name; role=$Role }
  domains=@($domains); users=@($users); apps=@($apps); conditionalAccess=@($ca); licenses=@($licenses)
  deviceSummary=[ordered]@{
    entraJoined=@($devs | Where-Object TrustType -eq 'AzureAd').Count
    hybridJoined=@($devs | Where-Object TrustType -eq 'ServerAd').Count
    intuneEnrolled=@($devs | Where-Object IsManaged).Count }
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutFile) | Out-Null
$doc | ConvertTo-Json -Depth 8 | Set-Content -Path $OutFile -Encoding UTF8
Write-Host "Wrote $OutFile  ($($users.Count) users, $($apps.Count) apps, $($ca.Count) CA policies)" -ForegroundColor Green
Disconnect-MgGraph | Out-Null
