"""Coleta vagas de feeds públicos com filtros conservadores para o perfil-alvo.

Não presume que "Worldwide" significa contratação confirmada no Brasil.
Salários estrangeiros são normalizados apenas quando a moeda e o período são identificáveis.
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
HEADERS = {"User-Agent": "JobMatchAI/0.2 (+https://github.com/victoriaprestes/JOBMATCH-AI)"}

# Busca por cargo/título, não por palavras soltas em qualquer trecho da descrição.
ROLE_PATTERNS = [
    r"\b(analista|analyst)\b.*\b(operac|operation|business|process|processo|administr|projeto|project|pmo|dados|data|bi|report|planejamento|planning|compras|procurement|supply chain|suprimentos|sistemas|systems|negocios|negócios)\b",
    r"\b(business|operations|process|administrative|project|data|bi|reporting|procurement|purchasing|supply chain|systems|planning)\b.*\b(analyst|coordinator|coordenador|coordenadora|assistant|assistente|specialist|especialista|associate|consultant)\b",
    r"\b(assistente|assistant|coordenador|coordenadora|coordinator)\b.*\b(administrativ|operac|operation|projeto|project|pmo|diretoria|executive|process|processo)\b",
    r"\b(executive assistant|assistente executiv[oa]|office coordinator|project coordinator|coordenador[ao] de projetos)\b",
    r"\b(data analyst|analista de dados|bi analyst|analista de bi|business intelligence analyst|reporting analyst)\b",
    r"\b(business analyst|analista de negocios|analista de negócios|it business analyst|systems analyst|analista de sistemas)\b",
    r"\b(pmo analyst|analista de pmo|project analyst|analista de projetos|process analyst|analista de processos)\b",
]

SENIOR_TITLE = re.compile(
    r"\b(senior|sr\.?|sênior|lead|principal|director|diretor|diretora|head|manager|gerente|"
    r"staff|iii|iv|chief|vp|vice president)\b",
    re.I,
)
EXCLUDE_TITLE = re.compile(
    r"\b(developer|desenvolvedor|engineer|engenheiro|writer|copywriter|"
    r"sales|vendas|inside sales|recruiter|recrutador|designer|"
    r"tier\s*[23]|service desk|help desk|customer support|video annotation)\b",
    re.I,
)

BRAZIL = ("brazil", "brasil", "curitiba", "parana", "paraná", "sao paulo", "são paulo")
LATAM = ("latin america", "latam", "south america")
GLOBAL = ("worldwide", "anywhere", "americas", "remote - global", "global")

def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(c for c in value if not unicodedata.combining(c))

def clean(value):
    value = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def is_target_role(title):
    title_n = normalize(title)
    if SENIOR_TITLE.search(title_n) or EXCLUDE_TITLE.search(title_n):
        return False
    return any(re.search(pattern, title_n, re.I) for pattern in ROLE_PATTERNS)

def classify_location(location, source=""):
    loc = normalize(location)
    if any(term in loc for term in BRAZIL):
        return "Brasil indicado", "Brasil indicado no anúncio"
    if any(term in loc for term in LATAM):
        return "América Latina — confirmar", "Região indicada; confirmar contratação no Brasil"
    if any(term in loc for term in GLOBAL):
        return "Global — confirmar", "Anúncio global; contratação no Brasil não confirmada"
    return "Não confirmado", "Localização não confirma elegibilidade no Brasil"

def request_json(url, params=None):
    response = requests.get(url, params=params, timeout=TIMEOUT, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def parse_salary(label, fx_rates=None, default_currency=None, default_period=None):
    """Retorna estimativa mensal bruta na moeda original e em BRL, quando possível."""
    raw = clean(label)
    if not raw:
        return {
            "salary": 0, "salary_currency": None, "salary_period": None,
            "salary_min_monthly": None, "salary_max_monthly": None,
            "salary_brl_monthly_estimate": None, "salary_note": "Não informado",
        }

    text = normalize(raw)
    currency = default_currency
    if "r$" in raw.lower() or "brl" in text or "reais" in text:
        currency = "BRL"
    elif "€" in raw or "eur" in text:
        currency = "EUR"
    elif "£" in raw or "gbp" in text:
        currency = "GBP"
    elif "$" in raw or "usd" in text:
        currency = "USD"

    period = default_period
    if any(x in text for x in ("/hour", "per hour", "hourly", "por hora", "hour")):
        period = "hour"
    elif any(x in text for x in ("/month", "per month", "monthly", "por mes", "mensal", "month")):
        period = "month"
    elif any(x in text for x in ("/year", "per year", "annual", "annually", "yearly", "anual", "year")):
        period = "year"

    # Reconhece números como 3.5k, 35,3k, 3000 e faixas.
    nums = re.findall(r"(?<![A-Za-z])(\d+(?:[.,]\d+)?)\s*([kK])?", raw)
    values = []
    for number, suffix in nums:
        value = float(number.replace(",", "."))
        if suffix:
            value *= 1000
        values.append(value)
    if not values or currency is None or period is None:
        return {
            "salary": 0, "salary_currency": currency, "salary_period": period,
            "salary_min_monthly": None, "salary_max_monthly": None,
            "salary_brl_monthly_estimate": None,
            "salary_note": "Remuneração não normalizada; conferir anúncio original",
        }

    low, high = min(values[:2]), max(values[:2]) if len(values) > 1 else values[0]
    divisor = 160 if period == "hour" else (12 if period == "year" else 1)
    low_monthly, high_monthly = low / divisor, high / divisor
    rate = 1.0 if currency == "BRL" else (fx_rates or {}).get(currency)
    brl = ((low_monthly + high_monthly) / 2 * rate) if rate else None
    note = "Estimativa mensal bruta"
    if period == "hour":
        note += " (160 h/mês)"
    if currency != "BRL":
        note += "; conversão cambial estimada" if rate else "; sem conversão cambial"
    return {
        "salary": round(brl) if brl is not None else 0,
        "salary_currency": currency,
        "salary_period": period,
        "salary_min_monthly": round(low_monthly, 2),
        "salary_max_monthly": round(high_monthly, 2),
        "salary_brl_monthly_estimate": round(brl, 2) if brl is not None else None,
        "salary_note": note,
    }

def get_fx_rates():
    try:
        data = request_json("https://api.frankfurter.dev/v1/latest", {"base": "USD", "symbols": "BRL,EUR,GBP"})
        usd_brl = data.get("rates", {}).get("BRL")
        if not usd_brl:
            return {}
        return {
            "USD": float(usd_brl),
            "EUR": float(usd_brl) / float(data["rates"]["EUR"]),
            "GBP": float(usd_brl) / float(data["rates"]["GBP"]),
        }
    except Exception:
        # A coleta continua; salários em moeda estrangeira ficam sem conversão.
        return {}

def make_job(source, company, title, location, description, url, published, external_id,
             salary_label=None, work_mode="Remoto", employment_type="Não informado",
             fx_rates=None, default_currency=None, default_period=None):
    location_status, eligibility_note = classify_location(location, source)
    salary_data = parse_salary(salary_label, fx_rates, default_currency, default_period)
    return {
        "source": source,
        "company": company or "Não informada",
        "title": title,
        "location": location or "Não informada",
        "work_mode": work_mode,
        "employment_type": employment_type,
        **salary_data,
        "salary_label": salary_label or "Não informado",
        "eligibility_status": location_status,
        "eligibility_note": eligibility_note,
        "url": url or "",
        "description": clean(description),
        "published_at": published,
        "external_id": str(external_id or url or title),
    }

def remotive(fx_rates):
    payload = request_json("https://remotive.com/api/remote-jobs", {"limit": 500})
    jobs = []
    for item in payload.get("jobs", []):
        title = item.get("title", "")
        if not is_target_role(title):
            continue
        location = item.get("candidate_required_location") or ""
        status, _ = classify_location(location, "Remotive")
        # Mantém América Latina e global em categoria separada; não confunde com Brasil confirmado.
        if status == "Não confirmado":
            continue
        jobs.append(make_job(
            "Remotive", item.get("company_name"), title, location,
            item.get("description"), item.get("url"), item.get("publication_date"),
            item.get("id"), item.get("salary"), "Remoto",
            item.get("job_type") or "Não informado", fx_rates, default_currency="USD",
        ))
    return jobs

def remoteok(fx_rates):
    payload = request_json("https://remoteok.com/api")
    jobs = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict) or not item.get("position"):
            continue
        title = item.get("position", "")
        if not is_target_role(title):
            continue
        location = item.get("location") or "Remote / global"
        salary_label = item.get("salary") or ""
        if not salary_label and (item.get("salary_min") or item.get("salary_max")):
            low = item.get("salary_min") or item.get("salary_max")
            high = item.get("salary_max") or low
            salary_label = f"USD {low}-{high} per year"
        jobs.append(make_job(
            "RemoteOK", item.get("company"), title, location,
            item.get("description"), item.get("url"), item.get("date"),
            item.get("id"), salary_label, "Remoto", "Não informado",
            fx_rates, default_currency="USD", default_period="year",
        ))
    return jobs

def arbeitnow(fx_rates):
    payload = request_json("https://www.arbeitnow.com/api/job-board-api")
    jobs = []
    for item in payload.get("data", []):
        title = item.get("title", "")
        if not is_target_role(title):
            continue
        location = item.get("location") or ""
        status, _ = classify_location(location, "Arbeitnow")
        # A fonte é predominantemente europeia; só aceita localização explicitamente brasileira.
        if status != "Brasil indicado":
            continue
        jobs.append(make_job(
            "Arbeitnow", item.get("company_name"), title, location,
            item.get("description"), item.get("url"), item.get("created_at"),
            item.get("slug") or item.get("url"), None,
            "Remoto" if item.get("remote") else "Presencial / não informado",
            "Não informado", fx_rates,
        ))
    return jobs

def main():
    fx_rates = get_fx_rates()
    jobs, errors = [], []
    for name, collector in (
        ("Remotive", remotive),
        ("RemoteOK", remoteok),
        ("Arbeitnow", arbeitnow),
    ):
        try:
            found = collector(fx_rates)
            jobs.extend(found)
            print(f"{name}: {len(found)} vaga(s) após filtros.")
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    unique = {}
    for job in jobs:
        key = (job["source"], job["external_id"])
        unique[key] = job
    ordered = sorted(
        unique.values(),
        key=lambda j: (j["eligibility_status"] != "Brasil indicado", j.get("published_at") or ""),
        reverse=False,
    )
    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(ordered),
        "errors": errors,
        "sources": ["Remotive", "RemoteOK", "Arbeitnow"],
        "salary_policy": "Salários estrangeiros são estimativas mensais brutas convertidas quando há cotação; valores não informados permanecem desconhecidos, não zero.",
        "jobs": ordered,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Feed atualizado: {len(ordered)} vagas; {len(errors)} fonte(s) com erro.")
    if errors:
        print("\n".join(errors))

if __name__ == "__main__":
    main()
