from src.matcher import normalize, score_job

def test_normalize_accents():
    assert normalize("Governança e Gestão") == "governanca e gestao"

def test_score_detects_skills():
    score, matched, missing = score_job("Experiência com Excel, SAP e Power BI.")
    assert "excel" in matched
    assert "sap" in matched
    assert "power bi" in matched
    assert score > 0
