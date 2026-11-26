"""Generate a deterministic, realistic M&A scenario (fictional companies).

Acquirer  = Northwind Holdings (target tenant)  ~ 900 users
Acquired  = Contoso Bank       (source tenant)  ~ 650 users
Seeded, so CI output is reproducible. Deliberately plants conflicts so the
analyzer has real work to do.
"""
import json
import pathlib
import random
import uuid

rnd = random.Random(2026)
OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "sample"
FIRST = ("Amara Chidi Ngozi Tunde Folake Emeka Sade Kunle Ifeoma Bola Zainab Musa Halima Obinna Chiamaka Segun "
         "Yetunde Femi Aisha Ibrahim John Mary Peter Grace David Sarah Daniel Esther James Linda Paul Ruth Mark "
         "Anna Luke Rita Omar Fatima Hassan Lena Marco Sofia Ivan Mei Raj Priya Kenji Yuki").split()
LAST = ("Adeyemi Okafor Bello Balogun Eze Danjuma Abubakar Nwosu Okonkwo Adamu Smith Jones Brown Taylor Wilson "
        "Clark Lewis Walker Hall Young King Wright Scott Green Baker Adams Nelson Hill Campbell Mitchell Roberts "
        "Carter Phillips Evans Turner Parker Collins Edwards Stewart Morris").split()

SRC_DEPTS = {"Retail Banking": 150, "Corporate Banking": 90, "Treasury": 40, "Trading": 45, "Compliance": 35,
             "Risk": 40, "Operations": 100, "IT": 60, "HR": 25, "Finance": 35, "Legal": 20}
REGULATED = ["Treasury", "Trading", "Compliance", "Risk"]


def guid():
    return str(uuid.UUID(int=rnd.getrandbits(128)))


def mk_users(prefix, domain, depts, emp_prefix, extra_domains=()):
    users, seen, i = [], set(), 0
    for dept, n in depts.items():
        for _ in range(n):
            i += 1
            while True:
                f, l = rnd.choice(FIRST), rnd.choice(LAST)
                nick = (f[0] + l).lower() if rnd.random() < .5 else f"{f}.{l}".lower()
                if nick not in seen:
                    seen.add(nick)
                    break
            dom = domain if not extra_domains or rnd.random() < .85 else rnd.choice(extra_domains)
            users.append(dict(
                id=guid(), displayName=f"{f} {l}", mailNickname=nick, userPrincipalName=f"{nick}@{dom}",
                mail=f"{nick}@{dom}", proxyAddresses=[f"SMTP:{nick}@{dom}"], employeeId=f"{emp_prefix}{10000 + i}",
                department=dept, userType="Member", accountEnabled=True,
                onPremisesSyncEnabled=rnd.random() < (.78 if prefix == "src" else .55), licenses=[],
                mfaRegistered=rnd.random() < (.82 if prefix == "src" else .91),
                entraJoinedDevices=1 if rnd.random() < .35 else 0, hybridJoinedDevices=1 if rnd.random() < .5 else 0,
                privilegedRoles=[], apps=[]))
    return users


src_users = mk_users("src", "contosobank.example", SRC_DEPTS, "CB-", ("contosolife.example",))
tgt_depts = {"Sales": 220, "Engineering": 240, "Operations": 140, "Finance": 60, "HR": 40, "Legal": 25,
             "IT": 90, "Marketing": 55, "Supply Chain": 30}
tgt_users = mk_users("tgt", "northwind.example", tgt_depts, "NW-")

# licensing
for u in src_users:
    u["licenses"] = ["SPE_E5"] if u["department"] in REGULATED + ["IT"] else ["SPE_E3"]
    if u["department"] in ("Finance", "Treasury") and rnd.random() < .6:
        u["licenses"].append("POWER_BI_PRO")
    if u["department"] == "IT":
        u["licenses"].append("VISIO_PLAN2")
for u in tgt_users:
    u["licenses"] = ["SPE_E3"] if rnd.random() < .85 else ["SPE_E5"]

# privileged roles
for u in rnd.sample([x for x in src_users if x["department"] == "IT"], 9):
    u["privilegedRoles"] = [rnd.choice(["Global Administrator", "Privileged Role Administrator", "Exchange Administrator"])]
for u in src_users[:4]:
    u["privilegedRoles"] = ["Global Administrator"]

# guests in the source tenant
for i in range(12):
    src_users.append(dict(
        id=guid(), displayName=f"Partner Guest {i}", mailNickname=f"pg{i}_partner",
        userPrincipalName=f"pg{i}_partner.example#EXT#@contosobank.onmicrosoft.com", mail=f"pg{i}@partner.example",
        proxyAddresses=[f"SMTP:pg{i}@partner.example"], employeeId=None, department="External", userType="Guest",
        accountEnabled=True, onPremisesSyncEnabled=False, licenses=[], mfaRegistered=True, entraJoinedDevices=0,
        hybridJoinedDevices=0, privilegedRoles=[], apps=[]))

# ---- planted conflicts ---------------------------------------------------
members = [x for x in src_users if x["userType"] == "Member"]
for _ in range(14):   # (a) same human in both tenants
    s = rnd.choice([x for x in members if x["department"] in ("IT", "Finance", "Legal", "HR", "Operations")])
    rnd.choice(tgt_users)["employeeId"] = s["employeeId"]
for _ in range(9):    # (b) mailNickname collisions
    rnd.choice(tgt_users)["mailNickname"] = rnd.choice(members[:300])["mailNickname"]
for alias in ["helpdesk", "payroll", "treasury-ops", "swift-alerts", "legal", "ir"]:   # (c) shared aliases
    for pool in (members, tgt_users):
        rnd.choice(pool)["proxyAddresses"].append(f"smtp:{alias}@shared-legacy.example")
for _ in range(7):    # (d) same display name, different person
    rnd.choice(tgt_users)["displayName"] = rnd.choice(members[:300])["displayName"]

# ---- apps ----------------------------------------------------------------
ALL = list(SRC_DEPTS)
APP_DEFS = [
    ("Core Banking Gateway", "saml", "tier1", ["Retail Banking", "Corporate Banking", "Operations"], True, ["User.Read"]),
    ("SWIFT Alliance Access SSO", "saml", "tier1", ["Treasury", "Operations"], True, ["User.Read"]),
    ("Treasury Management System", "oidc", "tier1", ["Treasury", "Finance"], True, ["User.Read", "Directory.Read.All"]),
    ("Trading Blotter", "oidc", "tier1", ["Trading"], True, ["User.Read"]),
    ("AML Case Management", "saml", "tier1", ["Compliance", "Risk"], True, ["User.Read"]),
    ("Workday", "saml", "tier2", ["HR", "Finance"], False, ["User.Read"]),
    ("ServiceNow", "saml", "tier2", ALL, False, ["User.Read"]),
    ("Salesforce", "saml", "tier2", ["Corporate Banking", "Retail Banking"], False, ["User.Read"]),
    ("Bloomberg SSO", "saml", "tier2", ["Trading", "Treasury", "Risk"], False, ["User.Read"]),
    ("Splunk", "saml", "tier2", ["IT", "Risk"], False, ["User.Read"]),
    ("Intranet Portal", "oidc", "tier3", ALL, False, ["User.Read"]),
    ("Expense Tool", "oidc", "tier3", ALL, False, ["User.Read"]),
    ("Legacy HR Self Service", "oidc", "tier3", ["HR"], False, ["User.Read"]),
    ("Cards Processing API", "api", "tier1", ["Operations", "Retail Banking"], True, ["Directory.ReadWrite.All", "User.Read.All"]),
    ("Customer Onboarding Bot", "api", "tier2", ["Retail Banking"], False, ["Mail.Send", "User.Read.All"]),
    ("Regulatory Reporting Portal", "oidc", "tier1", ["Compliance", "Finance", "Risk"], True, ["User.Read"]),
    ("DocuSign", "saml", "tier3", ["Legal", "Corporate Banking"], False, ["User.Read"]),
    ("Zoom", "saml", "tier3", ALL, False, ["User.Read"]),
]
src_apps = []
for name, proto, tier, depts, tsc, perms in APP_DEFS:
    cert = rnd.choice([12, 25, 47, 80, 160, 300, 540]) if proto == "saml" else None
    src_apps.append(dict(
        appId=guid(), displayName=name, protocol=proto, criticality=tier, signInAudience="AzureADMyOrg",
        usesTenantSpecificClaims=tsc, appPermissions=perms, ssoCertExpiresInDays=cert, assignedDepartments=depts,
        redirectUris=[f"https://{name.lower().replace(' ', '-')}.contosobank.example/auth"]))
for u in src_users:
    for a in src_apps:
        if u["department"] in a["assignedDepartments"] and rnd.random() < .93:
            u["apps"].append(a["appId"])
tgt_apps = [dict(appId=guid(), displayName=n, protocol="saml", criticality="tier2", signInAudience="AzureADMyOrg",
                 usesTenantSpecificClaims=False, appPermissions=["User.Read"],
                 ssoCertExpiresInDays=rnd.choice([90, 200, 400]), assignedDepartments=[], redirectUris=[])
            for n in ["Workday", "ServiceNow", "Salesforce", "Zoom", "Slack"]]


# ---- conditional access ----------------------------------------------------
def ca(name, state="enabled", users="All", apps="All", grants=("mfa",), compliant=False, legacy=False,
       risk=None, location=None, session=None):
    return dict(name=name, state=state, users=users, apps=apps, grantControls=list(grants),
                requireCompliantDevice=compliant, blocksLegacyAuth=legacy, signInRiskBlock=risk,
                locationCondition=location, sessionControls=session)


src_ca = [
    ca("CA001 Require MFA all users"),
    ca("CA002 Block legacy auth", grants=("block",), legacy=True),
    ca("CA003 Compliant device for tier1 apps", apps="tier1", grants=("mfa", "compliantDevice"), compliant=True),
    ca("CA004 Block high sign-in risk", risk="high", grants=("block",)),
    ca("CA005 Admins phishing-resistant MFA", users="Admins", grants=("authStrength:phishingResistant",)),
    ca("CA006 Trusted locations only for Treasury", users="Treasury", location="trusted-only"),
    ca("CA007 Sign-in frequency 4h for tier1", apps="tier1", session="signInFrequency:4h"),
    ca("CA008 Terms of use new devices", state="enabledForReportingButNotEnforced", grants=("termsOfUse",)),
    ca("CA009 Block guests from tier1", users="Guests", apps="tier1", grants=("block",)),
]
tgt_ca = [
    ca("NW-CA01 MFA all users"),
    ca("NW-CA02 Block legacy auth", grants=("block",), legacy=True),
    ca("NW-CA03 Compliant or hybrid device for all apps", grants=("compliantDevice",), compliant=True),
    ca("NW-CA04 Admins MFA", users="Admins"),
    ca("NW-CA05 Block high user risk", risk="high", grants=("block",)),
    ca("NW-CA06 Report-only: sign-in frequency 12h", state="enabledForReportingButNotEnforced", session="signInFrequency:12h"),
]

# ---- licenses ---------------------------------------------------------------
cnt = lambda pool, s: sum(s in u["licenses"] for u in pool)
tgt_lic = [dict(sku="SPE_E3", purchased=1100, assigned=cnt(tgt_users, "SPE_E3") + 120),
           dict(sku="SPE_E5", purchased=300, assigned=cnt(tgt_users, "SPE_E5") + 60),
           dict(sku="POWER_BI_PRO", purchased=400, assigned=260)]
src_lic = [dict(sku=s, purchased=cnt(src_users, s) + 20, assigned=cnt(src_users, s))
           for s in ("SPE_E3", "SPE_E5", "POWER_BI_PRO", "VISIO_PLAN2")]


def domains(names, federated=()):
    return [dict(name=n, isVerified=True, isDefault=(i == 0),
                 authenticationType="Federated" if n in federated else "Managed") for i, n in enumerate(names)]


def devsum(pool, intune):
    return dict(entraJoined=sum(u["entraJoinedDevices"] for u in pool),
                hybridJoined=sum(u["hybridJoinedDevices"] for u in pool), intuneEnrolled=int(len(pool) * intune))


source = dict(tenant=dict(name="Contoso Bank", tenantId=guid(), initialDomain="contosobank.onmicrosoft.com", role="source"),
              domains=domains(["contosobank.example", "contosolife.example", "contoso-legacy.example"], ("contosolife.example",)),
              users=src_users, apps=src_apps, conditionalAccess=src_ca, licenses=src_lic, deviceSummary=devsum(src_users, .6))
target = dict(tenant=dict(name="Northwind Holdings", tenantId=guid(), initialDomain="northwind.onmicrosoft.com", role="target"),
              domains=domains(["northwind.example", "contoso-legacy.example"]),   # planted: legacy domain already verified in target
              users=tgt_users, apps=tgt_apps, conditionalAccess=tgt_ca, licenses=tgt_lic, deviceSummary=devsum(tgt_users, .8))

OUT.mkdir(parents=True, exist_ok=True)
for n, d in (("source-tenant.json", source), ("target-tenant.json", target)):
    (OUT / n).write_text(json.dumps(d, indent=1))
print(f"source users={len(src_users)} target users={len(tgt_users)} apps={len(src_apps)}")
