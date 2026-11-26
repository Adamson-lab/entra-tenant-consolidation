# Cutover runbook (per wave)

Cutover is a Tuesday. Every step has an owner, a time-box and a rollback.

## 1. Day-of sequence

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant SYNC as Cross-tenant sync
    participant T as Target tenant
    participant APP as Re-registered apps
    participant DEV as Device (Autopilot)
    participant SD as Service desk
    SYNC->>T: Provision wave group as B2B members
    T-->>SYNC: Accounts created (UPN from user-mapping.csv)
    SD->>U: Temporary Access Pass + wave guide
    U->>T: First sign-in
    T->>T: Evaluate CA parity set (trusts source MFA claim)
    T-->>U: Prompt to register target MFA methods
    U->>APP: Open tier-1 app
    APP->>T: OIDC/SAML against target tenant
    T-->>APP: Token with new tenant claims
    U->>DEV: Reset and enrol device
    DEV->>T: Autopilot join + Intune compliance
    SD-->>U: Hypercare for 7 days
```

## 2. User state machine and rollback

```mermaid
stateDiagram-v2
    [*] --> Discovered
    Discovered --> Mapped: user-mapping.csv row created
    Mapped --> Staged: in wave group, not yet synced
    Staged --> Provisioned: cross-tenant sync
    Provisioned --> Active: first sign-in + MFA registered
    Active --> Hypercare
    Hypercare --> Converted: 7 days, no sev-1/2 tickets
    Converted --> [*]: source account disabled, retained 90d
    Provisioned --> Staged: ROLLBACK remove from wave group
    Active --> Staged: ROLLBACK re-enable source, block target
    Hypercare --> Active: incident, extend hypercare
```

## 3. Go / no-go checklist (all must be true)

- [ ] `.\scripts\powershell\Test-Preflight.ps1` exits 0 (no unwaived critical findings)
- [ ] CA parity policies in **enforced** state in the target for at least 7 days
- [ ] MFA registration of the wave cohort is at least 98 percent
- [ ] Tier-1 apps in this wave pass pilot-group test in the target
- [ ] Licence headroom covers the cumulative demand (`reports/executive-summary.md`, licensing cliff)
- [ ] Not inside a freeze window (`config/plan.json`)
- [ ] Rollback rehearsed on pilot users within the last 30 days
- [ ] Service desk staffed at 2x normal and briefed

## 4. Cross-tenant sync configuration (source tenant side)

1. In the **target** tenant run `scripts/powershell/Set-CrossTenantSync.ps1 -SourceTenantId <guid> -WhatIf`, review, then rerun without `-WhatIf`.
2. In the **source** tenant: Entra ID, External Identities, Cross-tenant synchronization, Configurations, New configuration.
3. Enter the target tenant ID, test the connection, set provisioning to automatic.
4. Scope to a security group named `wave-<n>-migrate` (assignments, not "all users").
5. Attribute mappings: keep `userPrincipalName` as the rewrite in `reports/user-mapping.csv`; set `employeeId` to the source value; **do not** map privileged role memberships.
6. Provision on demand for the pilot group first, check the audit log, then turn the job on.

## 5. Rollback by layer

| Layer | Rollback | Time to roll back |
|---|---|---|
| Sync | Remove users from `wave-<n>-migrate`, disable job | 5 min |
| Access | Re-enable source sign-in, block target accounts with CA | 15 min |
| Apps | Re-point relying party to source app registration (kept 30 days) | 30 min per app |
| Domain | Reverse choreography, see `architecture.md` section 1 | 30 min |
| Devices | Not reversible without re-provisioning: only move devices in the last hour of a wave | n/a |
