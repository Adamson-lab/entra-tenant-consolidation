# ADR-003 Privileged roles are rebuilt in the target, never synced
Status: accepted

Context: The source tenant has more Global Administrators than policy allows.
Decision: Admin access is re-issued in the target through PIM with phishing-resistant MFA and two break-glass accounts. Cross-tenant sync attribute mappings exclude role assignments.
Consequences: Admins lose standing access on migration day and must request just-in-time elevation.
