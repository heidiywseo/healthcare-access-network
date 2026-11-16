"""Live scenario optimizer for the Healthcare Access Simulator (v4). All modeled values are illustrative.
See docs/MODEL_AND_PROVENANCE.md. Geography is gated on verified tract points.
"""
from pathlib import Path
import json, math
import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize
from scipy.sparse import coo_matrix, vstack

ROOT=Path(__file__).resolve().parent
COHORTS=ROOT/'data'/'synthetic_cohorts.csv'
PROVIDERS=ROOT/'data'/'providers.csv'
POINTS=ROOT/'data'/'tract_representative_points.csv'
TRAVEL=ROOT/'data'/'travel_times.csv'            # R5 network travel times (prepare_travel_times.py)
TRAVEL_META=ROOT/'data'/'travel_times_meta.json'
# Study area: keep only tracts whose representative point lies inside a circle. Providers were collected from
# a ~5-mile search, so tracts far outside it would look underserved only because their nearby providers were
# never collected. The data files are not changed. Applied only when real tract points are loaded.
#   'fit_providers' -> smallest circle that contains every provider in providers.csv (computed at load)
#   a number        -> circle of that many miles around STUDY_AREA_CENTER
#   None            -> no restriction; model all tracts
STUDY_AREA_RADIUS_MILES='fit_providers'
STUDY_AREA_CENTER=(39.966,-75.166)  # lat, lon; used only when the radius is a number
PAYER={'Medicaid':'accepts_medicaid','Medicare':'accepts_medicare','Private/other':'accepts_private','Uninsured':'accepts_uninsured'}

def wait_prob(days,mode='odds'):
    w=np.asarray(days,dtype=float)
    if mode=='piecewise':
        z=np.interp(w,[7,30,90],np.log(np.array([.91,.714,.64])/(1-np.array([.91,.714,.64]))))
    else:
        z=np.log(.91/.09)+(w-7)/7*np.log(.95)
    return 1/(1+np.exp(-np.clip(z,-60,60)))

def haversine(lat1,lon1,lat2,lon2):
    a=np.sin(np.radians(lat2-lat1)/2)**2+np.cos(np.radians(lat1))*np.cos(np.radians(lat2))*np.sin(np.radians(lon2-lon1)/2)**2
    return 12742*np.arcsin(np.sqrt(np.clip(a,0,1)))

def enclosing_circle(lat,lon):
    """Smallest circle (center lat, center lon, radius miles) containing all points; minimizes the max distance."""
    lat=np.asarray(lat,dtype=float);lon=np.asarray(lon,dtype=float)
    far=lambda c:float((haversine(c[0],c[1],lat,lon)/1.609344).max())
    starts=[(lat.mean(),lon.mean()),((lat.min()+lat.max())/2,(lon.min()+lon.max())/2)]
    best=min((minimize(far,s,method='Nelder-Mead',options={'xatol':1e-7,'fatol':1e-7,'maxiter':5000}) for s in starts),key=lambda r:r.fun)
    return float(best.x[0]),float(best.x[1]),far(best.x)+0.005  # small margin so edge providers are inside

class Model:
    def __init__(self,study_radius_miles=STUDY_AREA_RADIUS_MILES):
        raw=pd.read_csv(COHORTS,dtype={'tract_geoid':str})
        self.c=raw.groupby(['tract_geoid','insurance_type','transport_access'],as_index=False).agg(demand=('estimated_demand','sum'),latitude=('origin_latitude','first'),longitude=('origin_longitude','first'))
        self.p=pd.read_csv(PROVIDERS)
        self.verified=False
        if POINTS.exists():
            pts=pd.read_csv(POINTS,dtype={'tract_geoid':str})
            required={'tract_geoid','latitude','longitude'}
            if not required.issubset(pts.columns) or pts.tract_geoid.duplicated().any():
                raise ValueError('Invalid tract_representative_points.csv')
            joined=self.c[['tract_geoid']].merge(pts[['tract_geoid','latitude','longitude']],how='left',on='tract_geoid')
            if joined[['latitude','longitude']].isna().any().any():
                raise ValueError('Tract points file incomplete; geographic claims disabled until all 391 tracts matched')
            self.c[['latitude','longitude']]=joined[['latitude','longitude']].to_numpy()
            self.verified=True
        self.study_area=None
        if self.verified and study_radius_miles is not None:
            if study_radius_miles=='fit_providers':
                clat,clon,radius=enclosing_circle(self.p.latitude,self.p.longitude);rule='smallest circle containing all providers'
            else:
                (clat,clon),radius=STUDY_AREA_CENTER,float(study_radius_miles);rule='fixed radius'
            miles=haversine(clat,clon,self.c.latitude.to_numpy(),self.c.longitude.to_numpy())/1.609344
            all_tracts=self.c.tract_geoid.nunique()
            self.c=self.c[miles<=radius].reset_index(drop=True)
            self.study_area={'center_lat':round(clat,6),'center_lon':round(clon,6),'radius_miles':round(radius,2),'rule':rule,'tracts_kept':int(self.c.tract_geoid.nunique()),'tracts_total':int(all_tracts)}
        self.c['group']=self.c.insurance_type+' · '+self.c.transport_access
        self.total=float(self.c.demand.sum())
        self.tracts=self.c.groupby('tract_geoid',as_index=False).agg(demand=('demand','sum'),latitude=('latitude','first'),longitude=('longitude','first'))
        self.network=self._load_network_times() if self.verified and TRAVEL.exists() else None

    def _load_network_times(self):
        """R5 travel-time matrices from prepare_travel_times.py: driving and transit minutes, tract->provider and tract->tract."""
        tt=pd.read_csv(TRAVEL,dtype={'origin_tract':str,'dest_id':str})
        tracts=sorted(tt.origin_tract.unique());index={g:i for i,g in enumerate(tracts)}
        pids=list(self.p.provider_id.astype(str))
        pv=tt[tt.dest_type=='provider'];tv=tt[tt.dest_type=='tract']
        if not set(pids)<=set(pv.dest_id) or not set(self.c.tract_geoid)<=set(tracts):
            raise ValueError('data/travel_times.csv does not cover every provider and tract; rerun prepare_travel_times.py')
        grid=lambda df,cols,col:df.pivot(index='origin_tract',columns='dest_id',values=col).reindex(index=tracts,columns=cols).to_numpy(dtype=float)
        pts=pd.read_csv(POINTS,dtype={'tract_geoid':str}).set_index('tract_geoid').loc[tracts]
        meta=json.loads(TRAVEL_META.read_text()) if TRAVEL_META.exists() else {}
        # Transit departure windows: transit_<key>_min columns described in the meta file.
        # Older files have a single transit_min column, treated as one window.
        windows=[w for w in meta.get('transit_windows',[]) if w.get('column') in tt.columns]
        if not windows and 'transit_min' in tt.columns:
            dep=meta.get('departure','');windows=[{'key':'am','column':'transit_min','departure':dep,'label':dep[11:16] or 'Default'}]
        if not windows: raise ValueError('data/travel_times.csv has no transit columns; rerun prepare_travel_times.py')
        default=meta.get('default_transit_window') if meta.get('default_transit_window') in {w['key'] for w in windows} else windows[0]['key']
        return {'tracts':tracts,'rows':np.array([index[g] for g in self.c.tract_geoid]),'pids':pids,
                'drive_p':grid(pv,pids,'drive_min'),'drive_t':grid(tv,tracts,'drive_min'),
                'transit_p':{w['key']:grid(pv,pids,w['column']) for w in windows},
                'transit_t':{w['key']:grid(tv,tracts,w['column']) for w in windows},
                'windows':windows,'default_window':default,
                'lat':pts.latitude.to_numpy(),'lon':pts.longitude.to_numpy(),'meta':meta}

    def _network_minutes(self,p,window):
        """Cohort x provider minutes: driving for vehicle cohorts, transit for no-vehicle cohorts.
        A hypothetical new site (not in the matrix) uses the times to the nearest tract point."""
        N=self.network;rows=N['rows'];col={pid:j for j,pid in enumerate(N['pids'])}
        n,m=len(self.c),len(p);D=np.empty((n,m));T=np.empty((n,m));note=None
        for j,(pid,lat,lon) in enumerate(zip(p.provider_id.astype(str),p.latitude,p.longitude)):
            if pid in col:
                D[:,j]=N['drive_p'][rows,col[pid]];T[:,j]=N['transit_p'][window][rows,col[pid]]
            else:
                d=haversine(lat,lon,N['lat'],N['lon']);q=int(np.argmin(d))
                D[:,j]=N['drive_t'][rows,q];T[:,j]=N['transit_t'][window][rows,q]
                note={'provider':pid,'times_from_tract':N['tracts'][q],'distance_km':round(float(d[q]),2)}
        car=(self.c.transport_access=='Vehicle access').to_numpy()[:,None]
        mins=np.where(car,D,T)
        return np.where(np.isnan(mins),np.inf,mins),note

    def _apply_changes(self,ch):
        """Provider table after scenario edits (capacity, insurance acceptance, a hypothetical new site)."""
        p=self.p.copy()
        if ch.get('capacity_pct') is not None:
            pct=float(ch['capacity_pct']); p['annual_new_patient_capacity']*=max(0,min(300,100+pct))/100
        if ch.get('uninsured_everywhere'):
            p['accepts_uninsured']=1
        if ch.get('provider_id') and ch.get('provider_capacity_delta'):
            mask=p.provider_id==str(ch['provider_id']);p.loc[mask,'annual_new_patient_capacity']=np.maximum(0,p.loc[mask,'annual_new_patient_capacity']+float(ch['provider_capacity_delta']))
        if ch.get('provider_id') and ch.get('provider_accepts'):
            mask=p.provider_id==str(ch['provider_id'])
            for name,val in ch['provider_accepts'].items():
                if name in PAYER:p.loc[mask,PAYER[name]]=int(bool(val))
        new=ch.get('new_provider')
        if new:
            lat=float(new['latitude']);lon=float(new['longitude'])
            if not (39.82<=lat<=40.16 and -75.35<=lon<=-74.95):raise ValueError('New site must be near Philadelphia map extent')
            record={'provider_id':'NEW','provider_name':'Proposed new clinic','address':'User-selected map point (hypothetical)','latitude':lat,'longitude':lon,'wait_days':float(new.get('wait_days',30)),'annual_new_patient_capacity':max(0,float(new.get('capacity',400)))}
            for typ,col in PAYER.items():record[col]=int(typ in new.get('insurance',list(PAYER)))
            p=pd.concat([p,pd.DataFrame([record])],ignore_index=True)
        return p

    def patient_options(self,change=None,patient=None):
        """Patient view: every provider ranked for one patient (location, insurance, car or not).
        A filter and sort over the same inputs the optimizer uses; no optimization. Illustrative only:
        insurance acceptance, capacity and wait times are synthetic."""
        if not self.network: raise ValueError('Patient view needs network travel times (data/travel_times.csv)')
        ch=change or {};pt=patient or {};N=self.network
        p=self._apply_changes(ch)
        ins=str(pt.get('insurance','Medicaid'))
        if ins not in PAYER: raise ValueError(f'Unknown insurance {ins!r}')
        vehicle=bool(pt.get('vehicle',True))
        window=str(pt.get('transit_window') or ch.get('transit_window') or N['default_window'])
        if window not in N['transit_p']: raise ValueError(f"Unknown transit_window '{window}'")
        limit=float(pt.get('max_minutes') or (ch.get('vehicle_limit',45) if vehicle else ch.get('no_vehicle_limit',60)))
        # Origin: nearest tract internal point to the chosen location (or the tract given).
        if pt.get('tract') in N['tracts']: q=N['tracts'].index(pt['tract']);dist=0.0
        else:
            lat=float(pt['latitude']);lon=float(pt['longitude'])
            d=haversine(lat,lon,N['lat'],N['lon']);q=int(np.argmin(d));dist=float(d[q])
        col={pid:j for j,pid in enumerate(N['pids'])}
        tp=N['drive_p'] if vehicle else N['transit_p'][window];tt=N['drive_t'] if vehicle else N['transit_t'][window]
        mins=[]
        for pid,lat,lon in zip(p.provider_id.astype(str),p.latitude,p.longitude):
            if pid in col: mins.append(tp[q,col[pid]])
            else: mins.append(tt[q,int(np.argmin(haversine(lat,lon,N['lat'],N['lon'])))])  # new site: nearest tract's times
        mins=np.array(mins,dtype=float)
        pw=wait_prob(p.wait_days.to_numpy(),ch.get('wait_model','odds'));ptrav=np.exp(-np.log(2)*mins/60)
        accepts=p[PAYER[ins]].to_numpy(dtype=int).astype(bool)
        out=[{'id':str(r.provider_id),'name':str(r.provider_name),'address':str(r.address),'service_type':str(getattr(r,'service_type','') if isinstance(getattr(r,'service_type',''),str) else ''),
              'accepts':bool(accepts[j]),'minutes':None if np.isnan(mins[j]) else round(float(mins[j]),1),'wait':float(r.wait_days),
              'within':bool(mins[j]<=limit),'p_wait':round(float(pw[j]),4),'p_travel':round(float(ptrav[j]),4),'p_attend':round(float(pw[j]*ptrav[j]),4)}
             for j,r in enumerate(p.itertuples(index=False))]
        win=next(w for w in N['windows'] if w['key']==window)
        return {'origin':{'tract':N['tracts'][q],'lat':float(N['lat'][q]),'lon':float(N['lon'][q]),'distance_km':round(dist,2),
                          'in_study_area':N['tracts'][q] in set(self.c.tract_geoid)},
                'insurance':ins,'vehicle':vehicle,'mode':'Driving' if vehicle else 'Public transit','transit_window':None if vehicle else window,
                'window_label':None if vehicle else win['label'],'limit':limit,'wait_model':ch.get('wait_model','odds'),
                'matches':sum(o['accepts'] and o['within'] for o in out),'accepting':int(accepts.sum()),'providers':out}

    def run(self,change=None):
        ch=change or {}
        p=self._apply_changes(ch)
        # Geographic feasibility can be demonstrated with fictional coordinates ONLY when explicitly labeled.
        # 'network' = R5 driving/transit times; 'illustrative'/'verified' = straight-line distance proxy.
        # 'auto' (or omitted) = network when the travel-time matrix is available, else illustrative.
        default_mode='network' if self.network else 'illustrative'
        travel_mode=str(ch.get('travel_mode') or 'auto')
        if travel_mode=='auto':travel_mode=default_mode
        if travel_mode not in {'none','illustrative','verified','network'}: raise ValueError('Invalid travel_mode')
        if travel_mode=='verified' and not self.verified: raise ValueError('Verified geography requires Census tract representative points; see docs/GEOGRAPHY.md')
        if travel_mode=='network' and not self.network: raise ValueError('Network travel times require data/travel_times.csv; see docs/GEOGRAPHY.md')
        transit_window=None
        if travel_mode=='network':
            transit_window=str(ch.get('transit_window') or self.network['default_window'])
            if transit_window not in self.network['transit_p']: raise ValueError(f"Unknown transit_window '{transit_window}'; available: {', '.join(self.network['transit_p'])}")
        new_site_note=None
        use_geo=travel_mode!='none'
        n=len(self.c);m=len(p)
        insurance=self.c.insurance_type.map({v:k for v,k in PAYER.items()})
        accepted=p[[PAYER[k] for k in PAYER]].to_numpy(dtype=int)
        typ_idx=self.c.insurance_type.map({k:i for i,k in enumerate(PAYER)}).to_numpy()
        elig=accepted[:,typ_idx].T.astype(bool)
        if use_geo:
            car=(self.c.transport_access=='Vehicle access').to_numpy()[:,None]
            if travel_mode=='network':
                mins,new_site_note=self._network_minutes(p,transit_window)
            else:
                lat1=self.c.latitude.to_numpy()[:,None];lon1=self.c.longitude.to_numpy()[:,None]
                km=haversine(lat1,lon1,p.latitude.to_numpy()[None,:],p.longitude.to_numpy()[None,:])
                # Deliberately hypothetical proxies, NOT actual route/transit travel times.
                mins=np.where(car,8+2*km,12+4*km)
            limit_car=float(ch.get('vehicle_limit',45));limit_no=float(ch.get('no_vehicle_limit',60))
            elig &= mins<=np.where(car,limit_car,limit_no)
        reach=elig.sum(axis=1)  # insurance-compatible sites within the travel limit, before candidate pruning
        if use_geo:
            # Sparsify candidate graph for responsive interactive LP. This is an exact
            # LP over the retained candidate edges, not the full feasible network.
            # Retain 12 nearest plus 5 lowest-wait compatible sites per cohort.
            keep=np.zeros_like(elig)
            waits=p.wait_days.to_numpy(dtype=float)
            for i in range(n):
                choices=np.flatnonzero(elig[i])
                if len(choices)<=17: keep[i,choices]=True;continue
                near=choices[np.argsort(mins[i,choices])[:12]]
                quick=choices[np.argsort(waits[choices])[:5]]
                keep[i,near]=True;keep[i,quick]=True
            elig=keep
        else: mins=None
        ii,jj=np.nonzero(elig)
        k=len(ii)
        if k==0:raise ValueError('No feasible insurance-compatible edges')
        # Constraints: sum_j x_ij <= D_i; sum_i x_ij <= C_j.
        ids=np.arange(k)
        A=coo_matrix((np.ones(2*k), (np.r_[ii,n+jj],np.r_[ids,ids])),shape=(n+m,k)).tocsr()
        b=np.r_[self.c.demand.to_numpy(dtype=float),p.annual_new_patient_capacity.to_numpy(dtype=float)]
        # Lexicographic LP: maximize total assignment, then maximize attendance without losing assignment.
        first=linprog(-np.ones(k),A_ub=A,b_ub=b,bounds=(0,None),method='highs')
        if not first.success:raise RuntimeError('Max flow failed: '+first.message)
        maxflow=float(np.sum(first.x))
        attendance=wait_prob(p.wait_days.to_numpy(),ch.get('wait_model','odds'))[jj]
        if use_geo:
            attendance*=np.exp(-np.log(2)*mins[ii,jj]/60) # assumed travel half-life
        # Add equality total assigned within tolerance. Maximize attendance.
        Aeq=coo_matrix((np.ones(k),(np.zeros(k),ids)),shape=(1,k)).tocsr()
        objective=str(ch.get('objective','attendance'))
        if objective=='equity':
            groups=sorted(self.c.group.unique()); gcode=pd.Categorical(self.c.group,categories=groups).codes
            D=np.array([self.c.loc[gcode==q,'demand'].sum() for q in range(len(groups))])
            # Max-min coverage z with x and z, preserve maximum total served.
            from scipy.sparse import hstack
            gA=coo_matrix((np.ones(k),(gcode[ii],ids)),shape=(len(groups),k)).tocsr()
            constraints=hstack([-gA,coo_matrix((D,(np.arange(len(groups)),np.zeros(len(groups)))),shape=(len(groups),1)).tocsr()]).tocsr()
            Ab=hstack([A,coo_matrix((n+m,1))]).tocsr()
            eq=hstack([Aeq,coo_matrix((1,1))]).tocsr()
            fair=linprog(np.r_[np.zeros(k),-1.],A_ub=vstack([Ab,constraints]),b_ub=np.r_[b,np.zeros(len(groups))],A_eq=eq,b_eq=[maxflow],bounds=[(0,None)]*k+[(0,1)],method='highs')
            if not fair.success:raise RuntimeError('Fairness LP failed: '+fair.message)
            z=float(fair.x[-1]);
            # Retain optimal min group coverage, then optimize expected attendance.
            fairness_floor=-(z-1e-6)*D
            second=linprog(-attendance,A_ub=vstack([A,-gA]),b_ub=np.r_[b,fairness_floor],A_eq=Aeq,b_eq=[maxflow],bounds=(0,None),method='highs')
        else:
            second=linprog(-attendance,A_ub=A,b_ub=b,A_eq=Aeq,b_eq=[maxflow],bounds=(0,None),method='highs')
        if not second.success:raise RuntimeError('Attendance LP failed: '+second.message)
        flows=second.x
        assigned=float(flows.sum());completed=float(flows@attendance)
        provider_assigned=np.bincount(jj,weights=flows,minlength=m)
        cohort_assigned=np.bincount(ii,weights=flows,minlength=n)
        groupout=self.c[['group','demand']].copy();groupout['assigned']=cohort_assigned
        groups=groupout.groupby('group',as_index=False).sum();groups['coverage']=groups.assigned/groups.demand
        tractout=self.c[['tract_geoid','demand']].copy();tractout['assigned']=cohort_assigned
        tractout=tractout.groupby('tract_geoid',as_index=False).sum();tractout['coverage']=tractout.assigned/tractout.demand.replace(0,np.nan)
        bytract=tractout.set_index('tract_geoid').to_dict('index')
        traces=[]
        for index in np.flatnonzero(flows>1e-4):
            i=int(ii[index]);j=int(jj[index]);tr=str(self.c.iloc[i].tract_geoid)
            traces.append({'tract':tr,'provider':str(p.iloc[j].provider_id),'group':str(self.c.iloc[i]['group']),'assigned':round(float(flows[index]),3),'expected_completed':round(float(flows[index]*attendance[index]),3)})
        providers=[]
        for j,row in p.iterrows():
            providers.append({'id':str(row.provider_id),'name':str(row.provider_name),'address':str(row.address),'lat':float(row.latitude),'lon':float(row.longitude),'capacity':round(float(row.annual_new_patient_capacity),2),'assigned':round(float(provider_assigned[j]),3),'wait':float(row.wait_days),'accepts':{typ:bool(row[col]) for typ,col in PAYER.items()}})
        reach_by_tract={}
        for g,grp,cnt in zip(self.c.tract_geoid,self.c.group,reach):reach_by_tract.setdefault(str(g),{})[grp]=int(cnt)
        tracts=[]
        for _,row in self.tracts.iterrows():
            r=bytract.get(str(row.tract_geoid),{'demand':0,'assigned':0,'coverage':0})
            tracts.append({'id':str(row.tract_geoid),'lat':float(row.latitude),'lon':float(row.longitude),'demand':round(float(r['demand']),3),'assigned':round(float(r['assigned']),3),'coverage':round(float(r['coverage']),5),'reach':reach_by_tract.get(str(row.tract_geoid),{})})
        nm=self.network['meta'] if self.network else {}
        win=next((w for w in self.network['windows'] if w['key']==transit_window),{}) if transit_window else {}
        if travel_mode=='network':
            warning=(f"Travel times from R5 routing: driving on OpenStreetMap roads (free-flow, no congestion); public transit on SEPTA schedules "
                     f"(median over departures {win.get('departure','?')[:16].replace('T',' ')} + {nm.get('departure_window_hours','?')} h, incl. walking and waiting). "
                     "Tract origins are Census internal points. Attendance-vs-travel multiplier is an assumption.")
        elif self.verified:
            warning='Real Census tract points; travel time here is a hypothetical straight-line distance proxy, NOT road/transit routing.' if use_geo else 'Real Census tract points. Travel constraints are disabled.'
        else:
            warning='ILLUSTRATIVE ONLY: population coordinates are fictional. All travel feasibility and site-placement effects reflect a synthetic map, NOT real Philadelphia reachability.' if use_geo else 'Population coordinates are fictional. Geographic travel constraints are disabled.'
        return {'meta':{'geography_verified':self.verified,'study_area':self.study_area,'geography_active':use_geo,'travel_mode':travel_mode,'vehicle_limit':float(ch.get('vehicle_limit',45)),'no_vehicle_limit':float(ch.get('no_vehicle_limit',60)),'geography_warning':warning,'network_travel_available':bool(self.network),'travel_source':nm if travel_mode=='network' else None,'transit_window':transit_window,'transit_windows':[{'key':w['key'],'label':w['label']} for w in self.network['windows']] if self.network else [],'new_site_travel':new_site_note,'algorithm':('Two-stage linear programming over up to 17 candidate sites per cohort: maximum assignment then maximum expected attendance' if use_geo else 'Two-stage exact linear programming: maximum flow then maximum expected attended intakes')+(' with max-min group coverage' if objective=='equity' else ''),'candidate_edge_pruning':bool(use_geo),'edge_count':int(k),'nonzero_flows':len(traces)},'metrics':{'demand':round(self.total,2),'assigned':round(assigned,2),'completed':round(completed,2),'coverage':round(assigned/self.total,5),'attendance':round(completed/assigned,5) if assigned else 0,'min_group_coverage':round(float(groups.coverage.min()),5),'capacity':round(float(p.annual_new_patient_capacity.sum()),2)},'providers':providers,'tracts':tracts,'flows':traces,'groups':groups.round(5).to_dict('records')}

if __name__=='__main__':
    import json,time
    t=time.time();v=Model().run();print('elapsed',round(time.time()-t,2),v['metrics'],'edges',v['meta']['edge_count'],'flows',len(v['flows']))
