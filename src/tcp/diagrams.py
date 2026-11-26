"""Render diagrams from analysis results.

PNGs (matplotlib, no extra deps beyond matplotlib) and Mermaid text that GitHub renders natively.
"""
import datetime as dt
import pathlib
from collections import Counter, defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from .checks import CONTROLS, ca_matrix

NAVY, BLUE, TEAL, AMBER, RED, GREEN, GREY, LIGHT = "#12263f", "#2b6cb0", "#1a9e8f", "#d99a1c", "#c0392b", "#2f855a", "#6b7280", "#eef2f7"
SEV_COLOR = {"critical": RED, "high": AMBER, "medium": BLUE, "info": GREY}


def _box(ax, x, y, w, h, text, fc=LIGHT, ec=NAVY, tc=NAVY, fs=9, bold=False, lw=1.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc,
            fontweight="bold" if bold else "normal", linespacing=1.25)


def _arrow(ax, p, q, color=NAVY, style="-|>", ls="-", lw=1.5, rad=0.0, label=None, lx=0, ly=0.12):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=13, color=color, lw=lw, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text((p[0] + q[0]) / 2 + lx, (p[1] + q[1]) / 2 + ly, label, ha="center", fontsize=7.5, color=color, style="italic")


def _canvas(w, h, title, sub=None):
    fig, ax = plt.subplots(figsize=(w, h), dpi=150)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    ax.text(0.3, h - 0.35, title, fontsize=15, fontweight="bold", color=NAVY, va="top")
    if sub:
        ax.text(0.3, h - 0.8, sub, fontsize=9, color=GREY, va="top")
    return fig, ax


def _save(fig, path):
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# --------------------------------------------------------------------------- architecture
def render_architecture(out, ctx):
    fig, ax = _canvas(16, 9.2, "Entra ID tenant consolidation: from two estates to one",
                      f"{ctx['src_name']} ({ctx['src_users']} users)  ->  {ctx['tgt_name']} ({ctx['tgt_users']} users).  Generated from the analysis of the exported tenant data.")
    # AS-IS
    ax.text(0.5, 7.7, "AS-IS: two tenants, two trust boundaries", fontsize=11, fontweight="bold", color=RED)
    ax.add_patch(FancyBboxPatch((0.4, 4.2), 3.6, 3.3, boxstyle="round,pad=0.02,rounding_size=0.1", fc="#fdf2f0", ec=RED, lw=1.6, ls="--"))
    ax.text(2.2, 7.25, f"{ctx['src_name']} tenant", ha="center", fontsize=10, fontweight="bold", color=RED)
    _box(ax, 0.65, 6.15, 3.1, 0.7, f"{ctx['src_users']} users\n(AD-synced {ctx['src_synced']})", fs=8.5)
    _box(ax, 0.65, 5.25, 3.1, 0.7, f"{ctx['src_apps']} single-tenant apps\n({ctx['src_tier1']} tier-1)", fs=8.5)
    _box(ax, 0.65, 4.4, 3.1, 0.7, "9 CA policies  |  federated domain", fs=8.5)
    ax.add_patch(FancyBboxPatch((0.4, 0.6), 3.6, 3.1, boxstyle="round,pad=0.02,rounding_size=0.1", fc="#f1f6fd", ec=BLUE, lw=1.6, ls="--"))
    ax.text(2.2, 3.45, f"{ctx['tgt_name']} tenant", ha="center", fontsize=10, fontweight="bold", color=BLUE)
    _box(ax, 0.65, 2.45, 3.1, 0.7, f"{ctx['tgt_users']} users", fs=8.5)
    _box(ax, 0.65, 1.55, 3.1, 0.7, "6 CA policies  |  E3-heavy", fs=8.5)
    _box(ax, 0.65, 0.75, 3.1, 0.6, "Shared mail domain collision", fs=8.5, ec=RED, tc=RED)
    _arrow(ax, (2.2, 4.2), (2.2, 3.7), RED, style="<|-|>", ls="--", label="no trust", lx=0.55)

    # TRANSITION
    ax.text(5.1, 7.7, "TRANSITION: coexistence engine", fontsize=11, fontweight="bold", color=AMBER)
    ax.add_patch(FancyBboxPatch((4.7, 0.6), 6.3, 6.9, boxstyle="round,pad=0.02,rounding_size=0.12", fc="#fffaf0", ec=AMBER, lw=1.6))
    steps = [("1  Cross-tenant access policy", "inbound MFA + device trust, auto-redeem", 6.35),
             ("2  Cross-tenant sync (B2B members)", "attribute mapping, scoped by wave group", 5.35),
             ("3  Domain + mail coexistence", "shared address space, mailbox moves", 4.35),
             ("4  App re-registration factory", "SAML/OIDC pipeline from IaC templates", 3.35),
             ("5  Device re-provisioning", "Autopilot reset + Intune re-enrol", 2.35),
             ("6  Wave controller + rollback", "gates, freeze calendar, hypercare", 1.35)]
    for t, s, y in steps:
        _box(ax, 5.0, y - 0.35, 5.7, 0.8, f"{t}\n{s}", fc="white", ec=AMBER, fs=8.5)
    for (_, _, y1), (_, _, y2) in zip(steps, steps[1:]):
        _arrow(ax, (7.85, y1 - 0.38), (7.85, y2 + 0.48), AMBER, lw=1.2)
    _arrow(ax, (4.0, 6.2), (5.0, 6.2), RED, rad=0.0)
    _arrow(ax, (4.0, 2.7), (5.0, 5.3), BLUE, rad=0.15)

    # TO-BE
    ax.text(11.6, 7.7, "TO-BE: one tenant, one control plane", fontsize=11, fontweight="bold", color=GREEN)
    ax.add_patch(FancyBboxPatch((11.4, 0.6), 4.2, 6.9, boxstyle="round,pad=0.02,rounding_size=0.12", fc="#f0faf4", ec=GREEN, lw=2))
    ax.text(13.5, 7.25, f"{ctx['tgt_name']} (surviving tenant)", ha="center", fontsize=10, fontweight="bold", color=GREEN)
    blocks = [("Unified identity: " + f"{ctx['tgt_users'] + ctx['src_members'] - ctx['merges']:,}" + " people", 6.2),
              ("Conditional Access parity + PIM", 5.2), ("App catalog: re-registered, cert-rolled", 4.2),
              ("Entitlement mgmt + access reviews", 3.2), ("Devices: Autopilot + Intune", 2.2),
              ("Defender XDR + Sentinel: one SOC view", 1.2)]
    for t, y in blocks:
        _box(ax, 11.7, y - 0.3, 3.6, 0.7, t, fc="white", ec=GREEN, fs=8.5)
    _arrow(ax, (11.0, 4.0), (11.4, 4.0), GREEN, lw=2.2)

    ax.text(0.3, 0.15, "Legend:  red dashed = trust boundary / risk   amber = migration tooling   green = end state", fontsize=8, color=GREY)
    _save(fig, out)


# --------------------------------------------------------------------------- waves gantt
def render_waves(out, waves, freezes):
    fig, ax = plt.subplots(figsize=(14, 6.2), dpi=150)
    start = min(w["date"] for w in waves) - dt.timedelta(days=7)
    end = max(w["date"] for w in waves) + dt.timedelta(days=21)
    for f in freezes:
        a, b = dt.date.fromisoformat(f["start"]), dt.date.fromisoformat(f["end"])
        if b >= start and a <= end:
            ax.axvspan(a, b, color=RED, alpha=.12)
            ax.text(a + dt.timedelta(days=1), -0.75, f["name"], fontsize=8, color=RED, fontweight="bold")
    for i, w in enumerate(waves):
        y = len(waves) - 1 - i
        c = GREEN if w["wave"] == 0 else (BLUE if w["avgRisk"] < 40 else AMBER if w["avgRisk"] < 55 else RED)
        ax.barh(y, 5, left=w["date"], color=c, height=.55)
        ax.barh(y, 10, left=w["date"] + dt.timedelta(days=5), color=c, alpha=.25, height=.55)
        ax.text(w["date"] + dt.timedelta(days=16), y, f"{w['size']} users  |  risk {w['avgRisk']}  |  {w['tier1Apps']} tier-1 apps",
                va="center", fontsize=8, color=NAVY)
    ax.set_yticks(range(len(waves)))
    ax.set_yticklabels([f"{w['label']}  ({', '.join(list(w['departments'])[:2])}{'...' if len(w['departments']) > 2 else ''})"
                        for w in reversed(waves)], fontsize=8.5)
    ax.set_xlim(start, end)
    ax.set_ylim(-0.95, len(waves) - 0.4)
    ax.set_title("Cutover wave plan (solid = cutover week, light = hypercare). Red bands = freeze windows", loc="left", fontsize=12,
                 fontweight="bold", color=NAVY, pad=12)
    ax.grid(axis="x", alpha=.25)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.autofmt_xdate()
    _save(fig, out)


# --------------------------------------------------------------------------- risk heatmap
def render_risk_heatmap(out, src, cfg):
    import numpy as np
    depts = sorted({u["department"] for u in src["users"] if u["userType"] == "Member"})
    factors = ["Privileged", "AD-synced", "Tier-1 apps", "Entra-joined device", "No MFA"]
    M = []
    for d in depts:
        us = [u for u in src["users"] if u["userType"] == "Member" and u["department"] == d]
        tier1 = {a["appId"] for a in src["apps"] if a["criticality"] == "tier1"}
        M.append([100 * sum(bool(u["privilegedRoles"]) for u in us) / len(us),
                  100 * sum(u["onPremisesSyncEnabled"] for u in us) / len(us),
                  100 * sum(bool(set(u["apps"]) & tier1) for u in us) / len(us),
                  100 * sum(bool(u["entraJoinedDevices"]) for u in us) / len(us),
                  100 * sum(not u["mfaRegistered"] for u in us) / len(us)])
    M = np.array(M)
    fig, ax = plt.subplots(figsize=(9, 6), dpi=150)
    im = ax.imshow(M, cmap="YlOrRd", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(factors)))
    ax.set_xticklabels(factors, fontsize=9)
    ax.set_yticks(range(len(depts)))
    ax.set_yticklabels(depts, fontsize=9)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            ax.text(j, i, f"{M[i, j]:.0f}%", ha="center", va="center", fontsize=8.5, color="white" if M[i, j] > 60 else NAVY)
    ax.set_title("Where the migration risk lives: % of each department exposed", loc="left", fontsize=12, fontweight="bold", color=NAVY)
    fig.colorbar(im, ax=ax, fraction=.03)
    _save(fig, out)


# --------------------------------------------------------------------------- CA parity
def render_ca_matrix(out, src, tgt):
    ms, mt = ca_matrix(src), ca_matrix(tgt)
    col = {"enforced": GREEN, "report-only": AMBER, "none": RED, "off": RED}
    fig, ax = _canvas(11, 6.4, "Conditional Access parity: source vs target", "Controls the acquired bank enforces today, and whether the acquirer matches them.")
    ax.text(5.6, 5.15, src["tenant"]["name"], fontsize=10, fontweight="bold", color=NAVY, ha="center")
    ax.text(8.6, 5.15, tgt["tenant"]["name"], fontsize=10, fontweight="bold", color=NAVY, ha="center")
    for i, c in enumerate(CONTROLS):
        y = 4.55 - i * .55
        ax.text(0.4, y + .13, c, fontsize=9.5, color=NAVY, va="center")
        for x, m in ((5.6, ms), (8.6, mt)):
            st = m[c][0]
            _box(ax, x - 1.0, y - .1, 2.0, .45, st, fc=col[st], ec=col[st], tc="white", fs=8.5, bold=True)
        gap = {"none": 0, "off": 0, "report-only": 1, "enforced": 2}[ms[c][0]] > {"none": 0, "off": 0, "report-only": 1, "enforced": 2}[mt[c][0]]
        if gap:
            ax.text(10.0, y + .13, "GAP", color=RED, fontsize=9.5, fontweight="bold", va="center")
    _save(fig, out)


# --------------------------------------------------------------------------- findings overview
def render_findings(out, findings):
    cats = sorted({f.category for f in findings})
    sevs = ["critical", "high", "medium"]
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    bottom = [0] * len(cats)
    for s in sevs:
        vals = [sum(1 for f in findings if f.category == c and f.severity == s) for c in cats]
        ax.bar(cats, vals, bottom=bottom, color=SEV_COLOR[s], label=s)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_title("Findings by category and severity", loc="left", fontsize=12, fontweight="bold", color=NAVY)
    ax.legend(frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    plt.xticks(rotation=25, ha="right")
    _save(fig, out)


# --------------------------------------------------------------------------- Mermaid
def mermaid_wave_gantt(waves, freezes):
    lines = ["```mermaid", "gantt", "    title Cutover waves and freeze windows", "    dateFormat YYYY-MM-DD", "    axisFormat %d %b", "    section Freeze"]
    for f in freezes:
        lines.append(f"    {f['name']} :crit, {f['start']}, {f['end']}")
    lines.append("    section Waves")
    for w in waves:
        d = w["date"]
        lines.append(f"    {w['label']} ({w['size']} users) :{'done,' if w['wave'] == 0 else ''}w{w['wave']}, {d}, 3d")
        lines.append(f"    Hypercare W{w['wave']} :after w{w['wave']}, 7d")
    lines.append("```")
    return "\n".join(lines)


def mermaid_app_dependencies(src):
    tier = {"tier1": ":::t1", "tier2": ":::t2", "tier3": ":::t3"}
    cnt = defaultdict(int)
    for u in src["users"]:
        for a in u["apps"]:
            cnt[a] += 1
    lines = ["```mermaid", "flowchart LR", "    classDef t1 fill:#fde8e6,stroke:#c0392b,color:#12263f",
             "    classDef t2 fill:#fff4d6,stroke:#d99a1c,color:#12263f", "    classDef t3 fill:#e8f1fb,stroke:#2b6cb0,color:#12263f"]
    depts = sorted({d for a in src["apps"] for d in a["assignedDepartments"]})
    for i, d in enumerate(depts):
        lines.append(f"    D{i}[\"{d}\"]")
    for j, a in enumerate(src["apps"]):
        shape = "{{" if a["protocol"] == "saml" else "([" if a["protocol"] == "oidc" else "[["
        close = "}}" if a["protocol"] == "saml" else "])" if a["protocol"] == "oidc" else "]]"
        lines.append(f"    A{j}{shape}\"{a['displayName']}<br/>{cnt[a['appId']]} users\"{close}{tier[a['criticality']]}")
        if len(a["assignedDepartments"]) < len(depts):
            for d in a["assignedDepartments"]:
                lines.append(f"    D{depts.index(d)} --> A{j}")
    lines.append("```")
    return "\n".join(lines)


def mermaid_findings_pie(findings):
    c = Counter(f.severity for f in findings)
    return "```mermaid\npie showData title Findings by severity\n" + "\n".join(f'    "{k}" : {c[k]}' for k in ("critical", "high", "medium") if c[k]) + "\n```"


def write_all(outdir, ctx, src, tgt, findings, waves, cfg):
    out = pathlib.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    render_architecture(out / "01-architecture.png", ctx)
    render_waves(out / "02-wave-plan.png", waves, cfg["freezeWindows"])
    render_risk_heatmap(out / "03-risk-heatmap.png", src, cfg)
    render_ca_matrix(out / "04-ca-parity.png", src, tgt)
    render_findings(out / "05-findings.png", findings)
    (out / "wave-gantt.mmd.md").write_text(mermaid_wave_gantt(waves, cfg["freezeWindows"]) + "\n")
    (out / "app-dependencies.mmd.md").write_text(mermaid_app_dependencies(src) + "\n")
    (out / "findings-pie.mmd.md").write_text(mermaid_findings_pie(findings) + "\n")
