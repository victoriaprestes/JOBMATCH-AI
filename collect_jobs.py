"""Coleta vagas de entrada com contratação explicitamente confirmada no Brasil.

Fontes usadas nesta versão são feeds públicos. A cobertura não equivale a uma busca
exaustiva em LinkedIn, Gupy, Indeed ou em páginas de carreiras de todas as empresas.
"""
import html
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

OUT = Path("data/jobs_feed.json")
TIMEOUT = 25
HEADERS = {"User-Agent": "JobMatchAI/0.3 (+https://github.com/victoriaprestes/JOBMATCH-AI)"}

# Cargos compatíveis com a experiência já demonstrada.
PROFILE_ROLE_PATTERNS = [
    r"\bassistente\s+(administrativ[oa]|executiv[oa]|de\s+diretoria|de\s+operacoes|de\s+operações|de\s+processos|de\s+projetos|de\s+compras|de\s+suprimentos|de\s+facilities|financeir[oa]|de\s+back\s*office)\b",
    r"\b(auxiliar\s+administrativ[oa]|secretari[oa]\s+executiv[oa]|executive\s+assistant|administrative\s+assistant|operations\s+assistant|office\s+assistant|office\s+coordinator)\b",
    r"\b(back\s*office\s+(assistant|associate|analyst)|procurement\s+assistant|purchasing\s+assistant|facilities\s+assistant|project\s+assistant|pmo\s+assistant)\b",
    r"\b(analista|analyst)\s+(administrativ[oa]|de\s+operacoes|de\s+operações|de\s+processos|de\s+projetos|de\s+compras|de\s+suprimentos|de\s+planejamento|de\s+negocios|de\s+negócios|de\s+back\s*office)\b",
    r"\b(administrative|business\s+operations|operations|process|project|procurement|purchasing)\s+(assistant|associate|analyst)\b",
    r"\b(assistente|assistant)\s+de\s+gestao\b",
    r"\b(management\s+assistant|management\s+trainee|project\s+coordinator\s+assistant)\b",
]

# Cargos que podem ser uma trilha de transição/estudo. Não são tratados como
# experiência já adquirida: a interface os identifica separadamente.
TRANSITION_ROLE_PATTERNS = [
    r"\b(assistente|auxiliar)\s+(de\s+)?(governanca|governance|governanca\s+de\s+ti|it\s+governance|controles\s+internos|internal\s+controls|riscos|risk|compliance|auditoria|audit)\b",
    r"\b(analista|analyst)\s+(de\s+)?(governanca|governance|controles\s+internos|internal\s+controls|riscos|risk|compliance|auditoria|audit)(\s+(junior|jr\.?|i))?\b",
    r"\b(governance|it\s+governance|internal\s+controls|risk|compliance|audit)\s+(assistant|associate|analyst\s+(i|junior|jr\.?))\b",
    r"\b(junior|jr\.?)\s+(governance|it\s+governance|it\s+operations|it\s+service\s+management|itsm)\s+(analyst|coordinator)\b",
    r"\b(governance|it\s+governance|it\s+operations|it\s+service\s+management|itsm)\s+coordinator\b",
    r"\b(assistente|auxiliar)\s+(de\s+)?(operacoes\s+de\s+ti|it\s+operations|infraestrutura\s+de\s+ti|servicos\s+de\s+ti|gestao\s+de\s+servicos|gestao\s+de\s+ti)\b",
    r"\b(analista|analyst)\s+(de\s+)?(operacoes\s+de\s+ti|it\s+operations|it\s+service\s+management|itsm|service\s+management|service\s+delivery)(\s+(junior|jr\.?|i))?\b",
    r"\b(it\s+operations|it\s+service\s+management|itsm|service\s+management|service\s+delivery|it\s+governance)\s+(assistant|associate|analyst\s+(i|junior|jr\.?))\b",
    r"\b(assistente|auxiliar)\s+(de\s+)?(pmo|projetos\s+de\s+ti|gestao\s+de\s+projetos|gestao|gestao de projetos)\b",
    r"\b(pmo|project\s+management\s+office)\s+(assistant|coordinator\s+assistant|analyst\s+(i|junior|jr\.?))\b",
    r"\b(analista|analyst)\s+(de\s+)?(pmo|gestao\s+de\s+projetos|gestao\s+de\s+servicos|service\s+management)(\s+(junior|jr\.?|i))?\b",
    r"\b(analista|analyst)\s+(de\s+)?(projetos|projects|project)(\s+(junior|jr\.?|i))?\b",
    r"\b(assistente|auxiliar)\s+(de\s+)?(processos|melhoria\s+continua|qualidade|controles)\b",
    r"\b(analista|analyst)\s+(de\s+)?(processos|melhoria\s+continua|qualidade|controles)(\s+(junior|jr\.?|i))?\b",
]

SENIOR_TITLE = re.compile(
    r"\b(senior|sr\.?|sênior|pleno|mid.level|lead|principal|director|diretor|diretora|head|manager|gerente|"
    r"staff|iii|iv|chief|vp|vice president|especialista|specialist)\b", re.I
)
EXCLUDED_TITLE = re.compile(
    r"\b(developer|desenvolvedor|engineer|engenheiro|data analyst|analista de dados|"
    r"sales|vendas|inside sales|recruiter|recrutador|designer|customer support|"
    r"service desk|help desk|tier\s*[23]|video annotation|estagio|estágio|"
    r"caixa|loja|shopping|retail|estoque|warehouse|logistica|logistics|"
    r"recepcionista|front desk|atendimento ao cliente|temporaria|temporario|temporary)\b", re.I
)

BRAZIL_TERMS = (
    "brazil", "brasil", "curitiba", "colombo", "sao jose dos pinhais",
    "são josé dos pinhais", "pinhais", "araucaria", "araucária",
    "campo largo", "almirante tamandare", "almirante tamandaré",
)
GLOBAL_ONLY = ("worldwide", "anywhere", "global", "latin america", "latam", "south america", "americas")
REMOTE_WORDS = ("remote", "remoto", "work from home", "home office")
HYBRID_WORDS = ("hybrid", "hibrido", "híbrido")
ONSITE_WORDS = ("on-site", "onsite", "presencial", "in person")

def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(c for c in value if not unicodedata.combining(c))

def clean(value):
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def classify_location(location):
    loc = normalize(location)
    if any(term in loc for term in map(normalize, BRAZIL_TERMS)):
        if "curitiba" in loc or any(x in loc for x in ("colombo", "sao jose dos pinhais", "pinhais", "araucaria", "campo largo", "almirante tamandare")):
            return "Brasil confirmado", "Curitiba ou região metropolitana indicada no anúncio"
        return "Brasil confirmado", "Brasil indicado explicitamente no anúncio"
    # Remote/Worldwide sem país não prova que a empresa contrata no Brasil.
    if any(term in loc for term in GLOBAL_ONLY):
        return "Não elegível", "Região ampla/global; contratação no Brasil não confirmada"
    return "Não elegível", "O anúncio não confirma contratação no Brasil"

def classify_mode(location, remote_flag=None):
    loc = normalize(location)
    if any(x in loc for x in HYBRID_WORDS):
        return "Híbrido"
    if remote_flag is True or any(x in loc for x in REMOTE_WORDS):
        return "Remoto"
    if any(x in loc for x in ONSITE_WORDS) or any(x in loc for x in map(normalize, BRAZIL_TERMS)):
        return "Presencial"
    return "Não informado"

def is_entry_level(title, description):
    title_n = normalize(title)
    desc_n = normalize(clean(description))
    if SENIOR_TITLE.search(title_n) or EXCLUDED_TITLE.search(title_n):
        return False
    # Exigeções explícitas acima de dois anos eliminam a vaga, mesmo se o título disser assistente.
    if re.search(r"\b([3-9]|[1-9][0-9])\s*\+?\s*(years?|anos?)\b", desc_n):
        return False
    if re.search(r"\b(minimum|at least|required|exige|exigimos|minimo|minimo de)\s+([3-9]|[1-9][0-9])\s*(years?|anos?)\b", desc_n):
        return False
    if re.search(r"\b(senior|sênior|pleno|mid.level)\s+(position|role|level|vaga|cargo)\b", desc_n):
        return False
    # Assistente/auxiliar/trainee são cargos de entrada por nomenclatura.
    if re.search(r"\b(assistente|assistant|auxiliar|trainee|aprendiz|intern|estagiari[oa])\b", title_n):
        return True
    # Analista só entra com marcador explícito de início de carreira.
    entry_marker = re.search(
        r"\b(junior|jr\.?|entry.level|entry level|early career|analista i|analyst i|"
        r"0\s*(a|to|-)\s*2\s+anos?|1\s*(a|to|-)\s*2\s+anos?|"
        r"no experience required|sem experiencia|experiencia de ate 2 anos|"
        r"up to 2 years|0-2 years|1-2 years)\b", title_n + " " + desc_n
    )
    return bool(entry_marker)

def classify_role(title):
    title_n = normalize(title)
    # Os cargos específicos de TI/governança/gestão devem ficar na trilha de transição,
    # mesmo quando também contenham termos como operações ou processos.
    if any(re.search(p, title_n, re.I) for p in TRANSITION_ROLE_PATTERNS):
        return "Trilha de transição", "Área de governança/IT Operations/gestão para desenvolver com estudo"
    if any(re.search(p, title_n, re.I) for p in PROFILE_ROLE_PATTERNS):
        return "Perfil atual", "Experiência administrativa, financeira e operacional já demonstrada"
    return None, None

def request_json(url, params=None):
    response = requests.get(url, params=params, timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def parse_brl_salary(label):
    raw = clean(label)
    if not raw or not re.search(r"(r\$|brl|reais)", normalize(raw)):
        return None, None, "Salário não informado em reais"
    text = normalize(raw).replace(".", "").replace(",", ".")
    values = re.findall(r"(\d+(?:\.\d+)?)\s*([kK])?", text)
    nums = [float(n) * (1000 if suffix else 1) for n, suffix in values]
    if not nums:
        return None, None, "Conferir remuneração no anúncio"
    low = min(nums[:2])
    high = max(nums[:2]) if len(nums) > 1 else nums[0]
    if re.search(r"(ano|anual|year)", text):
        low, high = low / 12, high / 12
    return round(low), round(high), "Faixa bruta mensal estimada em reais; conferir periodicidade"

def extract_benefits(item, description):
    """Extrai benefícios declarados pela fonte ou por seção explícita do anúncio."""
    raw = item.get("benefits") or item.get("benefit") or item.get("perks")
    values = []
    if isinstance(raw, list):
        values = [clean(x.get("name") or x.get("title") or x) if isinstance(x, (dict, str)) else "" for x in raw]
    elif isinstance(raw, dict):
        values = [clean(k) + (": " + clean(v) if isinstance(v, str) and v.strip() else "") for k, v in raw.items()]
    elif isinstance(raw, str):
        values = [clean(x) for x in re.split(r"[;|•\\n]", raw) if clean(x)]
    values = [x for x in values if x]
    if values:
        return "; ".join(dict.fromkeys(values))[:1200]
    # Fallback conservador: só captura o trecho quando o anúncio tem um cabeçalho de benefícios.
    text = clean(description)
    match = re.search(
        r"(?:benef[ií]cios|benefits|o que oferecemos|what we offer|perks)\\s*[:\\-]?\\s*(.{0,1400})",
        text, re.I
    )
    if not match:
        return ""
    section = match.group(1)
    section = re.split(
        r"\\b(?:requisitos|qualifica[cç][oõ]es|responsabilidades|sobre a vaga|about the role|requirements)\\b",
        section, maxsplit=1, flags=re.I
    )[0]
    return section[:1000].strip(" .;:-")

def make_job(source, item, title, company, location, description, url, published, external_id,
             salary_label=None, remote_flag=None, employment_type=None, mode_hint=None):
    role_group, role_note = classify_role(title)
    mode = mode_hint or classify_mode(location, remote_flag)
    salary_min, salary_max, salary_note = parse_brl_salary(salary_label)
    return {
        "source": source,
        "company": company or "Empresa não informada",
        "title": title,
        "location": location,
        "work_mode": mode,
        "employment_type": employment_type or "Não informado",
        "salary_label": salary_label or "Não informado",
        "salary_min_brl_monthly": salary_min,
        "salary_max_brl_monthly": salary_max,
        "salary_note": salary_note,
        "benefits": extract_benefits(item, description),
        "eligibility_status": "Brasil confirmado",
        "eligibility_note": classify_location(location)[1],
        "role_group": role_group,
        "role_note": role_note,
        "url": url or "",
        "description": clean(description),
        "published_at": published,
        "external_id": str(external_id or url or title),
    }


def is_targeted_affirmative_vacancy(title, description):
    """Exclui vagas exclusivas/afirmativas para PCD ou pessoas negras."""
    text = normalize(f"{title} {description}")
    target = (
        r"(?:pcd|pessoas? com deficiencia|pessoas? negras?|negros?|"
        r"pretos?|populacao negra|profissionais negros?|candidatos negros?)"
    )
    exclusive = (
        r"(?:exclusiv[oa]s?|somente|apenas|reservad[oa]s?|"
        r"afirmativ[oa]s?|destinad[oa]s?|voltad[oa]s?)"
    )
    patterns = (
        rf"\b{exclusive}\b.{{0,100}}\b(?:para\s+)?{target}\b",
        rf"\b{target}\b.{{0,100}}\b{exclusive}\b",
        rf"\b(?:vaga|vagas|oportunidade|oportunidades)\b.{{0,100}}\b{exclusive}\b.{{0,100}}\b{target}\b",
        rf"\b(?:pcd|pessoa com deficiencia|pessoas com deficiencia)\b.{{0,80}}\b(?:exclusiv[oa]|reservad[oa]|afirmativ[oa])\b",
    )
    return any(re.search(pattern, text, re.I) for pattern in patterns)

def keep_job(title, location, description):
    if is_targeted_affirmative_vacancy(title, description):
        return False
    eligibility, _ = classify_location(location)
    if eligibility != "Brasil confirmado":
        return False
    role_group, _ = classify_role(title)
    if not role_group:
        return False
    if not is_entry_level(title, description):
        return False
    return True

def remotive():
    payload = request_json("https://remotive.com/api/remote-jobs", {"limit": 500})
    jobs = []
    for item in payload.get("jobs", []):
        title = item.get("title", "")
        location = item.get("candidate_required_location") or ""
        description = item.get("description") or ""
        if not keep_job(title, location, description):
            continue
        jobs.append(make_job(
            "Remotive", item, title, item.get("company_name"), location, description,
            item.get("url"), item.get("publication_date"), item.get("id"),
            item.get("salary"), True, item.get("job_type"),
        ))
    return jobs

def remoteok():
    payload = request_json("https://remoteok.com/api")
    jobs = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict) or not item.get("position"):
            continue
        title = item.get("position", "")
        location = item.get("location") or ""
        description = item.get("description") or ""
        if not keep_job(title, location, description):
            continue
        salary = item.get("salary") or ""
        if not salary and (item.get("salary_min") or item.get("salary_max")):
            salary = f"{item.get('salary_min') or item.get('salary_max')} - {item.get('salary_max') or item.get('salary_min')}"
        jobs.append(make_job(
            "RemoteOK", item, title, item.get("company"), location, description,
            item.get("url"), item.get("date"), item.get("id"), salary, True,
        ))
    return jobs

def arbeitnow():
    payload = request_json("https://www.arbeitnow.com/api/job-board-api")
    jobs = []
    for item in payload.get("data", []):
        title = item.get("title", "")
        location = item.get("location") or ""
        description = item.get("description") or ""
        if not keep_job(title, location, description):
            continue
        jobs.append(make_job(
            "Arbeitnow", item, title, item.get("company_name"), location, description,
            item.get("url"), item.get("created_at"), item.get("slug") or item.get("url"),
            item.get("salary"), item.get("remote"),
        ))
    return jobs



def is_fresh_posting(published_at, max_age_days=45):
    if not published_at:
        return False
    try:
        parsed = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed >= datetime.now(timezone.utc) - timedelta(days=max_age_days)
    except (TypeError, ValueError):
        return False

def has_conflicting_local_city(title):
    local_cities = {
        "curitiba", "colombo", "sao jose dos pinhais",
        "pinhais", "araucaria", "campo largo",
    }
    patterns = (
        r"[-–]\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]+?)\s*/\s*[A-Z]{2}\b",
        r"\(([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]+?)\s*/\s*[A-Z]{2}\)",
    )
    title_n = normalize(title)
    for pattern in patterns:
        for match in re.finditer(pattern, str(title or "")):
            city = normalize(match.group(1)).strip(" -")
            if city and city not in local_cities:
                return True
    return False

def gupy():
    """Busca ampla no endpoint público usado pela busca do portal Gupy."""
    api = "https://portal.gupy.io/api/job-search/jobs"
    keywords = [
        "assistente",
        "analista",
        "assistente administrativo",
        "assistente de operações",
        "assistente de projetos",
        "assistente de governança",
        "assistente de operações de TI",
        "assistente de compras",
        "assistente de facilities",
        "analista de governança júnior",
        "analista de processos júnior",
        "IT Operations Assistant",
        "PMO Assistant",
        "assistente de gestão",
        "governança",
        "governança de TI",
        "IT governance",
        "IT operations",
        "IT service management",
        "gestão de serviços",
        "ITSM",
        "PMO",
        "controles internos",
        "gestão de riscos",
        "compliance",
        "analista de processos",
        "gestão de projetos",
        "analista de PMO",
        "analista de gestão de serviços",
        "assistente de ITSM",
    ]
    jobs = []
    seen = set()
    workplace_modes = (
        ("Local", "hybrid,on-site", "Paraná"),
        ("Remoto", "remote", None),
    )
    for scope, workplace_type, state in workplace_modes:
        for keyword in keywords:
            for page in range(2):
                params = {
                    "jobName": keyword,
                    "offset": page * 100,
                    "limit": 100,
                    "workplaceType": workplace_type,
                    "type": "vacancy_type_effective,vacancy_type_trainee",
                }
                if state:
                    params["state"] = state
                payload = request_json(api, params)
                rows = payload.get("data") if isinstance(payload, dict) else None
                if not isinstance(rows, list):
                    raise ValueError("Gupy: resposta inesperada; esperado objeto com lista 'data'")
                for item in rows:
                    title = item.get("name") or ""
                    company = item.get("careerPageName") or ""
                    company_n = normalize(company).strip(" .!,:;")
                    if not company or company_n in {
                        "confidencial", "empresa confidencial", "pagina de carreira", "carreiras",
                    } or company_n.startswith("vem fazer parte do time"):
                        continue
                    city = item.get("city") or ""
                    state_name = item.get("state") or ""
                    country = item.get("country") or ""
                    workplace = item.get("workplaceType") or ""
                    location = ", ".join(str(x) for x in (workplace, city, state_name, country) if x)
                    mode_map = {"remote": "Remoto", "hybrid": "Híbrido", "on-site": "Presencial"}
                    mode_hint = mode_map.get(normalize(workplace), classify_mode(location))
                    if scope == "Local":
                        local_terms = ("curitiba", "colombo", "sao jose dos pinhais", "pinhais", "araucaria", "campo largo")
                        if not any(term in normalize(location) for term in local_terms):
                            continue
                        if has_conflicting_local_city(title):
                            continue
                    published = item.get("publishedDate")
                    if not is_fresh_posting(published):
                        continue
                    description = clean(item.get("description") or "")
                    if not keep_job(title, location, description):
                        continue
                    url = item.get("jobUrl") or ""
                    if not str(url).startswith("https://") or ".gupy.io/" not in str(url):
                        continue
                    key = str(url)
                    if key in seen:
                        continue
                    seen.add(key)
                    salary = item.get("salary")
                    if isinstance(salary, dict):
                        currency = str(salary.get("currency") or "").upper()
                        low = salary.get("min") or salary.get("minimum")
                        high = salary.get("max") or salary.get("maximum")
                        if currency in ("BRL", "R$") and low is not None:
                            salary = f"R$ {low}" + (f" - {high}" if high is not None else "")
                        else:
                            salary = None
                    job_type = item.get("type") or "Regime não informado"
                    if job_type == "vacancy_type_effective":
                        job_type = "Efetivo (regime CLT a confirmar)"
                    elif job_type == "vacancy_type_trainee":
                        job_type = "Trainee (regime a confirmar)"
                    jobs.append(make_job(
                        "Gupy", item, title, company, location, description, url,
                        published, item.get("id") or url,
                        salary, mode_hint == "Remoto", job_type, mode_hint,
                    ))
                if len(rows) < 100:
                    break
    print(f"Gupy: {len(jobs)} vaga(s) elegíveis após filtros.")
    return jobs

def main():
    jobs, errors = [], []
    for name, collector in (("Gupy", gupy), ("Remotive", remotive), ("RemoteOK", remoteok), ("Arbeitnow", arbeitnow)):
        try:
            found = collector()
            jobs.extend(found)
            print(f"{name}: {len(found)} vaga(s) elegíveis após filtros.")
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    unique = {}
    for job in jobs:
        key = (job["source"], job["external_id"])
        unique[key] = job
    ordered = sorted(
        unique.values(),
        key=lambda j: (
            j["role_group"] != "Perfil atual",
            j["work_mode"] not in ("Híbrido", "Presencial"),
            j.get("published_at") or "",
        ),
        reverse=False,
    )
    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(ordered),
        "errors": errors,
        "sources": ["Gupy", "Remotive", "RemoteOK", "Arbeitnow"],
        "filters": {
            "country": "Brasil confirmado; vagas globais sem elegibilidade brasileira são excluídas",
            "locations": ["Curitiba e região metropolitana", "Remoto em todo o Brasil"],
            "seniority": "Entrada; assistente/auxiliar ou júnior com requisitos compatíveis",
            "salary_floor_brl": 3000,
            "salary_policy": "Vagas sem salário informado são mantidas e identificadas; somente valores explicitamente em BRL são comparados ao piso",
        },
        "coverage_note": "Cobertura parcial. Inclui busca pública Gupy e feeds Remotive, RemoteOK e Arbeitnow; não inclui LinkedIn, Indeed nem todas as páginas de carreira das empresas.",
        "jobs": ordered,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Feed atualizado: {len(ordered)} vaga(s); {len(errors)} fonte(s) com erro.")
    if errors:
        print("\n".join(errors))

if __name__ == "__main__":
    main()
