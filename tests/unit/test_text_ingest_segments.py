import json

from rag_document_processor.application.use_cases.ingestion.process_job import texts_from_source_text


def test_texts_from_source_text_json_list() -> None:
    payload = json.dumps(["alpha", "beta"], ensure_ascii=False)
    assert texts_from_source_text(payload) == ["alpha", "beta"]


def test_texts_from_source_text_legacy_joined_string() -> None:
    legacy = "alpha\n\nbeta"
    assert texts_from_source_text(legacy) == ["alpha\n\nbeta"]


def test_texts_from_source_text_empty() -> None:
    assert texts_from_source_text(None) == [""]
    assert texts_from_source_text("") == [""]
    assert texts_from_source_text("[]") == [""]
