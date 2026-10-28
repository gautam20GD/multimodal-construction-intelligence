from pathlib import Path
from typing import Optional, Literal
import uuid, httpx
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from .config import get_settings
from . import db
from .ai import analyze, ask

s=get_settings()
app=FastAPI(title=s.app_name,version="1.0.0",description="Multimodal construction decision-support API")
app.add_middleware(CORSMiddleware,allow_origins=s.origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

@app.on_event("startup")
def startup():
    db.init_db()
    (Path(__file__).resolve().parent.parent/s.upload_dir).mkdir(parents=True,exist_ok=True)

@app.get("/api/health")
def health(): return {"status":"ok","service":s.app_name,"ai_configured":bool(s.ai_api_key),"model":s.ai_model if s.ai_api_key else "demo-mode"}

@app.post("/api/analyze")
async def analyze_api(mode: Literal["safety","crack","general"]=Form("general"),text:str=Form(""),project_data:str=Form(""),image:Optional[UploadFile]=File(None)):
    b=None; mime="image/jpeg"
    if image:
        mime=image.content_type or ""
        if mime not in ("image/jpeg","image/png","image/webp"): raise HTTPException(415,"Upload a JPG, PNG or WEBP image.")
        b=await image.read()
        if len(b)>s.max_upload_mb*1024*1024: raise HTTPException(413,f"Image exceeds {s.max_upload_mb} MB.")
        try:
            from PIL import Image
            import io
            im=Image.open(io.BytesIO(b)); im.verify()
        except Exception: raise HTTPException(400,"Invalid image file.")
        ext={"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}[mime]
        (Path(__file__).resolve().parent.parent/s.upload_dir/(uuid.uuid4().hex+ext)).write_bytes(b)
    try: data,model=await analyze(mode,text,project_data,b,mime)
    except httpx.HTTPStatusError as e: raise HTTPException(502,f"AI provider returned HTTP {e.response.status_code}. Check backend configuration.")
    except (httpx.HTTPError,ValueError,KeyError): raise HTTPException(502,"AI provider failed or returned invalid JSON.")
    aid,now=db.save(mode,data)
    return {**data,"analysis_id":aid,"mode":mode,"model":model,"created_at":now}

class Plan(BaseModel):
    project_type:str="Residential building"
    area_sqft:float=Field(default=1200,gt=0,le=10000000)
    floors:int=Field(default=1,ge=1,le=100)
    budget:float=Field(default=2500000,ge=0)
    currency:str="INR"
    notes:str=""
@app.post("/api/plan")
def plan(p:Plan):
    rate=1800 if "residential" in p.project_type.lower() else 2400
    cost=p.area_sqft*rate*max(1,p.floors*.82)
    tasks=[
      {"phase":"Pre-construction","name":"Requirements, survey & approvals","duration_days":7,"depends_on":[]},
      {"phase":"Pre-construction","name":"Design coordination & procurement","duration_days":14,"depends_on":["Requirements, survey & approvals"]},
      {"phase":"Structure","name":"Site preparation & foundations","duration_days":18,"depends_on":["Design coordination & procurement"]},
      {"phase":"Structure","name":"Frame and slab works","duration_days":max(14,int(p.area_sqft/100)),"depends_on":["Site preparation & foundations"]},
      {"phase":"Envelope","name":"Masonry, roofing & envelope","duration_days":max(18,int(p.area_sqft/80)),"depends_on":["Frame and slab works"]},
      {"phase":"Services","name":"MEP rough-in and inspections","duration_days":18,"depends_on":["Masonry, roofing & envelope"]},
      {"phase":"Finishes","name":"Finishes and fixtures","duration_days":max(21,int(p.area_sqft/65)),"depends_on":["MEP rough-in and inspections"]},
      {"phase":"Handover","name":"Testing, snagging & handover","duration_days":7,"depends_on":["Finishes and fixtures"]}]
    return {"project_type":p.project_type,"area_sqft":p.area_sqft,"floors":p.floors,"currency":p.currency,"indicative_cost":round(cost,2),"budget":p.budget,"budget_status":"within indicative budget" if p.budget>=cost else "indicative estimate exceeds budget","total_duration_days":sum(t["duration_days"] for t in tasks),"tasks":tasks,"assumptions":[f"Benchmark rate: {rate} {p.currency}/sq ft, before local adjustment.","Rough heuristic, not a tender BOQ or committed schedule.","Validate soil, structural drawings, approvals, labor, taxes, escalation and procurement."],"material_allowances":[{"item":"Concrete","quantity":"TBD from structural drawings","basis":"Engineer / quantity surveyor"},{"item":"Reinforcement steel","quantity":"TBD from bar bending schedule","basis":"Engineer"},{"item":"Masonry and mortar","quantity":"TBD from wall layout","basis":"Quantity surveyor"},{"item":"Finishes and services","quantity":"TBD from specifications","basis":"Project team"}]}

class Valuation(BaseModel):
    location:str="Not specified"
    area_sqft:float=Field(gt=0,le=100000000)
    rate_per_sqft:float=Field(gt=0)
    age_years:float=Field(default=0,ge=0,le=300)
    condition:Literal["new","good","average","needs_repair"]="good"
    adjustment_percent:float=Field(default=0,ge=-90,le=500)
    currency:str="INR"
@app.post("/api/valuation")
def valuation(p:Valuation):
    cf={"new":1.0,"good":.95,"average":.85,"needs_repair":.65}[p.condition]
    af=max(.5,1-min(p.age_years*.008,.5)); base=p.area_sqft*p.rate_per_sqft
    value=base*cf*af*(1+p.adjustment_percent/100)
    return {"location":p.location,"area_sqft":p.area_sqft,"currency":p.currency,"base_value":round(base,2),"estimated_value":round(value,2),"low_estimate":round(value*.9,2),"high_estimate":round(value*1.1,2),"assumptions":{"rate_per_sqft":p.rate_per_sqft,"condition_factor":cf,"age_factor":round(af,3),"adjustment_percent":p.adjustment_percent},"limitations":["Indicative calculator, not a formal appraisal.","Rate and adjustment are user supplied and may not reflect current comparables, title, zoning, amenities or market conditions.","Consult a licensed local valuer for lending or legal purposes."]}

class Assistant(BaseModel):
    question:str=Field(min_length=2,max_length=5000)
    project_context:str=""
    weather_context:str=""
@app.post("/api/assistant")
async def assistant(p:Assistant):
    try: answer=await ask(f"Project context: {p.project_context or 'Not supplied'}\nWeather/site conditions: {p.weather_context or 'Not supplied'}\nQuestion: {p.question}")
    except httpx.HTTPError: raise HTTPException(502,"AI provider request failed.")
    return {"answer":answer,"mode":"ai" if s.ai_api_key else "demo-mode","disclaimer":"Verify safety-critical, structural, legal and valuation decisions with qualified professionals."}

@app.get("/api/weather")
async def weather(city:str):
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            g=await c.get("https://geocoding-api.open-meteo.com/v1/search",params={"name":city,"count":1,"language":"en","format":"json"}); g.raise_for_status()
            places=g.json().get("results",[])
            if not places: raise HTTPException(404,"City not found.")
            p=places[0]
            r=await c.get("https://api.open-meteo.com/v1/forecast",params={"latitude":p["latitude"],"longitude":p["longitude"],"current":"temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code","daily":"precipitation_probability_max,wind_speed_10m_max","timezone":"auto","forecast_days":1}); r.raise_for_status()
        return {"city":p["name"],"country":p.get("country"),"timezone":r.json().get("timezone"),"current":r.json().get("current",{}),"daily":r.json().get("daily",{}),"advisory":["Recheck before concrete pours, lifting, roof work and work at height.","Follow official local severe-weather alerts; this forecast is not an emergency warning."]}
    except HTTPException: raise
    except Exception: return {"available":False,"city":city,"message":"Live weather unavailable. Check official local meteorological service.","advisory":["Pause exposed work during lightning, unsafe wind, flooding or poor visibility.","Secure loose materials and protect excavations before rain."]}

@app.get("/api/history")
def history(): return {"items":db.listing()}
@app.get("/api/history/{aid}")
def history_item(aid:int):
    x=db.get(aid)
    if not x: raise HTTPException(404,"Analysis not found.")
    return x
