# Architecture and choreography

All diagrams are Mermaid and render natively on GitHub.

## 1. Domain move choreography (the step that causes most outages)

A verified domain can live in only one tenant. Moving `contoso-legacy.example` means a short window where mail for that namespace has no home. This sequence keeps it under 30 minutes.

```mermaid
sequenceDiagram
    autonumber
    participant IAM as IAM Lead
    participant S as Source tenant
    participant DNS as DNS provider
    participant T as Target tenant
    participant MX as Mail gateway
    IAM->>S: Freeze UPN and alias changes
    IAM->>S: Re-point UPN suffix of all users to *.onmicrosoft.com
    IAM->>S: Remove domain from all proxyAddresses, groups, apps
    S-->>IAM: Domain has zero references
    IAM->>S: Delete domain from tenant
    IAM->>DNS: Add TXT verification record for target tenant
    IAM->>T: Verify domain
    T-->>IAM: Verified
    IAM->>T: Add domain to Exchange accepted domains (internal relay)
    IAM->>MX: Route domain to target tenant connector
    IAM->>T: Re-apply UPN suffix and aliases from mapping table
    T-->>IAM: Mail flow test passes
    Note over IAM,MX: Rollback point: if mail test fails within 30 min, reverse steps 5 to 12
```

## 2. Mail coexistence during waves

```mermaid
flowchart LR
    ext([Internet senders]) --> MX[Mail gateway / MX]
    MX -->|user already moved| TEN[(Target tenant mailbox)]
    MX -->|user not yet moved| SRC[(Source tenant mailbox)]
    SRC <-->|Internal relay connector,<br/>shared address space| TEN
    TEN --> GAL[Unified GAL via cross-tenant sync contacts]
    SRC --> GAL
    classDef warn fill:#fff4d6,stroke:#d99a1c
    class MX warn
```

## 3. Control plane layers in the surviving tenant

```mermaid
flowchart TB
    subgraph L5[Governance]
        EM[Entitlement management] --- AR[Access reviews] --- LC[Lifecycle workflows]
    end
    subgraph L4[Privilege]
        PIM[PIM just-in-time roles] --- BG[Break-glass x2] --- PAW[Admin workstations]
    end
    subgraph L3[Access policy]
        CA[Conditional Access parity set] --- AS[Authentication strengths] --- CAE[Continuous access evaluation]
    end
    subgraph L2[Identity]
        U[Users and guests] --- G[Groups and dynamic rules] --- AU[Administrative units per business line]
    end
    subgraph L1[Foundation]
        D[Verified domains] --- CT[Cross-tenant settings] --- LOG[Diagnostic logs to Sentinel]
    end
    L1 --> L2 --> L3 --> L4 --> L5
```

## 4. Risk quadrant (where to spend the steering committee's time)

```mermaid
quadrantChart
    title Migration risks: likelihood vs business impact
    x-axis Low likelihood --> High likelihood
    y-axis Low impact --> High impact
    quadrant-1 Act now
    quadrant-2 Prepare mitigation
    quadrant-3 Monitor
    quadrant-4 Automate away
    Domain mail outage: [0.45, 0.9]
    Admin sprawl imported: [0.3, 0.78]
    SAML cert expiry: [0.4, 0.62]
    Tier-1 app token break: [0.82, 0.82]
    CA control gap: [0.68, 0.72]
    Duplicate identities: [0.62, 0.58]
    License shortfall: [0.9, 0.3]
    Device re-enrol backlog: [0.75, 0.18]
    Shared mailbox renames: [0.22, 0.25]
```

## 5. Decision flow: which consolidation pattern?

```mermaid
flowchart TD
    A{Acquired entity staying<br/>operationally separate?} -->|Yes, regulator or contract requires it| B[Keep both tenants<br/>B2B collaboration + cross-tenant access]
    A -->|No| C{Source has fewer than<br/>5,000 users and no federated domains?}
    C -->|Yes| D[Absorb into acquirer tenant<br/>cross-tenant sync, this repo]
    C -->|No| E{Target tenant security posture<br/>meets acquirer's own baseline?}
    E -->|Yes| D
    E -->|No| F[Fix target first, or build a new<br/>greenfield tenant and move both]
    D --> G{Source forest consolidating?}
    G -->|Yes| H[ADMT forest migration<br/>then hard-match]
    G -->|No| I[Cloud Sync from source AD<br/>into target tenant]
```
