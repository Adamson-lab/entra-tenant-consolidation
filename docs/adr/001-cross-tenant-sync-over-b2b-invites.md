# ADR-001 Use cross-tenant synchronization, not manual B2B invites
Status: accepted

Context: Invites require per-user redemption, create guest-typed objects and do not scale past a few hundred users.
Decision: Provision wave groups via cross-tenant synchronization with automatic redemption and inbound MFA trust.
Consequences: Source tenant must run the sync job; both tenants must be Entra ID P1 or higher. Guest accounts are not synced and are re-invited separately.
