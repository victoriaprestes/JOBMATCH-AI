"""Coleta vagas de entrada com contratação explicitamente confirmada no Brasil.

Fontes usadas nesta versão são feeds públicos. A cobertura não equivale a uma busca
exaustiva em LinkedIn, Gupy, Indeed ou em páginas de carreiras de todas as empresas.
"""
import html
import json
import re
import unicodedata
from datetime import datetime, timezone
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
    r"\b(assistente|auxiliar)\s+(de\s+)?(operacoes\s+de\s+ti|it\s+operations|infraestrutura\s+de\s+ti|servicos\s+de\s+ti|gestao\s+de\s+servicos|gestao\s+de\s+ti)\b",
    r"\b(analista|analyst)\s+(de\s+)?(operacoes\s+de\s+ti|it\s+operations|it\s+service\s+management|itsm|service\s+management|service\s+delivery)(\s+(junior|jr\.?|i))?\b",
    r"\b(it\s+operations|it\s+service\s+management|itsm|service\s+management|service\s+delivery|it\s+governance)\s+(assistant|associate|analyst\s+(i|junior|jr\.?))\b",
    r"\b(assistente|auxiliar)\s+(de\s+)?(pmo|projetos\s+de\s+ti|gestao\s+de\s+projetos|gestao|gestao de projetos)\b",
    r"\b(pmo|project\s+management\s+office)\s+(assistant|coordinator\s+assistant|analyst\s+(i|junior|jr\.?))\b",
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
    r"service desk|help desk|tier\s*[23]|video annotation|estagio|estágio)\b", re.I
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
        "eligibility_status": "Brasil confirmado",
        "eligibility_note": classify_location(location)[1],
        "role_group": role_group,
        "role_note": role_note,
        "url": url or "",
        "description": clean(description),
        "published_at": published,
        "external_id": str(external_id or url or title),
    }

def keep_job(title, location, description):
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


def fetch_empregare_pages(params, max_pages=5):
    jobs = []
    for page in range(1, max_pages + 1):
        query = list(params) + [("ItensPagina", 100), ("Pagina", page)]
        payload = request_json("https://memora.empregare.com/api/pt-br/vagas/buscar-novo", query)
        model = payload.get("model") or {}
        jobs.extend(model.get("dados") or [])
        if page >= int(model.get("totalPaginas") or 1):
            break
    return jobs

def empregare():
    jobs = []
    # Presencial/híbrido: somente Curitiba e municípios próximos explicitamente filtrados.
    local_params = [
        ("Estado", "Paraná"),
        ("Cidade", "Curitiba"),
        ("Cidade", "Colombo"),
        ("Cidade", "São José dos Pinhais"),
        ("Cidade", "Pinhais"),
        ("Cidade", "Araucária"),
        ("Cidade", "Campo Largo"),
        ("Modalidade", "presencial"),
        ("Modalidade", "hibrido"),
        ("Regime", "CLT"),
    ]
    # Remoto: API filtrada por país, não por localização global.
    remote_params = [
        ("Pais", "Brasil"),
        ("Modalidade", "remoto"),
        ("Regime", "CLT"),
    ]
    for mode, params in (("Local", local_params), ("Remoto", remote_params)):
        for item in fetch_empregare_pages(params):
            title = item.get("titulo") or ""
            city_names = item.get("cidades") or []
            if isinstance(city_names, str):
                city_names = [city_names]
            if mode == "Remoto":
                location = "Remoto - Brasil"
                mode_hint = "Remoto"
            else:
                allowed_cities = {
                    "curitiba", "colombo", "sao jose dos pinhais",
                    "pinhais", "araucaria", "campo largo",
                }
                matching_cities = [str(city) for city in city_names if normalize(city) in allowed_cities]
                if not matching_cities:
                    continue
                location = ", ".join(matching_cities) + ", Paraná, Brasil"
                mode_text = normalize(item.get("trabalhoRemotoTexto") or "")
                if "hibrid" in mode_text:
                    mode_hint = "Híbrido"
                elif item.get("trabalhoRemoto") is True or "remoto" in mode_text:
                    mode_hint = "Remoto"
                else:
                    mode_hint = "Presencial"
            level = item.get("nivel") or ""
            summary = item.get("chamada") or ""
            description = " ".join(str(x) for x in (summary, level) if x)
            if not keep_job(title, location, description):
                continue
            salary = item.get("salario")
            if isinstance(salary, (int, float)) and salary > 0:
                salary = f"R$ {salary}"
            url = item.get("url") or ""
            if url and not str(url).startswith("http"):
                url = "https://www.empregare.com/" + str(url).lstrip("/")
            jobs.append(make_job(
                "Empregare", item, title, item.get("empresa"), location, description,
                url, item.get("data") or item.get("timestamp"), item.get("id"),
                salary, mode_hint == "Remoto", "CLT (filtro da fonte)", mode_hint,
            ))
    return jobs

def main():
    jobs, errors = [], []
    for name, collector in (("Empregare", empregare), ("Remotive", remotive), ("RemoteOK", remoteok), ("Arbeitnow", arbeitnow)):
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
        "sources": ["Empregare", "Remotive", "RemoteOK", "Arbeitnow"],
        "filters": {
            "country": "Brasil confirmado; vagas globais sem elegibilidade brasileira são excluídas",
            "locations": ["Curitiba e região metropolitana", "Remoto em todo o Brasil"],
            "seniority": "Entrada; assistente/auxiliar ou júnior com requisitos compatíveis",
            "salary_floor_brl": 3000,
            "salary_policy": "Vagas sem salário informado são mantidas e identificadas; somente valores explicitamente em BRL são comparados ao piso",
        },
        "coverage_note": "Cobertura parcial dos feeds públicos listados. Não inclui integração com LinkedIn, Gupy, Indeed nem páginas de carreira não conectadas.",
        "jobs": ordered,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Feed atualizado: {len(ordered)} vaga(s); {len(errors)} fonte(s) com erro.")
    if errors:
        print("\n".join(errors))

if __name__ == "__main__":
    main()
