"""Optional: create real Census tract internal-point coordinates from a Census Gazetteer file.
Usage: python prepare_census_tract_points.py /path/to/2024_Gazetteer_tracts.txt
The source file must be downloaded by the user from the Census Bureau. No network required.
"""
import sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
if len(sys.argv)!=2:raise SystemExit('Usage: python prepare_census_tract_points.py /path/to/Census_Gazetteer_tracts.txt')
p=Path(sys.argv[1]); df=pd.read_csv(p,sep='\t',dtype=str,encoding='utf-8-sig')
df.columns=df.columns.str.strip()
col={x.upper():x for x in df.columns}
for key in ['GEOID','INTPTLAT','INTPTLONG']:
 if key not in col:raise SystemExit(f'Missing {key}. File must be an official Census tract Gazetteer table.')
out=df[[col['GEOID'],col['INTPTLAT'],col['INTPTLONG']]].copy();out.columns=['tract_geoid','latitude','longitude']
out['tract_geoid']=out.tract_geoid.astype(str).str.zfill(11)
out['latitude']=pd.to_numeric(out.latitude,errors='coerce');out['longitude']=pd.to_numeric(out.longitude,errors='coerce')
needed=pd.read_csv(ROOT/'data'/'synthetic_cohorts.csv',usecols=['tract_geoid'],dtype=str).tract_geoid.unique()
out=out[out.tract_geoid.isin(needed)].drop_duplicates('tract_geoid')
if len(out)!=len(needed) or out[['latitude','longitude']].isna().any().any():
 missing=set(needed)-set(out.tract_geoid);raise SystemExit(f'Not all cohort tracts matched: {len(out)}/{len(needed)}; sample missing: {sorted(missing)[:6]}')
if not out.latitude.between(39.8,40.2).all() or not out.longitude.between(-75.4,-74.9).all():raise SystemExit('Unexpected coordinates outside Philadelphia vicinity')
out.to_csv(ROOT/'data'/'tract_representative_points.csv',index=False)
print(f'Created {len(out)} tract representative points. Restart server.py to load them. Source file: {p.name}')
