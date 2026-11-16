import sys, unittest
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from build_v2 import wait_attendance,travel_factor,solve,build_edges,max_min_equity
class ModelTests(unittest.TestCase):
    def setUp(self):
        self.O=pd.DataFrame({'insurance_type':['Medicaid','Uninsured'],'transport_access':['Vehicle access','No household vehicle'],'demand':[8.,8.]})
        self.H=pd.DataFrame({'accepts_medicaid':[1,1],'accepts_medicare':[0,0],'accepts_private':[0,0],'accepts_uninsured':[1,0],'wait_days':[7,30],'annual_new_patient_capacity':[5.,5.]})
    def test_odds_reference(self):self.assertAlmostEqual(float(wait_attendance(7)),.91)
    def test_odds_decreasing(self):self.assertTrue(np.all(np.diff(wait_attendance(np.array([7,14,30,90])))<0))
    def test_piecewise_anchors(self):np.testing.assert_allclose(wait_attendance([7,30,90],'piecewise'),[.91,.714,.64])
    def test_travel_factor(self):self.assertAlmostEqual(float(travel_factor(60)),.5)
    def test_flow_constraints(self):
        E=build_edges(self.O,self.H);x,served,ok=solve(self.O.demand.to_numpy(),self.H.annual_new_patient_capacity.to_numpy(),E)
        self.assertTrue(ok);self.assertAlmostEqual(served,10.)
        self.assertTrue((np.bincount(E.oi,weights=x,minlength=2)<=self.O.demand.to_numpy()+1e-5).all())
        self.assertTrue((np.bincount(E.pj,weights=x,minlength=2)<=self.H.annual_new_patient_capacity.to_numpy()+1e-5).all())
    def test_ineligible_edge_absent(self):
        E=build_edges(self.O,self.H);self.assertFalse(((E.oi==1)&(E.pj==1)).any())
    def test_capacity_monotonic(self):
        E=build_edges(self.O,self.H);_,s,_=solve(self.O.demand.to_numpy(),self.H.annual_new_patient_capacity.to_numpy(),E)
        _,s2,_=solve(self.O.demand.to_numpy(),self.H.annual_new_patient_capacity.to_numpy()*2,E)
        self.assertGreaterEqual(s2+1e-5,s)
    def test_equity_constraints(self):
        E=build_edges(self.O,self.H);z,x=max_min_equity(self.O,self.H,E)
        self.assertAlmostEqual(z,10/16,places=4)
        served=np.bincount(E.oi,weights=x,minlength=2)
        self.assertTrue((served/self.O.demand.to_numpy()>=z-1e-4).all())
    def test_expanded_eligibility(self):
        E=build_edges(self.O,self.H,uninsured_expansion=True)
        self.assertTrue(((E.oi==1)&(E.pj==1)).any())
if __name__=='__main__':unittest.main()
