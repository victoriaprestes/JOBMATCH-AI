"""Collect public job feeds; outputs only public vacancy data."""
import json, re, html
from pathlib import Path
from datetime import datetime, timezone
import requests

OUT=Path("data/jobs_feed.json")
KEYWORDS=[
 "administrative analyst","operations analyst","business operations","process analyst",
 "project coordinator","project assistant","back office","governance analyst",
 "business analyst","data analyst","business intelligence","bi analyst",
 "analista administrativo","analista de operações","analista de processos",
 "analista de negócios","analista de projetos","backoffice","analista de dados",
 "power bi","sql","support analyst","it analyst","junior analyst"
]
ROLE_TERMS=("analyst","analista","operations","operacoes","process","processos","business","negocios",
            "administrative","administrativo","back office","backoffice","project","projetos",
            "data","dados","support","suporte","governance","governanca","bi ")
SENIOR_TERMS=("senior","sr.","sênior","lead","principal","director","diretor","head of","manager","gerente")

def clean_text(value):
    value=re.sub(r"<[^>]+>"," ",str(value or ""))
    return re.sub(r"\\s+"," ",html.unescape(value)).strip()

def is_relevant(title, description=""):
    text=(title+" "+description).lower()
    return any(k in text for k in ROLE_TERMS) and not any(s in title.lower() for s in SENIOR_TERMS)

def fetch_json(url, params=None):
    response=requests.get(url,params=params,timeout=25,headers={"User-Agent":"JobMatchAI/0.1 (personal job search)"})
    response.raise_for_status()
    return response.json()

def collect_arbeitnow():
    found=[]
    for page in range(1,4):
        payload=fetch_json("https://www.arbeitnow.com/api/job-board-api",{"page":page})
        for j in payload.get("data",[]):
            title=j.get("title","")
            desc=clean_text(j.get("description",""))
            loc=j.get("location","")
            remote=bool(j.get("remote",False))
            local=("curitiba" in loc.lower() or "parana" in loc.lower() or "paraná" in loc.lower() or "brazil" in loc.lower() or "brasil" in loc.lower())
            if (remote or local) and is_relevant(title,desc):
                found.append({
                  "source":"Arbeitnow","source_url":"https://www.arbeitnow.com/",
                  "external_id":str(j.get("slug") or j.get("url") or title),
                  "company":j.get("company_name","Empresa não informada"),"title":title,
                  "location":loc or ("Remoto" if remote else "Não informado"),
                  "work_mode":"Remoto" if remote else "Presencial / não informado",
                  "salary":0,"salary_label":"Não informado","url":j.get("url",""),
                  "description":desc,"published_at":j.get("created_at")
                })
    return found

def collect_remotive():
    payload=fetch_json("https://remotive.com/api/remote-jobs",{"limit":500})
    found=[]
    for j in payload.get("jobs",[]):
        title=j.get("title","")
        desc=clean_text(j.get("description",""))
        if not is_relevant(title,desc):
            continue
        found.append({
          "source":"Remotive","source_url":"https://remotive.com/",
          "external_id":str(j.get("id")),"company":j.get("company_name","Empresa não informada"),
          "title":title,"location":j.get("candidate_required_location","Remoto"),
          "work_mode":"Remoto","salary":0,"salary_label":j.get("salary") or "Não informado",
          "url":j.get("url",""),"description":desc,
          "published_at":j.get("publication_date")
        })
    return found

def main():
    jobs=[]; errors=[]
    for name,fn in [("Arbeitnow",collect_arbeitnow),("Remotive",collect_remotive)]:
        try: jobs.extend(fn())
        except Exception as exc: errors.append(f"{name}: {type(exc).__name__}: {exc}")
    unique={}
    for j in jobs:
        key=(j["source"],j["external_id"])
        unique[key]=j
    result={"updated_at":datetime.now(timezone.utc).isoformat(),
            "sources":["Arbeitnow","Remotive"],"count":len(unique),
            "errors":errors,"jobs":list(unique.values())}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Coletadas {len(unique)} vagas. Fontes com erro: {len(errors)}.")
    if errors: print("\\n".join(errors))

if __name__=="__main__": main()
