"""Local Healthcare Access Simulator server. Start: python server.py"""
from pathlib import Path
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from engine import Model

ROOT=Path(__file__).resolve().parent
app=FastAPI(title='Healthcare Access Simulator',version='4.0')
model=Model()
class Scenario(BaseModel):
    capacity_pct:float=0
    uninsured_everywhere:bool=False
    objective:str='attendance'
    wait_model:str='odds'
    provider_id:str|None=None
    provider_capacity_delta:float=0
    provider_accepts:dict[str,bool]|None=None
    new_provider:dict|None=None
    travel_mode:str='auto'
    transit_window:str|None=None
    vehicle_limit:float=45
    no_vehicle_limit:float=60
    travel_decay:str='halflife60'
    max_wait_days:float|None=None
    provider_wait_days:float|None=None
    telehealth_share:float=0
    telehealth_effect:str='neutral'
    new_providers:list[dict]|None=None
    capacity_deltas:dict[str,float]|None=None

@app.get('/')
def index():return FileResponse(ROOT/'index.html')
@app.get('/api/status')
def status():return {'live':True,'geography_verified':model.verified,'study_area':model.study_area,'network_travel':bool(model.network),'transit_windows':[{'key':w['key'],'label':w['label']} for w in model.network['windows']] if model.network else [],'cohorts':len(model.c),'providers':len(model.p)}
@app.post('/api/run')
def run(s:Scenario):
    try:return model.run(s.model_dump())
    except (ValueError,RuntimeError) as e:raise HTTPException(status_code=400,detail=str(e))

class Patient(BaseModel):
    scenario:Scenario=Scenario()
    latitude:float|None=None
    longitude:float|None=None
    tract:str|None=None
    insurance:str='Medicaid'
    vehicle:bool=True
    max_minutes:float|None=None
    transit_window:str|None=None
@app.post('/api/patient')
def patient(s:Patient):
    if s.tract is None and (s.latitude is None or s.longitude is None):raise HTTPException(status_code=400,detail='Give a tract or a latitude and longitude')
    try:return model.patient_options(s.scenario.model_dump(),s.model_dump(exclude={'scenario'}))
    except (ValueError,RuntimeError) as e:raise HTTPException(status_code=400,detail=str(e))

class SiteSearch(BaseModel):
    scenario:Scenario=Scenario()
    capacity:float=500
    wait_days:float=14
    insurance:list[str]=['Medicaid','Medicare','Private/other','Uninsured']
    goal:str='completed'
    count:int=1

@app.post('/api/site_search')
def site_search(s:SiteSearch):
    try:return model.site_search(s.scenario.model_dump(),{'capacity':s.capacity,'wait_days':s.wait_days,'insurance':s.insurance},s.goal,s.count)
    except (ValueError,RuntimeError) as e:raise HTTPException(status_code=400,detail=str(e))

app.mount('/assets',StaticFiles(directory=ROOT/'assets'),name='assets')
app.mount('/docs',StaticFiles(directory=ROOT/'docs'),name='docs')
if __name__=='__main__':
    import uvicorn
    print('Open http://127.0.0.1:8765')
    uvicorn.run(app,host='127.0.0.1',port=8765)
