from src.matcher import normalize, score_job
from collect_jobs import classify_location, classify_role, is_entry_level, keep_job, is_fresh_posting, has_conflicting_local_city, is_targeted_affirmative_vacancy

def test_normalize_accents():
    assert normalize("Governança e Gestão") == "governanca e gestao"

def test_score_detects_profile_skills():
    score, matched, missing, learning = score_job(
        "Experiência com Excel, SAP e Power BI."
    )
    assert "excel" in matched
    assert "sap" in matched
    assert "power bi" in matched
    assert score > 0

def test_transition_track_does_not_claim_full_match():
    score, matched, missing, learning = score_job(
        "Noções de ITIL e COBIT são desejáveis.", "Assistente de Governança",
        "Trilha de transição"
    )
    assert score <= 75
    assert "ITIL" in learning
    assert "COBIT" in learning

def test_only_brazil_confirmed_locations_are_eligible():
    assert classify_location("Remote - Brazil")[0] == "Brasil confirmado"
    assert classify_location("Curitiba, Brazil")[0] == "Brasil confirmado"
    assert classify_location("Worldwide")[0] == "Não elegível"
    assert classify_location("Remote")[0] == "Não elegível"
    assert classify_location("Kuala Lumpur, Malaysia")[0] == "Não elegível"

def test_role_groups_include_profile_and_transition():
    assert classify_role("Assistente Administrativo")[0] == "Perfil atual"
    assert classify_role("Assistente de Governança")[0] == "Trilha de transição"
    assert classify_role("IT Operations Assistant")[0] == "Trilha de transição"
    assert classify_role("Junior Governance Analyst")[0] == "Trilha de transição"
    assert classify_role("Junior IT Operations Analyst")[0] == "Trilha de transição"
    assert classify_role("IT Operations Coordinator")[0] == "Trilha de transição"
    assert classify_role("Analista de PMO Jr")[0] == "Trilha de transição"
    assert classify_role("Analista de Gestão de Serviços Jr")[0] == "Trilha de transição"
    assert classify_role("Analista de Projetos Jr")[0] == "Trilha de transição"
    assert classify_role("Data Analyst") == (None, None)

def test_entry_level_rules():
    assert is_entry_level("Assistente Administrativo", "Excel e SAP.")
    assert is_entry_level("Analista de Governança Jr", "Até 2 anos de experiência.")
    assert not is_entry_level("Analista de Governança", "Experiência mínima de 4 anos.")
    assert not is_entry_level("Senior IT Operations Analyst", "Experiência com ITIL.")

def test_keep_job_requires_all_filters():
    assert keep_job("Assistente Administrativo", "Curitiba, Brazil", "Excel")
    assert keep_job("Assistente de Governança", "Remote - Brazil", "Noções de ITIL")
    assert not keep_job("Assistente Administrativo", "Worldwide", "Excel")
    assert not keep_job("Senior Operations Analyst", "Curitiba, Brazil", "10 years")
    assert not keep_job("Data Analyst", "Remote - Brazil", "SQL")


def test_gupy_posting_freshness_and_city_conflicts():
    assert is_fresh_posting("2026-11-06T12:00:00Z")
    assert not is_fresh_posting("2025-12-12T12:00:00Z")
    assert has_conflicting_local_city("Assistente Administrativo - Londrina/PR")
    assert has_conflicting_local_city("Assistente Administrativo iPlace - Joinville/SC")
    assert not has_conflicting_local_city("Assistente Administrativo - Curitiba/PR")

def test_exclude_retail_and_cashier_roles():
    assert not is_entry_level("Assistente Administrativo de Loja", "Atendimento ao cliente e caixa.")


def test_exclude_exclusive_affirmative_vacancies():
    assert is_targeted_affirmative_vacancy(
        "ASSISTENTE ADMINISTRATIVO | EXCLUSIVA PARA PESSOAS COM DEFICIÊNCIA", ""
    )
    assert is_targeted_affirmative_vacancy(
        "Analista Administrativo Jr (Exclusivo PCD)", ""
    )
    assert is_targeted_affirmative_vacancy(
        "Assistente", "Esta é uma vaga afirmativa para pessoas negras."
    )
    assert not is_targeted_affirmative_vacancy(
        "Assistente Administrativo", "Todas as nossas vagas são elegíveis a pessoas com deficiência."
    )
    assert not is_targeted_affirmative_vacancy(
        "Assistente Administrativo", "Vaga aberta a todos os públicos, inclusive PCD."
    )
    assert not keep_job(
        "ASSISTENTE ADMINISTRATIVO | EXCLUSIVA PARA PESSOAS COM DEFICIÊNCIA",
        "Curitiba, Paraná", "Rotinas de compras."
    )


def test_extract_benefits_from_description_sections():
    from collect_jobs import extract_benefits

    marista_like = (
        "Responsabilidades e atribuições: acompanhar cursos. "
        "Informações adicionais: "
        "O que oferecemos: Plano de saúde, vale-refeição, "
        "vale-transporte, seguro de vida e bolsa de estudos. "
        "Requisitos e qualificações: Ensino superior cursando."
    )
    result = extract_benefits({}, marista_like).lower()
    assert "plano de saúde" in result
    assert "vale-refeição" in result
    assert "seguro de vida" in result

    explicit_header = (
        "Atividades da vaga. Benefícios: Plano odontológico; "
        "Vale alimentação; Gympass. Requisitos: Excel."
    )
    result = extract_benefits({}, explicit_header).lower()
    assert "plano odontológico" in result
    assert "vale alimentação" in result
    assert "gympass" in result

    no_benefits = "Responsabilidades: organizar documentos. Requisitos: Excel."
    assert extract_benefits({}, no_benefits) == ""


def test_extract_marista_style_benefits_heading():
    from collect_jobs import extract_benefits

    description = (
        "Informações adicionaisO que vai encontrar por aqui: "
        "Plano de Saúde Unimed; Plano Odontológico OdontoPrev; "
        "Incentivo à Educação; Vale-refeição; Previdência Privada; "
        "Seguro de Vida; Vale Transporte; Wellhub; Zenklub. "
        "Salário: a combinar. Horário: segunda a sexta."
    )
    result = extract_benefits({}, description).lower()
    assert "unimed" in result
    assert "odontoprev" in result
    assert "vale-refeição" in result
    assert "wellhub" in result
    assert "zenklub" in result
    assert "salário:" not in result


def test_extract_benefits_when_gupy_removes_spaces_between_headings():
    from collect_jobs import extract_benefits

    description = (
        "Informações adicionaisO que vai encontrar por aqui: "
        "Plano de Saúde Unimed; Plano Odontológico OdontoPrev; "
        "Incentivo à Educação; Vale-refeição; Previdência Privada; "
        "Seguro de Vida; Vale Transporte; Wellhub; Zenklub: "
        "duas consultas ao mêsPrograma Conte Comigo: suporte. "
        "Clube de Vantagens: descontos especiaisSalário: a combinarHorário: "
        "segunda a sextaLocal: Curitiba"
    )
    result = extract_benefits({}, description).lower()
    assert "unimed" in result
    assert "odontoprev" in result
    assert "vale-refeição" in result
    assert "wellhub" in result
    assert "zenklub" in result
    assert "salário:" not in result
    assert "curitiba" not in result
