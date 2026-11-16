"""AccessLab network v1: reproducible proof-of-concept from user-supplied CSVs.

Insurance+capacity baseline is independent of artificial population coordinates.
Illustrative travel scenario uses artificial tract points and is NOT geographic evidence.
Flows are fractional expected people/year, not observed appointments.
"""
from pathlib import Path
import argparse, json
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

INSURANCE = {'Medicaid':'accepts_medicaid','Medicare':'accepts_medicare',
             'Private/other':'accepts_private','Uninsured':'accepts_uninsured'}

def solve_flow(demand,capacity,edges, n_origins, n_providers):
    """Maximize total served first, then minimize per-unit access cost (0..100).
    A cost of -1000 + access cost guarantees each added served unit is preferred.
    """
    if len(edges)==0:
        return np.zeros(0), None
    r=np.concatenate([edges.origin_idx.to_numpy(),n_origins+edges.provider_idx.to_numpy()])
    c=np.concatenate([np.arange(len(edges)),np.arange(len(edges))])
    A=coo_matrix((np.ones(len(r)),(r,c)),shape=(n_origins+n_providers,len(edges))).tocsr()
    res=linprog(-1000+edges.access_cost.to_numpy(), A_ub=A,
                b_ub=np.r_[demand,capacity], bounds=(0,None), method='highs')
    if not res.success: raise RuntimeError(res.message)
    return res.x,res

def haversine_km(lat1,lon1,lat2,lon2):
    r1,r2=np.radians(lat1),np.radians(lat2)
    dlat=r2-r1; dlon=np.radians(lon2-lon1)
    a=np.sin(dlat/2)**2+np.cos(r1)*np.cos(r2)*np.sin(dlon/2)**2
    return 6371*2*np.arcsin(np.sqrt(np.clip(a,0,1)))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cohorts',default='synthetic_cohorts.csv')
    ap.add_argument('--providers',default='providers.csv')
    ap.add_argument('--output',default='outputs')
    args=ap.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    B=pd.read_csv(args.cohorts,dtype={'tract_geoid':str,'cohort_id':str})
    H=pd.read_csv(args.providers,dtype={'provider_id':str})
    assert B.cohort_id.is_unique and H.provider_id.is_unique
    assert set(B.insurance_type)==set(INSURANCE)
    assert B.estimated_demand.ge(0).all() and H.annual_new_patient_capacity.ge(0).all()
    assert B.demand_period.eq('annual').all()
    assert B.coordinates_are_synthetic.astype(str).str.lower().eq('true').all(), 'Revisit travel caveat for new coordinates'
    # Model only 2 transportation modes; age categories are combined because eligibility is age-agnostic (all adults).
    cols=['tract_geoid','insurance_type','transport_access','origin_latitude','origin_longitude']
    O=B.groupby(cols,as_index=False).agg(demand=('estimated_demand','sum'),population_weight=('population_weight','sum'))
    O=O[O.demand>0].reset_index(drop=True)
    O['origin_idx']=np.arange(len(O))
    H=H.reset_index(drop=True).copy();H['provider_idx']=np.arange(len(H))
    capacity=H.annual_new_patient_capacity.to_numpy(dtype=float)
    demand=O.demand.to_numpy(dtype=float)
    # Scenario 1: insurance + capacity, no travel restrictions; 4 insurance origins.
    ins_groups=B.groupby('insurance_type',as_index=False).agg(demand=('estimated_demand','sum'))
    ins_groups['origin_idx']=np.arange(len(ins_groups))
    e0=[]
    for o in ins_groups.itertuples():
        for h in H.itertuples():
            if getattr(h,INSURANCE[o.insurance_type])==1:
                e0.append((o.origin_idx,h.provider_idx,min(100,2*h.wait_days)*0.4))
    E0=pd.DataFrame(e0,columns=['origin_idx','provider_idx','access_cost'])
    x0,_=solve_flow(ins_groups.demand.to_numpy(),capacity,E0,len(ins_groups),len(H))
    E0['assigned']=x0
    insurance_alloc=E0.groupby('origin_idx',as_index=False).assigned.sum().merge(ins_groups[['origin_idx','insurance_type','demand']],on='origin_idx')
    insurance_alloc['unserved']=np.maximum(0,insurance_alloc.demand-insurance_alloc.assigned)
    insurance_alloc.to_csv(out/'insurance_only_by_group.csv',index=False)
    # Simple intervention experiments under insurance-only constraints; no geographic claims.
    intervention_rows=[]
    for label,cap_multiplier,expand_uninsured in [
        ('baseline',1.0,False),('20pct_more_capacity',1.2,False),
        ('uninsured_accepted_everywhere',1.0,True),
        ('capacity_plus_uninsured_expansion',1.2,True)]:
        if expand_uninsured:
            extra=[(o.origin_idx,h.provider_idx,min(100,2*h.wait_days)*.4)
                   for o in ins_groups.itertuples() if o.insurance_type=='Uninsured'
                   for h in H.itertuples() if getattr(h,'accepts_uninsured')==0]
            e_alt=pd.concat([E0[['origin_idx','provider_idx','access_cost']],pd.DataFrame(extra,columns=['origin_idx','provider_idx','access_cost'])],ignore_index=True)
        else:
            e_alt=E0[['origin_idx','provider_idx','access_cost']]
        alloc,_=solve_flow(ins_groups.demand.to_numpy(),capacity*cap_multiplier,e_alt,len(ins_groups),len(H))
        intervention_rows.append({'scenario':label,'assigned':round(float(alloc.sum()),3),
            'unserved':round(float(demand.sum()-alloc.sum()),3),
            'coverage_rate':round(float(alloc.sum()/demand.sum()),5),
            'capacity_slots':round(float(capacity.sum()*cap_multiplier),1)})
    pd.DataFrame(intervention_rows).to_csv(out/'intervention_comparison_insurance_only.csv',index=False)
    # Scenario 2: synthetic coordinate-based travel (NOT observed Philly routing).
    # driving = 8 min + great-circle km / 30 km/h; no vehicle = 12 min + km / 15 km/h
    # Both are illustrative impedance functions; travel cutoff 45 min for car, 60 for no vehicle.
    lat_o=O.origin_latitude.to_numpy()[:,None];lon_o=O.origin_longitude.to_numpy()[:,None]
    lat_h=H.latitude.to_numpy()[None,:];lon_h=H.longitude.to_numpy()[None,:]
    km=haversine_km(lat_o,lon_o,lat_h,lon_h)
    has_vehicle=O.transport_access.eq('Vehicle access').to_numpy()[:,None]
    travel=np.where(has_vehicle,8+km*2,12+km*4)
    max_travel=np.where(has_vehicle,45,60)
    eligibility=np.zeros((len(O),len(H)),dtype=bool)
    for ins,col in INSURANCE.items():
        eligibility[O.insurance_type.eq(ins).to_numpy(),:]=H[col].eq(1).to_numpy()
    feasible=eligibility & (travel<=max_travel)
    oi,pj=np.where(feasible)
    costs=.6*np.minimum(100,2*travel[oi,pj])+.4*np.minimum(100,2*H.wait_days.to_numpy()[pj])
    E=pd.DataFrame({'origin_idx':oi,'provider_idx':pj,'travel_minutes_synthetic':np.round(travel[oi,pj],3),'access_cost':np.round(costs,5)})
    E['access_score']=np.round(100-E.access_cost,5)
    x,_=solve_flow(demand,capacity,E,len(O),len(H))
    E['assigned_expected_patients']=np.round(x,8)
    E['tract_geoid']=O.tract_geoid.to_numpy()[oi]
    E['insurance_type']=O.insurance_type.to_numpy()[oi]
    E['transport_access']=O.transport_access.to_numpy()[oi]
    E['provider_id']=H.provider_id.to_numpy()[pj]
    E.to_csv(out/'feasible_edges_synthetic_travel.csv',index=False)
    A=E.groupby('origin_idx').agg(assigned=('assigned_expected_patients','sum'),feasible_providers=('provider_idx','count'),best_access_score=('access_score','max')).reindex(np.arange(len(O)),fill_value=0)
    O['assigned_expected_patients']=A.assigned.to_numpy()
    O['unserved_expected_patients']=np.maximum(0,O.demand-O.assigned_expected_patients)
    O['feasible_provider_count']=A.feasible_providers.to_numpy().astype(int)
    O['best_access_score']=A.best_access_score.to_numpy()
    O.to_csv(out/'cohort_network_results.csv',index=False)
    P=E.groupby('provider_idx').assigned_expected_patients.sum().reindex(np.arange(len(H)),fill_value=0)
    H['assigned_expected_patients']=P.to_numpy()
    H['unused_capacity']=np.maximum(0,H.annual_new_patient_capacity-H.assigned_expected_patients)
    H.to_csv(out/'provider_network_results.csv',index=False)
    group=O.groupby(['insurance_type','transport_access'],as_index=False).agg(demand=('demand','sum'),assigned=('assigned_expected_patients','sum'),unserved=('unserved_expected_patients','sum'),isolated_origins=('feasible_provider_count',lambda s:int((s==0).sum())))
    group['coverage_rate']=group.assigned/group.demand
    group.to_csv(out/'coverage_by_group.csv',index=False)
    insurance_eligibility=eligibility.sum(axis=1)
    metrics={
        'inputs':{'cohorts':len(B),'aggregated_origins':len(O),'providers':len(H),'annual_demand_expected_patients':round(float(demand.sum()),3),'annual_new_patient_capacity':int(capacity.sum())},
        'insurance_only':{'served':round(float(x0.sum()),3),'unserved':round(float(demand.sum()-x0.sum()),3),'coverage_rate':round(float(x0.sum()/demand.sum()),5),'eligible_edges':len(E0)},
        'illustrative_travel':{'served':round(float(x.sum()),3),'unserved':round(float(demand.sum()-x.sum()),3),'coverage_rate':round(float(x.sum()/demand.sum()),5),'feasible_edges':len(E),'origins_without_eligible_insurance_provider':int((insurance_eligibility==0).sum()),'origins_without_feasible_provider_after_travel':int((O.feasible_provider_count==0).sum()),'provider_unused_capacity':round(float(H.unused_capacity.sum()),3)},
        'warnings':['Provider capacity, wait time, and insurance acceptance are synthetic.', 'Population origin coordinates are fictional demo points, not real Census tract coordinates.', 'Travel is calculated from artificial coordinates using illustrative speed formulas; results cannot be interpreted as Philadelphia travel times.', 'Provider sample of 77 source records is not a complete census of city outpatient mental health capacity.', 'Cohort demand is fractional expected patients/year and estimated from assumed care-seeking rates.', 'Assignments are mathematical allocations, not actual appointments.', 'Insurance-only and illustrative-travel objectives both maximize served before minimizing modeled access cost.']
    }
    (out/'summary.json').write_text(json.dumps(metrics,indent=2))
    assert np.all(O.assigned_expected_patients.to_numpy()<=demand+1e-4)
    assert np.all(H.assigned_expected_patients.to_numpy()<=capacity+1e-4)
    assert x.sum()<=x0.sum()+1e-3
    assert abs(H.assigned_expected_patients.sum()-O.assigned_expected_patients.sum())<1e-3
    print(json.dumps(metrics,indent=2))
    print('\nBy group:\n',group.to_string(index=False))

if __name__=='__main__':main()
