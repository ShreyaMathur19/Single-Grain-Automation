import csv
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from main import rules, budget_value, run
from verification import verify

ROOT=Path(__file__).resolve().parents[1]
class TriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT/'fixtures/inbound_leads.csv').open(encoding='utf-8',newline='') as f:
            cls.rows=list(csv.DictReader(f))
        cls.lookup={r['lead_id']:r for r in cls.rows}

    def test_budget_variants(self):
        self.assertEqual(budget_value('15k'),15000)
        self.assertEqual(budget_value('25,000'),25000)
        self.assertIsNone(budget_value("we'll discuss"))

    def test_injection_is_not_executed(self):
        r=rules(self.lookup['L-006'],{})
        self.assertEqual(r['decision'],'REJECT')
        self.assertIn('prompt_injection',r['flags'])

    def test_low_or_unknown_budget_is_nurture(self):
        for id in ('L-005','L-014'):
            self.assertEqual(rules(self.lookup[id],{})['decision'],'NURTURE')

    def test_conflicting_enterprise_budget_escalates(self):
        self.assertEqual(rules(self.lookup['L-007'],{})['decision'],'ESCALATE')

    def test_privacy_and_executable(self):
        for id in ('L-019','L-020'):
            self.assertEqual(rules(self.lookup[id],{})['decision'],'ESCALATE')

    def test_malformed_date(self):
        self.assertEqual(rules(self.lookup['L-012'],{})['decision'],'ESCALATE')

    def test_html_and_spanish_intent(self):
        for id in ('L-009','L-016'):
            self.assertEqual(rules(self.lookup[id],{})['decision'],'QUALIFY')

    def test_repeat_contact_with_new_intent_not_silently_rejected(self):
        earlier={'marcus.lee.2027@stateuniv.edu':[self.lookup['L-002']]}
        self.assertEqual(rules(self.lookup['L-015'],earlier)['decision'],'NURTURE')

    def test_verification_reduces_noncritical_escalations(self):
        expectations = {'L-007':'NURTURE','L-012':'NURTURE','L-017':'NURTURE'}
        for lead_id, expected in expectations.items():
            row=self.lookup[lead_id]
            updated,audit=verify(row,rules(row,{}),{})
            self.assertEqual(updated['decision'],expected)
            self.assertFalse(audit['human_review_required'])
            self.assertNotEqual(audit['next_action'],'NONE')

    def test_security_and_privacy_remain_human_routed(self):
        for lead_id in ('L-019','L-020'):
            row=self.lookup[lead_id]
            updated,audit=verify(row,rules(row,{}),{})
            self.assertEqual(updated['decision'],'ESCALATE')
            self.assertTrue(audit['human_review_required'])

    def test_no_external_claims_for_missing_contact(self):
        row=self.lookup['L-004']
        updated,audit=verify(row,rules(row,{}),{})
        self.assertEqual(updated['decision'],'ESCALATE')
        self.assertEqual(audit['next_action'],'VERIFY_CONTACT_CHANNEL')
        self.assertTrue(any(c['check']=='contact' for c in audit['checks']))

    def test_all_rows_and_unique_ids(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'result.csv';log=Path(d)/'log.jsonl'
            run(ROOT/'fixtures/inbound_leads.csv',out,log,'rules')
            with out.open(encoding='utf-8',newline='') as f:
                results=list(csv.DictReader(f))
            self.assertEqual(len(results),len(self.rows))
            self.assertEqual({r['lead_id'] for r in results},{r['lead_id'] for r in self.rows})
            self.assertTrue(log.exists())
if __name__=='__main__': unittest.main()
