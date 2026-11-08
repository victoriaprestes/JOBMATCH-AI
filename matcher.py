import re
import unicodedata

SKILLS = [
    "excel", "sap", "contas a pagar", "contas a receber", "fornecedores",
    "contratos", "processos", "indicadores", "kpi", "power bi", "sql",
    "python", "pandas", "gestao de projetos", "governanca", "controles internos",
    "compliance", "bpmn", "melhoria continua", "ingles", "operacoes",
    "analise de dados", "planejamento", "orcamento", "auditoria", "riscos",
    "documentacao", "gestao de servicos", "itil", "cobit"
]

def normalize(value):
    value = unicodedata.normalize("NFKD", str(value).lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value)

def score_job(description):
    text = normalize(description)
    matched = [skill for skill in SKILLS if skill in text]
    missing = [skill for skill in SKILLS if skill not in text]
    # Score is the proportion of the profile skill vocabulary found in the vacancy.
    # It is deliberately conservative and is not a probability of being hired.
    score = round(100 * len(matched) / len(SKILLS))
    return score, matched, missing

def explain_match(score):
    return (
        "Indicador exploratório baseado em termos do perfil e da descrição. "
        "Não mede senioridade, contexto, qualidade da experiência nem chance real de contratação. "
        f"Pontuação lexical: {score}%."
    )
