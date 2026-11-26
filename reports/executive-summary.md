# Executive summary: Contoso Bank into Northwind Holdings

**Scope:** 640 identities, 18 applications (7 tier-1), 221 Entra-joined devices.  
**Plan:** 9 waves, first cutover 2027-01-12, last 2027-03-23.  
**Findings:** 11 critical, 15 high, 18 medium.

## Go / no-go position

**NO-GO for wave 1 until 11 critical findings have an owner and a dated fix.**

## Critical findings (decisions needed from the steering committee)

| ID | Subject | What breaks | Fix |
|---|---|---|---|
| APP-001 | AML Case Management | Single-tenant SAML app, tier1, 68 assigned users. | Re-register in the target, rotate secrets, update the relying party, and test with a pilot group before its wave. |
| APP-001 | Cards Processing API | Single-tenant API app, tier1, 235 assigned users. | Re-register in the target, rotate secrets, update the relying party, and test with a pilot group before its wave. |
| APP-001 | Core Banking Gateway | Single-tenant SAML app, tier1, 316 assigned users. | Re-register in the target, rotate secrets, update the relying party, and test with a pilot group before its wave. |
| APP-001 | Regulatory Reporting Portal | Single-tenant OIDC app, tier1, 104 assigned users. | Re-register in the target, rotate secrets, update the relying party, and test with a pilot group before its wave. |
| APP-001 | SWIFT Alliance Access SSO | Single-tenant SAML app, tier1, 126 assigned users. | Re-register in the target, rotate secrets, update the relying party, and test with a pilot group before its wave. |
| APP-001 | Trading Blotter | Single-tenant OIDC app, tier1, 42 assigned users. | Re-register in the target, rotate secrets, update the relying party, and test with a pilot group before its wave. |
| APP-001 | Treasury Management System | Single-tenant OIDC app, tier1, 70 assigned users. | Re-register in the target, rotate secrets, update the relying party, and test with a pilot group before its wave. |
| APP-003 | Cards Processing API | Holds high-privilege application permissions: Directory.ReadWrite.All, User.Read.All. | Re-justify each permission, scope down, and re-consent in the target with a documented approval. |
| CA-001 | Phishing-resistant admins | Source enforces this control (CA005 Admins phishing-resistant MFA); target is 'none'. | Deploy an equivalent policy to the target in report-only, review sign-in logs for a week, then enforce before the first wave. |
| DOM-001 | contoso-legacy.example | Domain is verified in BOTH tenants. | Remove from the tenant that should not own it (after clearing references), then verify in the other. |
| USR-003 | proxyAddress conflict | 6 SMTP addresses exist in both tenants. | Choose a single owner per alias, remove it from the other object, and convert to a shared mailbox or distribution group where appropriate. |

## Licensing cliff

- **SPE_E3**: seats run out in **wave 4**, short by **95** at that point.
- **SPE_E5**: seats run out in **wave 5**, short by **10** at that point.

## Wave plan

| Wave | Date | Users | Avg risk | Tier-1 apps | Entra devices | Gate |
|---|---|---|---|---|---|---|
| Pilot | 2027-01-12 | 25 | 14.9 | 0 | 2 | Pilot exit criteria signed off by CISO |
| Wave 1 | 2027-01-19 | 45 | 19.2 | 0 | 19 | MFA registration >= 98% and CA parity enforced |
| Wave 2 | 2027-02-09 | 90 | 30.8 | 1 | 27 | MFA registration >= 98% and CA parity enforced |
| Wave 3 | 2027-02-16 | 110 | 36.5 | 4 | 34 | Prior wave hypercare closed, ticket volume < 3% of cohort |
| Wave 4 | 2027-02-23 | 110 | 50.8 | 2 | 40 | Prior wave hypercare closed, ticket volume < 3% of cohort |
| Wave 5 | 2027-03-02 | 45 | 47.1 | 1 | 19 | Prior wave hypercare closed, ticket volume < 3% of cohort |
| Wave 6 | 2027-03-09 | 100 | 49.2 | 3 | 33 | Prior wave hypercare closed, ticket volume < 3% of cohort |
| Wave 7 | 2027-03-16 | 75 | 55.5 | 4 | 28 | Prior wave hypercare closed, ticket volume < 3% of cohort |
| Wave 8 | 2027-03-23 | 40 | 62.6 | 2 | 19 | Prior wave hypercare closed, ticket volume < 3% of cohort |
