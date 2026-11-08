from src.matcher import normalize, score_job
from collect_jobs import classify_location, classify_role, is_entry_level, keep_job

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
