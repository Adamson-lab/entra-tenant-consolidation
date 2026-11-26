"""Command line entry point:  python -m tcp.cli --source ... --target ... --out reports"""
import argparse
import csv
import json
import pathlib
import sys

from . import checks, diagrams, waves as wv


def load(p):
    return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))


def build_mapping(src, tgt, plan_waves):
    """Per-user migration decision: create | merge | skip, plus the target UPN."""
    tgt_emp = {u["employeeId"]: u for u in tgt["users"] if u.get("employeeId")}
    tgt_nick = {u["mailNickname"].lower() for u in tgt["users"]}
    wave_of = {u["id"]: w["wave"] for w in plan_waves for u in w["users"]}
    rows = []
    for u in src["users"]:
        if u["userType"] != "Member":
            rows.append([u["userPrincipalName"], "", "", "reinvite-guest", "", ""])
            continue
        if u.get("employeeId") in tgt_emp:
            t = tgt_emp[u["employeeId"]]
            rows.append([u["userPrincipalName"], t["userPrincipalName"], t["mailNickname"], "merge", wave_of.get(u["id"], ""), u["_risk"]])
            continue
        nick = u["mailNickname"]
        dom = u["userPrincipalName"].split("@")[1]
        if nick.lower() in tgt_nick:
            nick = nick + ".cb"
        rows.append([u["userPrincipalName"], f"{nick}@{dom}", nick, "create", wave_of.get(u["id"], ""), u["_risk"]])
    return rows


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def summary_md(src, tgt, findings, plan_waves, crossings, ctx):
    sev = {s: sum(1 for f in findings if f.severity == s) for s in ("critical", "high", "medium")}
    last = plan_waves[-1]["date"]
    lines = [f"# Executive summary: {src['tenant']['name']} into {tgt['tenant']['name']}", "",
             f"**Scope:** {ctx['src_members']} identities, {ctx['src_apps']} applications ({ctx['src_tier1']} tier-1), "
             f"{src['deviceSummary']['entraJoined']} Entra-joined devices.  ",
             f"**Plan:** {len(plan_waves)} waves, first cutover {plan_waves[0]['date']}, last {last}.  ",
             f"**Findings:** {sev['critical']} critical, {sev['high']} high, {sev['medium']} medium.", "",
             "## Go / no-go position", ""]
    crit = [f for f in findings if f.severity == "critical"]
    lines.append(f"**NO-GO for wave 1 until {len(crit)} critical findings have an owner and a dated fix.**" if crit else "**GO.**")
    lines += ["", "## Critical findings (decisions needed from the steering committee)", "",
              "| ID | Subject | What breaks | Fix |", "|---|---|---|---|"]
    for f in crit:
        first = lambda t: t.split(". ")[0].rstrip(".")
        lines.append(f"| {f.id} | {f.subject} | {first(f.detail)}. | {first(f.remediation)}. |")
    if crossings:
        lines += ["", "## Licensing cliff", ""]
        for sku, (w, short) in crossings.items():
            lines.append(f"- **{sku}**: seats run out in **wave {w}**, short by **{short}** at that point.")
    lines += ["", "## Wave plan", "", "| Wave | Date | Users | Avg risk | Tier-1 apps | Entra devices | Gate |", "|---|---|---|---|---|---|---|"]
    for w in plan_waves:
        lines.append(f"| {w['label']} | {w['date']} | {w['size']} | {w['avgRisk']} | {w['tier1Apps']} | {w['entraDevices']} | {w['gate']} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tcp")
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--config", default="config/plan.json")
    ap.add_argument("--out", default="reports")
    ap.add_argument("--no-png", action="store_true", help="skip matplotlib rendering")
    a = ap.parse_args(argv)

    src, tgt, cfg = load(a.source), load(a.target), load(a.config)
    findings = checks.run_all(src, tgt)
    plan_waves = wv.plan(src, cfg)
    headroom = {l["sku"]: l["purchased"] - l["assigned"] for l in tgt["licenses"]}
    crossings = wv.license_crossing(plan_waves, headroom)
    for sku, (w, short) in crossings.items():
        for f in findings:
            if f.id == "LIC-002" and f.subject == sku:
                f.detail += f" Seats are exhausted during wave {w}."

    members = [u for u in src["users"] if u["userType"] == "Member"]
    ctx = dict(src_name=src["tenant"]["name"], tgt_name=tgt["tenant"]["name"], src_users=len(src["users"]),
               src_members=len(members), tgt_users=len(tgt["users"]), src_synced=sum(u["onPremisesSyncEnabled"] for u in members),
               merges=len({u["employeeId"] for u in members if u.get("employeeId")} & {u["employeeId"] for u in tgt["users"] if u.get("employeeId")}),
               src_apps=len(src["apps"]), src_tier1=sum(x["criticality"] == "tier1" for x in src["apps"]))

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "findings.json").write_text(json.dumps([f.to_dict() for f in findings], indent=1))
    write_csv(out / "findings.csv", ["id", "severity", "category", "subject", "count", "detail", "remediation"],
              [[f.id, f.severity, f.category, f.subject, f.count, f.detail, f.remediation] for f in findings])
    write_csv(out / "wave-plan.csv", ["wave", "date", "size", "avgRisk", "maxRisk", "tier1Apps", "entraDevices", "departments", "gate"],
              [[w["wave"], w["date"], w["size"], w["avgRisk"], w["maxRisk"], w["tier1Apps"], w["entraDevices"],
                "; ".join(f"{k}:{v}" for k, v in w["departments"].items()), w["gate"]] for w in plan_waves])
    write_csv(out / "user-mapping.csv", ["sourceUpn", "targetUpn", "targetNickname", "action", "wave", "riskScore"],
              build_mapping(src, tgt, plan_waves))
    (out / "executive-summary.md").write_text(summary_md(src, tgt, findings, plan_waves, crossings, ctx), encoding="utf-8")
    if not a.no_png:
        diagrams.write_all(out / "diagrams", ctx, src, tgt, findings, plan_waves, cfg)
    crit = sum(f.severity == "critical" for f in findings)
    print(f"{len(findings)} findings ({crit} critical) | {len(plan_waves)} waves | reports in {out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
