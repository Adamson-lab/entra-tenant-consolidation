# Entra ID tenant consolidation playbook for mergers

[![analyze](https://github.com/Adamson-lab/entra-tenant-consolidation/actions/workflows/analyze.yml/badge.svg)](https://github.com/Adamson-lab/entra-tenant-consolidation/actions/workflows/analyze.yml)

**The problem:** a merger closes, and the board expects "one company" on day 100. Underneath, two Entra ID tenants hold two sets of identities, two Conditional Access postures, two app estates and often the *same* domain name. Get it wrong and you get a mail outage, a trading desk locked out of its blotter, or a regulator asking why admin MFA vanished.

**What this repo is:** a working toolchain, not a slide deck. It reads exports of both tenants, finds what will break, scores risk per person, builds a freeze-aware wave plan, emits the per-user mapping, and renders the diagrams below from the data. It ships with a seeded fictional merger (Contoso Bank into Northwind Holdings) so every number and picture on this page is reproducible with one command.

![Architecture](reports/diagrams/01-architecture.png)

## Run it (Windows PowerShell, 30 seconds)

```powershell
git clone https://github.com/Adamson-lab/entra-tenant-consolidation.git
cd entra-tenant-consolidation
.\run.ps1
```

Then open `reports\executive-summary.md` and `reports\diagrams\`. Tests: `python -m unittest discover -s tests -v`.

## How the pipeline works

```mermaid
flowchart LR
    subgraph COLLECT[1 Collect - read only]
        E1[Export-TenantInventory.ps1<br/>source tenant] --> J1[(source-tenant.json)]
        E2[Export-TenantInventory.ps1<br/>target tenant] --> J2[(target-tenant.json)]
    end
    subgraph ANALYZE[2 Analyze - python, no network]
        J1 --> CK[checks.py<br/>domains, identity, apps,<br/>CA parity, licences, devices]
        J2 --> CK
        CK --> RK[waves.py<br/>risk score + freeze calendar]
    end
    subgraph DECIDE[3 Decide]
        RK --> R1[executive-summary.md]
        RK --> R2[findings.csv / .json]
        RK --> R3[wave-plan.csv]
        RK --> R4[user-mapping.csv]
        RK --> R5[diagrams PNG + Mermaid]
        R2 --> GATE{Test-Preflight.ps1<br/>go / no-go}
    end
    subgraph EXECUTE[4 Execute per wave]
        GATE -->|GO| SYNC[Set-CrossTenantSync.ps1<br/>trust + inbound sync]
        SYNC --> WAVE[Cutover runbook<br/>docs/runbook.md]
        WAVE --> HC[Hypercare then retire source]
    end
    GATE -->|NO-GO| FIX[Owner + dated fix] --> CK
```

## What the sample merger reveals

The planner found **44 findings, 11 of them critical**, in the seeded estate. Steering-committee view:

![Findings](reports/diagrams/05-findings.png)

```mermaid
pie showData title Findings by severity
    "critical" : 11
    "high" : 15
    "medium" : 18
```


| ID | What breaks | Why an executive cares |
|---|---|---|
| DOM-001 | A mail domain is verified in both tenants | Mail for that namespace cannot move until one side releases it |
| USR-003 | Six SMTP aliases exist in both tenants | Second owner is rejected by Exchange Online; mail goes to the wrong mailbox |
| APP-001 | 7 tier-1 apps are single-tenant (core banking, SWIFT, treasury, trading, AML, regulatory reporting, cards) | Tokens change on migration, the relying party must be updated per app |
| APP-003 | Cards Processing API holds `Directory.ReadWrite.All` | Admin consent does not transfer; unreviewed tenant-wide write access |
| CA-001 | Target has no phishing-resistant admin MFA | Migrated admins would silently lose a regulatory control |
| LIC-002 | E3 seats run out in wave 4, E5 in wave 5 | Hard stop mid-programme unless purchased early |

### Conditional Access parity

![CA parity](reports/diagrams/04-ca-parity.png)

### Where the risk concentrates

![Heatmap](reports/diagrams/03-risk-heatmap.png)

### Wave plan with freeze windows

![Wave plan](reports/diagrams/02-wave-plan.png)

```mermaid
gantt
    title Cutover waves and freeze windows
    dateFormat YYYY-MM-DD
    axisFormat %d %b
    section Freeze
    Year-end close :crit, 2027-01-25, 2027-02-05
    Quarter-end :crit, 2027-03-25, 2027-04-06
    Regulatory filing :crit, 2027-04-26, 2027-05-07
    section Waves
    Pilot (25 users) :done,w0, 2027-01-12, 3d
    Hypercare W0 :after w0, 7d
    Wave 1 (45 users) :w1, 2027-01-19, 3d
    Hypercare W1 :after w1, 7d
    Wave 2 (90 users) :w2, 2027-02-09, 3d
    Hypercare W2 :after w2, 7d
    Wave 3 (110 users) :w3, 2027-02-16, 3d
    Hypercare W3 :after w3, 7d
    Wave 4 (110 users) :w4, 2027-02-23, 3d
    Hypercare W4 :after w4, 7d
    Wave 5 (45 users) :w5, 2027-03-02, 3d
    Hypercare W5 :after w5, 7d
    Wave 6 (100 users) :w6, 2027-03-09, 3d
    Hypercare W6 :after w6, 7d
    Wave 7 (75 users) :w7, 2027-03-16, 3d
    Hypercare W7 :after w7, 7d
    Wave 8 (40 users) :w8, 2027-03-23, 3d
    Hypercare W8 :after w8, 7d
```


### Application dependency map

Departments to the apps they depend on, coloured by criticality (red = tier 1). Hexagons are SAML, rounded are OIDC, double-bordered are API apps.

```mermaid
flowchart LR
    classDef t1 fill:#fde8e6,stroke:#c0392b,color:#12263f
    classDef t2 fill:#fff4d6,stroke:#d99a1c,color:#12263f
    classDef t3 fill:#e8f1fb,stroke:#2b6cb0,color:#12263f
    D0["Compliance"]
    D1["Corporate Banking"]
    D2["Finance"]
    D3["HR"]
    D4["IT"]
    D5["Legal"]
    D6["Operations"]
    D7["Retail Banking"]
    D8["Risk"]
    D9["Trading"]
    D10["Treasury"]
    A0{{"Core Banking Gateway<br/>316 users"}}:::t1
    D7 --> A0
    D1 --> A0
    D6 --> A0
    A1{{"SWIFT Alliance Access SSO<br/>126 users"}}:::t1
    D10 --> A1
    D6 --> A1
    A2(["Treasury Management System<br/>70 users"]):::t1
    D10 --> A2
    D2 --> A2
    A3(["Trading Blotter<br/>42 users"]):::t1
    D9 --> A3
    A4{{"AML Case Management<br/>68 users"}}:::t1
    D0 --> A4
    D8 --> A4
    A5{{"Workday<br/>53 users"}}:::t2
    D3 --> A5
    D2 --> A5
    A6{{"ServiceNow<br/>591 users"}}:::t2
    A7{{"Salesforce<br/>228 users"}}:::t2
    D1 --> A7
    D7 --> A7
    A8{{"Bloomberg SSO<br/>118 users"}}:::t2
    D9 --> A8
    D10 --> A8
    D8 --> A8
    A9{{"Splunk<br/>91 users"}}:::t2
    D4 --> A9
    D8 --> A9
    A10(["Intranet Portal<br/>604 users"]):::t3
    A11(["Expense Tool<br/>597 users"]):::t3
    A12(["Legacy HR Self Service<br/>23 users"]):::t3
    D3 --> A12
    A13[["Cards Processing API<br/>235 users"]]:::t1
    D6 --> A13
    D7 --> A13
    A14[["Customer Onboarding Bot<br/>141 users"]]:::t2
    D7 --> A14
    A15(["Regulatory Reporting Portal<br/>104 users"]):::t1
    D0 --> A15
    D2 --> A15
    D8 --> A15
    A16{{"DocuSign<br/>105 users"}}:::t3
    D5 --> A16
    D1 --> A16
    A17{{"Zoom<br/>590 users"}}:::t3
```


## Day-of-cutover and rollback

```mermaid
stateDiagram-v2
    [*] --> Discovered
    Discovered --> Mapped: user-mapping.csv row created
    Mapped --> Staged: in wave group
    Staged --> Provisioned: cross-tenant sync
    Provisioned --> Active: first sign-in + MFA registered
    Active --> Hypercare
    Hypercare --> Converted: 7 days, no sev-1/2
    Converted --> [*]: source disabled, kept 90 days
    Provisioned --> Staged: ROLLBACK
    Active --> Staged: ROLLBACK
```

More: [architecture and choreography](docs/architecture.md) (domain move sequence, mail coexistence, control-plane layers, risk quadrant, pattern decision tree), [runbook](docs/runbook.md) (cutover sequence, checklist, rollback by layer), [ADRs](docs/adr).

## Using it on real tenants

1. Install the SDK: `Install-Module Microsoft.Graph -Scope CurrentUser`
2. Export both tenants (read-only scopes), naming your tier-1 apps:
   ```powershell
   .\scripts\powershell\Export-TenantInventory.ps1 -Role source -OutFile data\live\source-tenant.json -Tier1AppNames "Core Banking Gateway","SWIFT Alliance Access SSO"
   .\scripts\powershell\Export-TenantInventory.ps1 -Role target -OutFile data\live\target-tenant.json
   ```
3. Analyze: `$env:PYTHONPATH="src"; py -3 -m tcp --source data\live\source-tenant.json --target data\live\target-tenant.json --out reports`
4. Tune `config/plan.json` (start date, wave cap, freeze windows, risk weights), rerun.
5. Gate: `.\scripts\powershell\Test-Preflight.ps1` (waive with owner and expiry in `config/waivers.json`).
6. Configure trust: `.\scripts\powershell\Set-CrossTenantSync.ps1 -SourceTenantId <guid> -WhatIf`, then without `-WhatIf`.

`data/live/` is git-ignored so real tenant data never reaches GitHub.

## Honest status

- The Python analyzer, planner, diagrams and tests are executed in CI on the sample estate.
- The PowerShell scripts target Microsoft Graph PowerShell and the cross-tenant access REST API. They have not been run against a live tenant in this repo's CI, so pilot them in a non-production tenant first and use `-WhatIf`.
- The sample data is fictional. Findings on a real tenant will differ.

## Layout

```
src/tcp/            analyzer (checks, waves, diagrams, cli)
scripts/powershell/ live export, cross-tenant trust, go/no-go gate
config/             plan.json (waves, freezes, weights), waivers.json
data/sample/        seeded fictional merger
reports/            generated outputs and diagrams (committed so GitHub shows them)
docs/               architecture, runbook, ADRs
tests/              unit tests
.github/workflows/  CI
```
