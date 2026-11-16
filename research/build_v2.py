"""AccessLab research network v2. See docs/RESEARCH_METHODS.md before interpreting outputs.
All data synthetic or partially modeled. Real provider geocodes; fictional population origins.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, vstack, csr_matrix, hstack

INS={'Medicaid':'accepts_medicaid','Medicare':'accepts_medicare','Private/other':'accepts_private','Uninsured':'accepts_uninsured'}
OR_WEEK=.95
P7=.91 # 9% no show at 1 week from Zhang et al., external clinic; calibration assumption
TRAVEL_HALF_LIFE=60. # minutes, hypothetical

def wait_attendance(days, model='odds'):
    w=np.asarray(days,dtype=float)
    if model=='odds':
        logodds=np.log(P7/(1-P7)) + (w-7.)/7.*np.log(OR_WEEK)
        return 1/(1+np.exp(-np.clip(logodds,-60,60)))
    if model=='piecewise':
        # Zhang 2020 single clinic 9%, 28.6%, 36% no-show at 7, 30, 90 days
        # Interpolation in log-odds of ATTENDANCE; extrapolation flat beyond endpoints.
        anchors=np.array([7.,30.,90.]); attend=np.array([.91,.714,.64]); logits=np.log(attend/(1-attend))
        return 1/(1+np.exp(-np.interp(w,anchors,logits)))
    raise ValueError(model)

def travel_factor(minutes, half_life=TRAVEL_HALF_LIFE):
    return np.exp(-np.log(2)*np.asarray(minutes,dtype=float)/half_life)

def haversine_km(lat1,lon1,lat2,lon2):
    a=np.sin(np.radians(lat2-lat1)/2)**2 + np.cos(np.radians(lat1))*np.cos(np.radians(lat2))*np.sin(np.radians(lon2-lon1)/2)**2
    return 12742*np.arcsin(np.sqrt(np.clip(a,0,1)))

def make_matrix(edges, n_o, n_p):
    m=len(edges); k=np.arange(m)
    return coo_matrix((np.ones(2*m),(np.r_[edges.oi.to_numpy(),n_o+edges.pj.to_numpy()],np.r_[k,k])),shape=(n_o+n_p,m)).tocsr()

def solve(demand, capacity, edges, objective='wait', min_group_coverage=None, groups=None):
    """Two-stage LP: max assignments, then maximize expected completions.
    Optional min_group_coverage enforces all insurance groups at least that share.
    All assignments are continuous expected annual patients.
    """
    n_o=len(demand); n_p=len(capacity); m=len(edges)
    if m==0: return np.zeros(0),0.,False
    A=make_matrix(edges,n_o,n_p); b=np.r_[demand,capacity]
    extra=[]; extra_b=[]
    if min_group_coverage is not None:
        if groups is None: raise ValueError('groups needed')
        for g in sorted(set(groups)):
            ids=np.flatnonzero(np.asarray(groups)==g)
            idx=np.flatnonzero(np.isin(edges.oi.to_numpy(),ids))
            row=csr_matrix((-np.ones(len(idx)),(np.zeros(len(idx)),idx)),shape=(1,m))
            extra.append(row); extra_b.append(-float(min_group_coverage)*float(demand[ids].sum()))
    if extra:
        A=vstack([A,*extra],format='csr');b=np.r_[b,extra_b]
    first=linprog(-np.ones(m),A_ub=A,b_ub=b,bounds=(0,None),method='highs')
    if not first.success: return np.zeros(m),0.,False
    maxserved=float(first.x.sum())
    # Tolerance 1e-5 expected people; preserve coverage optimum
    served_constraint=csr_matrix((-np.ones(m),(np.zeros(m),np.arange(m))),shape=(1,m))
    A2=vstack([A,served_constraint],format='csr');b2=np.r_[b,-maxserved+1e-5]
    probs=edges.p_attend.to_numpy()
    second=linprog(-probs,A_ub=A2,b_ub=b2,bounds=(0,None),method='highs')
    if not second.success: raise RuntimeError('Second stage failed: '+second.message)
    return second.x,maxserved,True

def build_edges(O,H,mode='insurance',wait_model='odds',half_life=60,uninsured_expansion=False):
    oi=[];pj=[];tmins=[]
    # Only 8 insurance/vehicle groups for insurance-only; tract groups for illustrative travel.
    if mode=='insurance':
        for i,row in enumerate(O.itertuples(index=False)):
            for j,h in enumerate(H.itertuples(index=False)):
                ok=(getattr(h,INS[row.insurance_type])==1 or (uninsured_expansion and row.insurance_type=='Uninsured'))
                if ok: oi.append(i);pj.append(j);tmins.append(np.nan)
    elif mode=='synthetic_travel':
        lat_o=O.origin_latitude.to_numpy()[:,None];lon_o=O.origin_longitude.to_numpy()[:,None]
        lat_h=H.latitude.to_numpy()[None,:];lon_h=H.longitude.to_numpy()[None,:]
        km=haversine_km(lat_o,lon_o,lat_h,lon_h)
        vehicle=O.transport_access.eq('Vehicle access').to_numpy()[:,None]
        travel=np.where(vehicle,8+2*km,12+4*km)
        cutoff=np.where(vehicle,45,60)
        ok=np.zeros_like(travel,dtype=bool)
        for ins,col in INS.items():
            ok[O.insurance_type.eq(ins).to_numpy(),:]=H[col].eq(1).to_numpy()
        if uninsured_expansion:
            ok[O.insurance_type.eq('Uninsured').to_numpy(),:]=True
        oi,pj=np.where(ok & (travel<=cutoff));tmins=travel[oi,pj]
    else: raise ValueError(mode)
    E=pd.DataFrame({'oi':np.asarray(oi,dtype=int),'pj':np.asarray(pj,dtype=int),'travel_minutes':np.asarray(tmins,dtype=float)})
    E['p_wait']=wait_attendance(H.wait_days.to_numpy()[E.pj],wait_model)
    E['p_attend']=E.p_wait.to_numpy() if mode=='insurance' else E.p_wait.to_numpy()*travel_factor(E.travel_minutes.to_numpy(),half_life)
    return E

def group_summary(O,E,x):
    oserved=np.bincount(E.oi.to_numpy(),weights=x,minlength=len(O))
    out=O[['insurance_type','transport_access','demand']].copy();out['assigned']=oserved
    out['expected_completed']=np.bincount(E.oi.to_numpy(),weights=x*E.p_attend.to_numpy(),minlength=len(O))
    G=out.groupby(['insurance_type','transport_access'],as_index=False)[['demand','assigned','expected_completed']].sum()
    G['coverage']=G.assigned/G.demand
    G['completed_per_demand']=G.expected_completed/G.demand
    return G

def summarize(label,O,H,E,x, maxserved=None):
    demand=O.demand.sum();served=x.sum();completed=np.dot(x,E.p_attend)
    return {'scenario':label,'demand':round(float(demand),4),'assigned':round(float(served),4),'coverage':round(float(served/demand),6),'expected_completed':round(float(completed),4),'completed_per_demand':round(float(completed/demand),6),'expected_attendance_among_assigned':round(float(completed/served),6) if served else 0,'available_capacity':round(float(H.annual_new_patient_capacity.sum()),4),'feasible_edges':len(E)}

def max_min_equity(O,H,E, group_mode="insurance_transport"):
    """Max-min insurance coverage, subject to max total served, then maximize completion.
    z is optimized continuously. Returns z, assignments.
    """
    d=O.demand.to_numpy();c=H.annual_new_patient_capacity.to_numpy();n=len(O);m=len(E)
    base,served,success=solve(d,c,E)
    if not success:return 0,base
    A=make_matrix(E,n,len(H))
    groups=(O.insurance_type+" | "+O.transport_access).to_numpy() if group_mode=="insurance_transport" else O.insurance_type.to_numpy()
    unique=sorted(set(groups))
    rows=[];rhs=[]
    for g in unique:
        ids=np.flatnonzero(groups==g)
        idx=np.flatnonzero(np.isin(E.oi.to_numpy(),ids))
        # -sum_{edges from g} x + D_g*z <= 0
        row=csr_matrix((-np.ones(len(idx)),(np.zeros(len(idx)),idx)),shape=(1,m))
        rows.append(hstack([row,csr_matrix([[d[ids].sum()]])],format='csr'));rhs.append(0.)
    main=hstack([A,csr_matrix((n+len(H),1))],format='csr')
    total=csr_matrix((np.r_[-np.ones(m),0.],(np.zeros(m+1),np.arange(m+1))),shape=(1,m+1))
    AA=vstack([main,*rows,total],format='csr');bb=np.r_[d,c,rhs,-served+1e-5]
    obj=np.r_[np.zeros(m),-1.]
    sol=linprog(obj,A_ub=AA,b_ub=bb,bounds=[(0,None)]*m+[(0,1)],method='highs')
    if not sol.success:raise RuntimeError('Equity LP failed '+sol.message)
    z=float(sol.x[-1]);
    # maximize expected completed while enforcing optimal min coverage, total served max
    xe,_,ok=solve(d,c,E,min_group_coverage=max(0,z-1e-6),groups=groups)
    if not ok: raise RuntimeError('Equity second-stage LP infeasible')
    return z,xe

def availability_experiments(O,H,output,reps=80,seed=20261111):
    """Provider-wide Bernoulli scenario; not inferred from JAMA's Medicaid clinician-specific result."""
    rng=np.random.default_rng(seed);rows=[]
    for prob in [.5,.75,.9]:
        for r in range(reps):
            h=H.copy();h['annual_new_patient_capacity']=np.where(rng.random(len(h))<prob,h.annual_new_patient_capacity,0)
            e=build_edges(O,h,'insurance')
            # Skip zero-capacity edges for speed
            e=e[h.annual_new_patient_capacity.to_numpy()[e.pj.to_numpy()]>0].reset_index(drop=True)
            x,_,ok=solve(O.demand.to_numpy(),h.annual_new_patient_capacity.to_numpy(),e)
            rows.append({'availability_probability_scenario':prob,'replicate':r,'assigned':float(x.sum()),'expected_completed':float(x@e.p_attend) if ok else 0.,'active_provider_count':int((h.annual_new_patient_capacity>0).sum())})
    trials=pd.DataFrame(rows);trials.to_csv(output/'provider_availability_trials.csv',index=False)
    agg=trials.groupby('availability_probability_scenario').agg(mean_assigned=('assigned','mean'),sd_assigned=('assigned','std'),p05_assigned=('assigned',lambda s:s.quantile(.05)),p95_assigned=('assigned',lambda s:s.quantile(.95)),mean_completed=('expected_completed','mean'),mean_active_providers=('active_provider_count','mean')).reset_index()
    agg.to_csv(output/'provider_availability_summary.csv',index=False)
    return agg

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',default='inputs');parser.add_argument('--output',default='outputs');parser.add_argument('--trials',type=int,default=80);parser.add_argument('--include-fictional-travel',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parent
    inp=Path(args.inputs); inp=inp if inp.is_absolute() else root/inp
    out=Path(args.output);out=out if out.is_absolute() else root/out;out.mkdir(parents=True,exist_ok=True)
    B=pd.read_csv(inp/'synthetic_cohorts.csv',dtype={'tract_geoid':str});H=pd.read_csv(inp/'providers.csv')
    assert B.cohort_id.is_unique and H.provider_id.is_unique
    assert B.demand_period.eq('annual').all() and B.coordinates_are_synthetic.astype(str).str.lower().eq('true').all()
    assert set(B.insurance_type)==set(INS)
    assert np.isfinite(B.estimated_demand).all() and (B.estimated_demand>=0).all()
    assert H.annual_new_patient_capacity.ge(0).all()
    H=H.reset_index(drop=True).copy()
    # Keep transport groups for equity reporting even when travel omitted.
    O=B.groupby(['insurance_type','transport_access'],as_index=False).agg(demand=('estimated_demand','sum'))
    e=build_edges(O,H,'insurance','odds');x,served,ok=solve(O.demand.to_numpy(),H.annual_new_patient_capacity.to_numpy(),e)
    assert ok
    rows=[summarize('insurance_capacity_wait_odds',O,H,e,x)]
    G=group_summary(O,e,x);G.to_csv(out/'baseline_coverage_by_group.csv',index=False)
    z,xe=max_min_equity(O,H,e)
    rows.append(summarize('max_min_insurance_transport_equity',O,H,e,xe))
    group_summary(O,e,xe).to_csv(out/'equity_coverage_by_group.csv',index=False)
    for label,capscale,uninsured in [('capacity_plus_20pct',1.2,False),('uninsured_accepted_all',1,True),('capacity_and_uninsured',1.2,True)]:
        h=H.copy();h['annual_new_patient_capacity']=h.annual_new_patient_capacity*capscale
        ee=build_edges(O,h,'insurance',uninsured_expansion=uninsured)
        xx,_,_=solve(O.demand.to_numpy(),h.annual_new_patient_capacity.to_numpy(),ee)
        rows.append(summarize(label,O,h,ee,xx))
        group_summary(O,ee,xx).to_csv(out/f'{label}_coverage_by_group.csv',index=False)
    for wait_model in ['piecewise']:
        ee=build_edges(O,H,'insurance',wait_model)
        xx,_,_=solve(O.demand.to_numpy(),H.annual_new_patient_capacity.to_numpy(),ee)
        rows.append(summarize('wait_piecewise_sensitivity',O,H,ee,xx))
    if args.include_fictional_travel:
        cols=['tract_geoid','insurance_type','transport_access','origin_latitude','origin_longitude']
        T=B.groupby(cols,as_index=False).agg(demand=('estimated_demand','sum'))
        T=T[T.demand>0].reset_index(drop=True)
        for model in ['odds','piecewise']:
            te=build_edges(T,H,'synthetic_travel',model)
            tx,_,_=solve(T.demand.to_numpy(),H.annual_new_patient_capacity.to_numpy(),te)
            rows.append(summarize('fictional_travel_'+model,T,H,te,tx))
            if model=='odds':
                group_summary(T,te,tx).to_csv(out/'fictional_travel_coverage_by_group.csv',index=False)
                nz=np.flatnonzero(tx>1e-6)
                assignments=pd.DataFrame({'tract_geoid':T.tract_geoid.to_numpy()[te.oi.to_numpy()[nz]],'insurance_type':T.insurance_type.to_numpy()[te.oi.to_numpy()[nz]],'transport_access':T.transport_access.to_numpy()[te.oi.to_numpy()[nz]],'provider_id':H.provider_id.to_numpy()[te.pj.to_numpy()[nz]],'synthetic_travel_minutes':te.travel_minutes.to_numpy()[nz],'modeled_attendance_probability':te.p_attend.to_numpy()[nz],'assigned_expected_people':tx[nz]})
                assignments.to_csv(out/'fictional_travel_positive_assignments.csv',index=False)
    pd.DataFrame(rows).to_csv(out/'scenario_comparison.csv',index=False)
    av=availability_experiments(O,H,out,reps=args.trials)
    report={'input_rows':{'cohorts':len(B),'providers':len(H),'insurance_transport_groups':len(O)},'demand_annual':float(B.estimated_demand.sum()),'capacity_annual':float(H.annual_new_patient_capacity.sum()),'baseline':rows[0],'max_min_insurance_transport_coverage':z,'equity':rows[1],'scenarios':rows,'availability_sensitivity':av.to_dict(orient='records'),'model_assumptions':{'reference_wait_days':7,'reference_attendance_probability':P7,'weekly_wait_attendance_odds_ratio':OR_WEEK,'travel_half_life_minutes_assumed':TRAVEL_HALF_LIFE,'provider_availability_scenario_probabilities':[.5,.75,.9],'availability_replicates_per_probability':args.trials,'seed':20261111},'warnings':['Synthetic cohort demand and provider insurance/capacity/wait assumptions are not observed Philadelphia access.','All cohort coordinates are fictional. Travel scenarios are NOT geographic evidence.','Completion estimates are modeled expectations using external observational associations and assumed baselines; not predictions or causal effects.','Insurance groups are broad mutually exclusive synthetic categories, not actual plan networks.','77 selected directory records are not the full city provider supply.','Waits do not respond endogenously to congestion.','Max-min equity defined over synthetic insurance categories only; no individual fairness or clinical suitability inference.']}
    (out/'summary_v2.json').write_text(json.dumps(report,indent=2))
    assert rows[0]['assigned']<=H.annual_new_patient_capacity.sum()+1e-4
    assert rows[1]['assigned']>=rows[0]['assigned']-1e-3
    print(pd.DataFrame(rows).to_string(index=False))
    print('\nmax-min coverage:',z,'\nAvailability scenarios:\n',av.to_string(index=False))

if __name__=='__main__':main()
