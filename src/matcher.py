import re
import unicodedata

WEIGHTS = {
    "excel": 3, "sap": 3, "contas a pagar": 2, "contas a receber": 2,
    "fornecedores": 2, "contratos": 2, "processos": 3, "indicadores": 3,
    "kpi": 3, "power bi": 3, "sql": 3, "python": 2, "pandas": 2,
    "gestao de projetos": 2, "governanca": 3, "controles internos": 3,
    "compliance": 2, "bpmn": 2, "melhoria continua": 3, "ingles": 2,
    "operacoes": 3, "analise de dados": 3, "planejamento": 2,
    "orcamento": 2, "auditoria": 2, "riscos": 2, "documentacao": 1,
    "gestao de servicos": 1, "itil": 1, "cobit": 1
}

def normalize(value):
    value=unicodedata.normalize("NFKD",str(value).lower())
    value="".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\\s+"," ",value)

def score_job(description):
    text=normalize(description)
    matched=[s for s in WEIGHTS if s in text]
    missing=[s for s in WEIGHTS if s not in text]
    total=sum(WEIGHTS.values())
    score=round(100*sum(WEIGHTS[s] for s in matched)/total) if total else 0
    return score,matched,missing

def explain_match(score):
    return f"Compatibilidade lexical ponderada: {score}%. Indicador exploratório, não representa chance de contratação."
