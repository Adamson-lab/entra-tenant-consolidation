"""Pre-merge conflict and readiness checks.

Each check returns a list of Finding. Severity: critical blocks cutover,
high needs a mitigation owner, medium is tracked, info is for the record.
"""
from collections import defaultdict
from dataclasses import dataclass, asdict, field

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "info": 3}
HIGH_PRIV_APP_PERMS = {"Directory.ReadWrite.All", "Directory.Read.All", "User.Read.All", "Mail.Send"}


@dataclass
class Finding:
    id: str
    severity: str
    category: str
    subject: str
    detail: str
    remediation: str
    count: int = 1
    refs: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def _smtp(u):
    return {p.split(":", 1)[1].lower() for p in u.get("proxyAddresses", []) if p.lower().startswith("smtp:")}


def check_domains(src, tgt):
    out = []
    tgt_domains = {d["name"].lower() for d in tgt["domains"]}
    for d in src["domains"]:
        n = d["name"].lower()
        if n in tgt_domains:
            out.append(Finding("DOM-001", "critical", "Domains", n,
                               "Domain is verified in BOTH tenants. A domain can live in only one tenant, so mail flow and UPN suffix "
                               "moves are blocked until it is released from one side.",
                               "Remove from the tenant that should not own it (after clearing references), then verify in the other. "
                               "Schedule DNS TXT changes inside a freeze-safe window."))
        if d["authenticationType"] == "Federated":
            out.append(Finding("DOM-002", "high", "Domains", n,
                               "Domain is federated (AD FS or third-party IdP). It must be converted to managed (PHS or PTA) before it "
                               "can move, which changes every user's sign-in path.",
                               "Pilot staged rollout to managed authentication, then convert the domain. Keep the federation trust "
                               "documented for rollback."))
    return out


def check_users(src, tgt):
    out = []
    tgt_members = [u for u in tgt["users"] if u["userType"] == "Member"]
    src_members = [u for u in src["users"] if u["userType"] == "Member"]
    tgt_emp = {u["employeeId"]: u for u in tgt_members if u.get("employeeId")}
    dupes = [(s, tgt_emp[s["employeeId"]]) for s in src_members if s.get("employeeId") in tgt_emp]
    if dupes:
        out.append(Finding("USR-001", "high", "Identity", "Same person in both tenants",
                           f"{len(dupes)} people hold an account in each tenant (matched on employeeId). Provisioning a second "
                           "identity creates split mailboxes, duplicate licenses and broken audit trails.",
                           "Decide the surviving account per person, merge group and app access to it, soft-match before sync, "
                           "retire the other after the wave.", len(dupes), [s["userPrincipalName"] for s, _ in dupes][:10]))
    tgt_nick = defaultdict(list)
    for u in tgt["users"]:
        tgt_nick[u["mailNickname"].lower()].append(u)
    nick = [(s, tgt_nick[s["mailNickname"].lower()][0]) for s in src_members
            if s["mailNickname"].lower() in tgt_nick and s.get("employeeId") not in tgt_emp]
    if nick:
        out.append(Finding("USR-002", "high", "Identity", "mailNickname collision",
                           f"{len(nick)} different people share a mailNickname across tenants. Cross-tenant sync and Exchange "
                           "provisioning will fail or silently rename one of them.",
                           "Pre-assign a deterministic suffix, for example <nick>.cb, and record it in the mapping table.",
                           len(nick), [s["mailNickname"] for s, _ in nick][:10]))
    tgt_smtp = defaultdict(list)
    for u in tgt["users"]:
        for a in _smtp(u):
            tgt_smtp[a].append(u)
    px = sorted({a for s in src["users"] for a in _smtp(s) if a in tgt_smtp})
    if px:
        out.append(Finding("USR-003", "critical", "Messaging", "proxyAddress conflict",
                           f"{len(px)} SMTP addresses exist in both tenants. Exchange Online rejects the second owner, so those users "
                           "cannot be provisioned and mail to the alias goes to the wrong mailbox.",
                           "Choose a single owner per alias, remove it from the other object, and convert to a shared mailbox or "
                           "distribution group where appropriate.", len(px), px[:10]))
    names = defaultdict(list)
    for u in tgt_members:
        names[u["displayName"].lower()].append(u)
    amb = [s for s in src_members if s["displayName"].lower() in names and s.get("employeeId") not in tgt_emp]
    if amb:
        out.append(Finding("USR-004", "medium", "Identity", "Ambiguous display names",
                           f"{len(amb)} users share a displayName with someone in the target. Not a technical blocker, but the GAL becomes "
                           "ambiguous and helpdesk match-by-name errors will appear.",
                           "Append department or location to displayName in the unified GAL.", len(amb)))
    synced = [u for u in src_members if u["onPremisesSyncEnabled"]]
    out.append(Finding("USR-005", "high", "Identity", "On-premises synced users",
                       f"{len(synced)} of {len(src_members)} source users are mastered in on-premises AD. Cross-tenant sync can provision "
                       "them, but source of authority stays in the old forest until it is consolidated or re-pointed.",
                       "Choose: (A) keep source AD and run Cloud Sync into the target tenant, or (B) migrate the forest with ADMT. "
                       "Decide before wave 1 because it sets the hard-match strategy.", len(synced)))
    guests = [u for u in src["users"] if u["userType"] == "Guest"]
    if guests:
        out.append(Finding("USR-006", "medium", "Identity", "Source guests",
                           f"{len(guests)} guest accounts exist in the source tenant. They do not move with cross-tenant sync and "
                           "must be re-invited.", "Export, de-duplicate against target guests, re-invite with B2B direct connect "
                           "where possible.", len(guests)))
    nomfa = [u for u in src_members if not u["mfaRegistered"]]
    pct = 100 * len(nomfa) / max(1, len(src_members))
    out.append(Finding("MFA-001", "high" if pct > 10 else "medium", "Authentication", "Users with no MFA registered",
                       f"{len(nomfa)} users ({pct:.0f}%) have no strong authentication method. Inbound MFA trust only helps users who "
                       "already registered; the rest hit a registration wall on day one.",
                       "Run a Temporary Access Pass campaign two weeks before each wave. Gate each wave on at least 98% registration.",
                       len(nomfa)))
    admins = [u for u in src_members if u["privilegedRoles"]]
    ga = [u for u in admins if "Global Administrator" in u["privilegedRoles"]]
    if len(ga) > 5:
        out.append(Finding("PRIV-001", "high", "Privilege", "Excess Global Administrators",
                           f"{len(ga)} Global Administrators in the source. Merging unchanged would import standing privilege into the "
                           "acquirer's tenant.", "Do not sync privileged roles. Rebuild admin access in the target with PIM, "
                           "break-glass accounts and phishing-resistant MFA.", len(ga)))
    return out


def check_apps(src, tgt):
    out = []
    tgt_apps = {a["displayName"].lower() for a in tgt["apps"]}
    users_by_app = defaultdict(int)
    for u in src["users"]:
        for a in u["apps"]:
            users_by_app[a] += 1
    for a in src["apps"]:
        n = users_by_app[a["appId"]]
        if a["signInAudience"] == "AzureADMyOrg":
            sev = "critical" if a["criticality"] == "tier1" and a["usesTenantSpecificClaims"] else \
                  "high" if a["criticality"] == "tier1" else "medium"
            twin = " The target already hosts an app of the same name, so decide whether to consolidate." if a["displayName"].lower() in tgt_apps else ""
            out.append(Finding("APP-001", sev, "Applications", a["displayName"],
                               f"Single-tenant {a['protocol'].upper()} app, {a['criticality']}, {n} assigned users."
                               + (" Uses tenant-specific claims or IDs, so tokens will change." if a["usesTenantSpecificClaims"] else "")
                               + twin,
                               "Re-register in the target, rotate secrets, update the relying party, and test with a pilot group "
                               "before its wave.", n, [a["appId"]]))
        if a.get("ssoCertExpiresInDays") is not None and a["ssoCertExpiresInDays"] <= 90:
            out.append(Finding("APP-002", "high" if a["ssoCertExpiresInDays"] <= 30 else "medium", "Applications", a["displayName"],
                               f"SAML signing certificate expires in {a['ssoCertExpiresInDays']} days, inside the migration window.",
                               "Roll the certificate once, in the target tenant, instead of twice."))
        hp = sorted(set(a["appPermissions"]) & HIGH_PRIV_APP_PERMS)
        if a["protocol"] == "api" and hp:
            out.append(Finding("APP-003", "critical" if "Directory.ReadWrite.All" in hp else "high", "Applications", a["displayName"],
                               f"Holds high-privilege application permissions: {', '.join(hp)}. Admin consent does not transfer between tenants.",
                               "Re-justify each permission, scope down, and re-consent in the target with a documented approval."))
    return out


def _signature(p):
    return (p["users"], p["apps"], tuple(sorted(p["grantControls"])), p["requireCompliantDevice"],
            p["blocksLegacyAuth"], p["signInRiskBlock"], p["locationCondition"], p["sessionControls"])


CONTROLS = ["MFA", "Block legacy auth", "Compliant device (tier1)", "Phishing-resistant admins",
            "Sign-in risk block", "Location restriction", "Sign-in frequency", "Block guests from tier1"]


def ca_matrix(tenant):
    """Which controls does a tenant effectively enforce? Returns {control: (state, policy)}."""
    m = {c: ("none", "") for c in CONTROLS}
    for p in tenant["conditionalAccess"]:
        st = "enforced" if p["state"] == "enabled" else "report-only" if "Reporting" in p["state"] else "off"
        g = p["grantControls"]
        hits = []
        if "mfa" in g and p["users"] == "All":
            hits.append("MFA")
        if p["blocksLegacyAuth"]:
            hits.append("Block legacy auth")
        if p["requireCompliantDevice"] and p["apps"] in ("tier1", "All"):
            hits.append("Compliant device (tier1)")
        if any(x.startswith("authStrength:phishingResistant") for x in g):
            hits.append("Phishing-resistant admins")
        if p["signInRiskBlock"]:
            hits.append("Sign-in risk block")
        if p["locationCondition"]:
            hits.append("Location restriction")
        if p["sessionControls"] and "signInFrequency" in p["sessionControls"]:
            hits.append("Sign-in frequency")
        if p["users"] == "Guests" and "block" in g:
            hits.append("Block guests from tier1")
        if p["users"] == "Admins" and "mfa" in g and "MFA" not in hits:
            pass
        for h in hits:
            if m[h][0] in ("none", "report-only") or st == "enforced":
                m[h] = (st, p["name"])
    return m


def check_ca(src, tgt):
    out, ms, mt = [], ca_matrix(src), ca_matrix(tgt)
    rank = {"none": 0, "off": 0, "report-only": 1, "enforced": 2}
    gaps = [c for c in CONTROLS if rank[ms[c][0]] > rank[mt[c][0]]]
    for c in gaps:
        sev = "critical" if c in ("Compliant device (tier1)", "Phishing-resistant admins") else "high"
        out.append(Finding("CA-001", sev, "Conditional Access", c,
                           f"Source enforces this control ({ms[c][1]}); target is '{mt[c][0]}'. Migrated users and tier-1 apps would "
                           "silently lose a regulatory-relevant control.",
                           "Deploy an equivalent policy to the target in report-only, review sign-in logs for a week, then enforce "
                           "before the first wave."))
    return out


def check_licenses(src, tgt, incoming):
    out, tl = [], {l["sku"]: l for l in tgt["licenses"]}
    need = defaultdict(int)
    for u in incoming:
        for s in u["licenses"]:
            need[s] += 1
    for sku, n in sorted(need.items()):
        t = tl.get(sku)
        if t is None:
            out.append(Finding("LIC-001", "high", "Licensing", sku, f"{n} users need {sku}, which the target tenant does not own.",
                               "Add the SKU to the acquirer's agreement or map to an equivalent before wave 1.", n))
        elif t["purchased"] - t["assigned"] < n:
            short = n - (t["purchased"] - t["assigned"])
            out.append(Finding("LIC-002", "high", "Licensing", sku,
                               f"Need {n}, free {t['purchased'] - t['assigned']}: short by {short} seats at full migration.",
                               "Purchase or true-up before the wave that crosses the limit. See wave plan for the exact crossing point.", short))
    return out


def check_devices(src):
    d = src["deviceSummary"]
    return [Finding("DEV-001", "high", "Devices", "Entra-joined devices",
                    f"{d['entraJoined']} Entra-joined devices cannot be moved between tenants and must be re-provisioned (Autopilot reset); "
                    f"{d['hybridJoined']} hybrid-joined devices need their connection point or Cloud Sync re-pointed; "
                    f"{d['intuneEnrolled']} are Intune-enrolled and must be re-enrolled in the target.",
                    "Schedule device re-provisioning with the user's wave, not before. Pre-stage Autopilot hardware hashes into the target.",
                    d["entraJoined"])]


def run_all(src, tgt):
    incoming = [u for u in src["users"] if u["userType"] == "Member"]
    findings = (check_domains(src, tgt) + check_users(src, tgt) + check_apps(src, tgt)
                + check_ca(src, tgt) + check_licenses(src, tgt, incoming) + check_devices(src))
    findings.sort(key=lambda f: (SEV_ORDER[f.severity], f.category, f.id, f.subject))
    return findings
