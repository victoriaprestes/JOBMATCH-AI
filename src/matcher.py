import re
import unicodedata

PROFILE_WEIGHTS = {
    "excel": 4, "sap": 4, "contas a pagar": 3, "contas a receber": 3,
    "fornecedores": 3, "compras": 3, "contratos": 3, "suporte a diretoria": 3,
    "administrativo": 3, "operacoes": 3, "processos": 3, "indicadores": 3,
    "kpi": 3, "mes": 2, "5s": 2, "kanban": 2, "melhoria continua": 2,
    "power bi": 2, "sql": 2, "python": 2, "ingles": 2,
    "controles internos": 1, "gestao de projetos": 1,
}
LEARNING_TERMS = {
    "governanca": "Governança", "it governance": "Governança de TI",
    "itil": "ITIL", "cobit": "COBIT", "itsm": "IT Service Management",
    "gestao de servicos": "Gestão de serviços", "gestao de riscos": "Gestão de riscos",
    "compliance": "Compliance", "auditoria": "Auditoria", "bpmn": "BPMN",
    "gestao de mudancas": "Gestão de mudanças", "service delivery": "Service Delivery",
    "gestao de ti": "Gestão de TI", "controles internos": "Controles internos",
}

def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value)

def score_job(description, title="", role_group="Perfil atual"):
    text = normalize(f"{title} {description}")
    matched = [skill for skill in PROFILE_WEIGHTS if skill in text]
    missing = [skill for skill in PROFILE_WEIGHTS if skill not in text]
    total = sum(PROFILE_WEIGHTS.values())
    score = round(100 * sum(PROFILE_WEIGHTS[s] for s in matched) / total) if total else 0
    learning = [label for term, label in LEARNING_TERMS.items() if term in text]
    if role_group == "Trilha de transição":
        score = min(score, 75)
    return score, matched, missing, learning

def explain_match(score, role_group="Perfil atual"):
    if role_group == "Trilha de transição":
        return (
            f"Aderência transferível: {score}%. Esta vaga pertence à trilha de transição; "
            "os conhecimentos específicos da área devem ser desenvolvidos e conferidos nos requisitos. "
            "A pontuação não representa chance de contratação."
        )
    return (
        f"Aderência lexical estimada: {score}%. Considera competências associadas à sua experiência "
        "administrativa, financeira e operacional. Não representa probabilidade de contratação."
    )
