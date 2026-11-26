import json, pathlib, sys, unittest, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tcp import checks, waves  # noqa: E402

def load(n): return json.loads((ROOT / "data/sample" / n).read_text())

class AnalyzerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src, cls.tgt = load("source-tenant.json"), load("target-tenant.json")
        cls.cfg = json.loads((ROOT / "config/plan.json").read_text())
        cls.findings = checks.run_all(cls.src, cls.tgt)

    def ids(self): return {f.id for f in self.findings}

    def test_planted_conflicts_are_detected(self):
        for fid in ("DOM-001", "DOM-002", "USR-001", "USR-002", "USR-003", "APP-001", "APP-003", "CA-001", "LIC-002", "DEV-001"):
            self.assertIn(fid, self.ids())

    def test_domain_collision_is_critical(self):
        f = [x for x in self.findings if x.id == "DOM-001"][0]
        self.assertEqual((f.severity, f.subject), ("critical", "contoso-legacy.example"))

    def test_every_member_lands_in_exactly_one_wave(self):
        w = waves.plan(json.loads(json.dumps(self.src)), self.cfg)
        ids = [u["id"] for x in w for u in x["users"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), sum(u["userType"] == "Member" for u in self.src["users"]))

    def test_no_cutover_inside_freeze_window(self):
        w = waves.plan(json.loads(json.dumps(self.src)), self.cfg)
        fr = [(dt.date.fromisoformat(f["start"]), dt.date.fromisoformat(f["end"])) for f in self.cfg["freezeWindows"]]
        for x in w:
            self.assertFalse(any(a <= x["date"] <= b for a, b in fr), x["date"])
            self.assertEqual(x["date"].weekday(), self.cfg["cutoverWeekday"])

    def test_pilot_is_lowest_risk_and_first(self):
        w = waves.plan(json.loads(json.dumps(self.src)), self.cfg)
        self.assertEqual(w[0]["label"], "Pilot")
        self.assertLess(w[0]["avgRisk"], min(x["avgRisk"] for x in w[1:]))

    def test_wave_size_cap(self):
        w = waves.plan(json.loads(json.dumps(self.src)), self.cfg)
        self.assertTrue(all(x["size"] <= self.cfg["maxWaveSize"] for x in w))

    def test_clean_tenants_have_no_critical_findings(self):
        clean_src = json.loads(json.dumps(self.src)); clean_tgt = json.loads(json.dumps(self.tgt))
        clean_src["domains"] = [d for d in clean_src["domains"] if d["name"] != "contoso-legacy.example"]
        clean_src["apps"] = []
        clean_src["conditionalAccess"] = []
        for u in clean_src["users"]: u["privilegedRoles"] = []
        clean_tgt["users"] = [u for u in clean_tgt["users"] if not (set(p.lower() for p in u["proxyAddresses"]) & {"smtp:helpdesk@shared-legacy.example"})]
        crit = [f for f in checks.run_all(clean_src, clean_tgt) if f.severity == "critical" and f.id != "USR-003"]
        self.assertEqual(crit, [])

if __name__ == "__main__":
    unittest.main()
