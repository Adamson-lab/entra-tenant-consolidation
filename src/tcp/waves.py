"""Risk scoring and wave planning.

Principle: people who work together move together (collaboration cohesion),
the riskiest cohorts move last (after the runbook is proven), and nothing
cuts over inside a freeze window.
"""
import datetime as dt
from collections import defaultdict


def user_risk(u, app_tier, w, regulated):
    s = 0
    if u["privilegedRoles"]:
        s += w["privileged"]
    if u["onPremisesSyncEnabled"]:
        s += w["onPremSynced"]
    for a in u["apps"]:
        t = app_tier.get(a)
        s += w["tier1App"] if t == "tier1" else w["tier2App"] if t == "tier2" else 0
    if u["entraJoinedDevices"]:
        s += w["entraJoinedDevice"]
    if not u["mfaRegistered"]:
        s += w["noMfa"]
    if u["department"] in regulated:
        s += w["regulatedDept"]
    return s


def _next_slot(day, weekday, freezes):
    while True:
        while day.weekday() != weekday:
            day += dt.timedelta(days=1)
        hit = next((f for f in freezes if f[0] <= day <= f[1]), None)
        if not hit:
            return day
        day = hit[1] + dt.timedelta(days=1)


def plan(src, cfg, tgt_license_headroom=None):
    app_tier = {a["appId"]: a["criticality"] for a in src["apps"]}
    members = [u for u in src["users"] if u["userType"] == "Member"]
    for u in members:
        u["_risk"] = user_risk(u, app_tier, cfg["riskWeights"], set(cfg["regulatedDepartments"]))
    by_dept = defaultdict(list)
    for u in members:
        by_dept[u["department"]].append(u)

    pilot_pool = sorted(by_dept.get(cfg["pilotDepartment"], []), key=lambda u: u["_risk"])
    pilot = pilot_pool[:cfg["pilotSize"]]
    pilot_ids = {u["id"] for u in pilot}
    remaining = {d: [u for u in us if u["id"] not in pilot_ids] for d, us in by_dept.items()}
    order = sorted(remaining, key=lambda d: sum(u["_risk"] for u in remaining[d]) / max(1, len(remaining[d])))

    waves = [{"wave": 0, "label": "Pilot", "users": pilot, "departments": {cfg["pilotDepartment"]: len(pilot)}}]
    cur, n = {"users": [], "departments": defaultdict(int)}, 1

    def flush():
        nonlocal cur, n
        if cur["users"]:
            waves.append({"wave": n, "label": f"Wave {n}", "users": cur["users"], "departments": dict(cur["departments"])})
            n += 1
            cur = {"users": [], "departments": defaultdict(int)}

    for d in order:
        us = sorted(remaining[d], key=lambda u: u["_risk"])
        cap = cfg["maxWaveSize"]
        # keep a department intact when it fits in one wave; otherwise split it
        if len(us) <= cap and len(cur["users"]) + len(us) > cap:
            flush()
        for u in us:
            if len(cur["users"]) >= cap:
                flush()
            cur["users"].append(u)
            cur["departments"][d] += 1
    flush()

    freezes = [(dt.date.fromisoformat(f["start"]), dt.date.fromisoformat(f["end"])) for f in cfg["freezeWindows"]]
    day = dt.date.fromisoformat(cfg["startDate"])
    cumulative = defaultdict(int)
    for w in waves:
        day = _next_slot(day, cfg["cutoverWeekday"], freezes)
        w["date"] = day
        w["size"] = len(w["users"])
        w["avgRisk"] = round(sum(u["_risk"] for u in w["users"]) / max(1, w["size"]), 1)
        w["maxRisk"] = max((u["_risk"] for u in w["users"]), default=0)
        w["tier1Apps"] = len({a for u in w["users"] for a in u["apps"] if app_tier.get(a) == "tier1"})
        w["entraDevices"] = sum(u["entraJoinedDevices"] for u in w["users"])
        for u in w["users"]:
            for s in u["licenses"]:
                cumulative[s] += 1
        w["cumLicenses"] = dict(cumulative)
        w["gate"] = ("Pilot exit criteria signed off by CISO" if w["wave"] == 0 else
                     "MFA registration >= 98% and CA parity enforced" if w["wave"] <= 2 else
                     "Prior wave hypercare closed, ticket volume < 3% of cohort")
        day += dt.timedelta(days=7)
    return waves


def license_crossing(waves, headroom):
    """First wave where cumulative demand exceeds free seats, per SKU."""
    cross = {}
    for sku, free in headroom.items():
        for w in waves:
            if w["cumLicenses"].get(sku, 0) > free:
                cross[sku] = (w["wave"], w["cumLicenses"][sku] - free)
                break
    return cross
