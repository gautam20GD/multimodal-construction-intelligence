import base64, json
import httpx
from .config import get_settings

SYSTEM = """You are a cautious construction decision-support assistant. Return ONLY valid JSON with keys title, summary, risk_level (low|medium|high|unknown), findings (array of objects with label, observation, severity, confidence), recommendations (array of strings), limitations (array of strings). Never certify safety or code compliance. State when evidence is insufficient. For potentially serious cracks, instability, falling material, or imminent hazards, advise isolating the area and getting qualified on-site inspection. Do not identify people."""

def demo(mode,text,project,has_image):
    if mode=="safety":
        findings=[{"label":"Site hazard review","observation":"Check edge protection, scaffolds, access routes, housekeeping, lifting operations and electrical hazards on site.","severity":"unknown","confidence":"low"},
                  {"label":"PPE review","observation":"Confirm task-appropriate hard hats, high-visibility clothing, eye protection, gloves and fall protection.","severity":"medium","confidence":"low"}]
        if any(x in (text or "").lower() for x in ["fall","exposed wire","no helmet","unsafe","collapse"]):
            findings.insert(0,{"label":"Reported potential hazard","observation":"The description suggests a possible hazard. Verify immediately and restrict access if danger is present.","severity":"high","confidence":"medium"})
        return {"title":"Construction Site Safety Screening","summary":"Demo-mode checklist screening. This is not a certified site inspection.","risk_level":"medium" if text or has_image else "unknown","findings":findings,"recommendations":["Isolate imminent hazards and alert the site safety officer.","Verify controls against the approved risk assessment and local rules.","Record hazard location, owner, corrective action and closure evidence."],"limitations":["AI provider is not configured; image pixels were not analyzed.","Not a compliance determination or substitute for a competent on-site person."]}
    if mode=="crack":
        return {"title":"Structural Crack Screening","summary":"A preliminary workflow only. Crack significance depends on width, pattern, movement, location, material and history.","risk_level":"unknown","findings":[{"label":"Engineering assessment needed","observation":"Record location, orientation, approximate width/length, movement, water ingress, displacement and nearby door/window changes.","severity":"unknown","confidence":"low"}],"recommendations":["For widening or diagonal/stepped cracks, sagging, displacement, falling material or unusual sounds, keep people away and seek urgent structural engineer review.","Do not conceal a potentially active crack before professional assessment.","Take dated photos with a scale and have a qualified professional measure and monitor it."],"limitations":["AI provider is not configured; image pixels were not analyzed.","Photos cannot establish capacity or rule out hidden damage."]}
    return {"title":"Construction Context Review","summary":"Demo mode is active. Configure an AI provider to analyze image pixels and project context.","risk_level":"unknown","findings":[{"label":"Input received","observation":f"Description length: {len(text or '')}; image attached: {'yes' if has_image else 'no'}.","severity":"unknown","confidence":"high"}],"recommendations":["Provide project stage, site location, material and the decision you need to make.","Verify critical outputs with the responsible professional."],"limitations":["AI provider is not configured; image pixels were not analyzed."]}

async def analyze(mode,text,project,image_bytes=None,mime="image/jpeg"):
    s=get_settings()
    if not s.ai_api_key: return demo(mode,text,project,image_bytes is not None),"demo-mode"
    content=[{"type":"text","text":f"Mode: {mode}\nDescription: {text or '(none)'}\nProject data: {project or '(none)'}"}]
    if image_bytes: content.append({"type":"image_url","image_url":{"url":f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"}})
    body={"model":s.ai_model,"temperature":0.2,"messages":[{"role":"system","content":SYSTEM},{"role":"user","content":content}],"response_format":{"type":"json_object"}}
    async with httpx.AsyncClient(timeout=90) as client:
        r=await client.post(s.ai_base_url.rstrip("/")+"/chat/completions",headers={"Authorization":f"Bearer {s.ai_api_key}"},json=body); r.raise_for_status()
    data=json.loads(r.json()["choices"][0]["message"]["content"])
    defaults={"title":"Construction Analysis","summary":"No summary provided.","risk_level":"unknown","findings":[],"recommendations":[],"limitations":[]}
    for k,v in defaults.items(): data.setdefault(k,v)
    if data["risk_level"] not in ("low","medium","high","unknown"): data["risk_level"]="unknown"
    return data,s.ai_model

async def ask(prompt):
    s=get_settings()
    if not s.ai_api_key:
        return "Demo mode: configure AI_API_KEY in backend/.env for model-generated advice. Check approved drawings and method statements, document decisions, and consult qualified professionals for safety-critical matters."
    body={"model":s.ai_model,"temperature":0.3,"messages":[{"role":"system","content":"You are a careful construction project assistant. Give practical advice and state when qualified local review is required."},{"role":"user","content":prompt}]}
    async with httpx.AsyncClient(timeout=60) as client:
        r=await client.post(s.ai_base_url.rstrip("/")+"/chat/completions",headers={"Authorization":f"Bearer {s.ai_api_key}"},json=body); r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
