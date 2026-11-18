from app.checklist import LLM_CHECKS, REQUIRED_SECTIONS


def test_required_sections_have_keywords():
    for name, keywords in REQUIRED_SECTIONS:
        assert name and keywords


def test_llm_check_ids_unique():
    ids = [cid for cid, _ in LLM_CHECKS]
    assert len(ids) == len(set(ids))
