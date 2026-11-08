"""Coleta vagas de feeds públicos; não acessa páginas privadas nem exige credenciais."""
import html, json, re
from datetime import datetime, timezone
from pathlib import Path
import requests

OUT=Path("data/jobs_feed.json")
ROLE_TERMS=("analyst","analista","operations","operacoes","process","processos","business","negocios",
 "administrative","administrativo","back office","backoffice","project","projetos","data","dados",
 "support","suporte","governance","governanca","business intelligence","power bi","sql")
SENIOR_TERMS=("senior","sr.","sênior","lead","principal","director","diretor","head of","manager","gerente")
BRAZIL_TERMS=("brazil","brasil","worldwide","anywhere","latin america","latam","south america","americas")

def clean(value):
    value=re.sub(r"<[^>]+>"," ",str(value or ""))
    return re.sub(r"\s+"," ",html.unescape(value)).strip()

def relevant(title,desc):
    t=(title+" "+desc).lower()
    return any(k in t for k in ROLE_TERMS) and not any(k in title.lower() for k in SENIOR_TERMS)

def get(url,params=None):
    r=requests.get(url,params=params,timeout=30,headers={"User-Agent":"JobMatchAI/0.1"})
    r.raise_for_status()
    return r.json()

def remotive():
    payload=get("https://remotive.com/api/remote-jobs",{"limit":500})
    out=[]
    for j in payload.get("jobs",[]):
        title=j.get("title",""); desc=clean(j.get("description"))
        allowed=j.get("candidate_required_location") or "Worldwide"
        if not any(x in allowed.lower() for x in BRAZIL_TERMS): continue
        if not relevant(title,desc): continue
        out.append({"source":"Remotive","company":j.get("company_name") or "Não informada",
         "title":title,"location":allowed,"work_mode":"Remoto","salary":0,
         "salary_label":j.get("salary") or "Não informado","url":j.get("url",""),
         "description":desc,"published_at":j.get("publication_date"),"external_id":str(j.get("id"))})
    return out

def arbeitnow():
    payload=get("https://www.arbeitnow.com/api/job-board-api")
    out=[]
    for j in payload.get("data",[]):
        title=j.get("title",""); desc=clean(j.get("description"))
        location=j.get("location") or ""
        if not any(x in location.lower() for x in BRAZIL_TERMS) and not any(x in location.lower() for x in ("curitiba","parana","paraná")):
            continue
        if not relevant(title,desc): continue
        out.append({"source":"Arbeitnow","company":j.get("company_name") or "Não informada",
         "title":title,"location":location or "Não informada",
         "work_mode":"Remoto" if j.get("remote") else "Presencial / não informado",
         "salary":0,"salary_label":"Não informado","url":j.get("url",""),
         "description":desc,"published_at":j.get("created_at"),
         "external_id":str(j.get("slug") or j.get("url"))})
    return out

def main():
    jobs=[]; errors=[]
    for name,fn in (("Remotive",remotive),("Arbeitnow",arbeitnow)):
        try: jobs.extend(fn())
        except Exception as e: errors.append(f"{name}: {type(e).__name__}: {e}")
    unique={(j["source"],j["external_id"]):j for j in jobs}
    data={"updated_at":datetime.now(timezone.utc).isoformat(),"count":len(unique),
          "errors":errors,"jobs":list(unique.values())}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Feed atualizado: {len(unique)} vagas; {len(errors)} fonte(s) com erro.")
    if errors: print("\n".join(errors))

if __name__=="__main__": main()
