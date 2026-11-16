import unittest
import numpy as np
from engine import Model,wait_prob

class TestAccessLab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=Model()
        cls.base=cls.model.run({'travel_mode':'illustrative'})
    def test_inputs_and_baseline(self):
        self.assertEqual(len(self.model.p),77)
        self.assertEqual(len(self.model.tracts),391)
        self.assertEqual(len(self.model.c),3128)
        self.assertFalse(self.model.verified)
        self.assertAlmostEqual(self.base['metrics']['assigned'],32078,places=1)
    def test_conservation(self):
        r=self.base
        self.assertAlmostEqual(sum(f['assigned'] for f in r['flows']),r['metrics']['assigned'],delta=2)
        self.assertAlmostEqual(sum(p['assigned'] for p in r['providers']),r['metrics']['assigned'],delta=2)
        self.assertTrue(all(p['assigned']<=p['capacity']+.01 for p in r['providers']))
        self.assertTrue(all(t['assigned']<=t['demand']+.01 for t in r['tracts']))
    def test_attendance(self):
        self.assertTrue(np.all(np.diff(wait_prob(np.array([7,30,90])))<0))
        self.assertTrue(np.all(np.diff(wait_prob(np.array([7,30,90]),'piecewise'))<0))
    def test_geography_gate(self):
        with self.assertRaisesRegex(ValueError,'requires Census'):
            self.model.run({'travel_mode':'verified'})
    def test_capacity_expansion(self):
        result=self.model.run({'capacity_pct':20,'travel_mode':'illustrative'})
        self.assertGreater(result['metrics']['assigned'],self.base['metrics']['assigned'])
        self.assertAlmostEqual(result['metrics']['assigned'],38493.6,delta=1)
    def test_new_clinic(self):
        result=self.model.run({'new_provider':{'latitude':40.04,'longitude':-75.08,'capacity':500,'insurance':['Medicaid','Uninsured']}})
        self.assertEqual(len(result['providers']),78)
        self.assertGreater(result['metrics']['assigned'],self.base['metrics']['assigned'])
    def test_equity(self):
        result=self.model.run({'objective':'equity'})
        self.assertAlmostEqual(result['metrics']['assigned'],self.base['metrics']['assigned'],delta=.1)
        self.assertGreater(result['metrics']['min_group_coverage'],self.base['metrics']['min_group_coverage'])

if __name__=='__main__':unittest.main()
