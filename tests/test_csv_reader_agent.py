import pytest
import pandas as pd
from unittest.mock import patch
from agents.csv_reader_agent import CSVReaderAgent


@pytest.fixture
def agent():
    return CSVReaderAgent()


def test_read_all_returns_35_items(agent):
    items = agent.read_all()
    assert len(items) == 35


def test_read_all_returns_20_reviews(agent):
    items = agent.read_all()
    reviews = [i for i in items if i["source_type"] == "review"]
    assert len(reviews) == 20


def test_read_all_returns_15_emails(agent):
    items = agent.read_all()
    emails = [i for i in items if i["source_type"] == "email"]
    assert len(emails) == 15


def test_each_item_has_required_keys(agent):
    for item in agent.read_all():
        assert "id" in item
        assert "source_type" in item
        assert "text" in item
        assert "metadata" in item


def test_review_metadata_has_platform_and_rating(agent):
    items = agent.read_all()
    reviews = [i for i in items if i["source_type"] == "review"]
    for r in reviews:
        assert "platform" in r["metadata"]
        assert "rating" in r["metadata"]
        assert r["metadata"]["platform"] in ("Google Play", "App Store")
        assert 1 <= r["metadata"]["rating"] <= 5


def test_email_metadata_has_subject_and_sender(agent):
    items = agent.read_all()
    emails = [i for i in items if i["source_type"] == "email"]
    for e in emails:
        assert "subject" in e["metadata"]
        assert "sender_email" in e["metadata"]


def test_results_sorted_by_source_type_then_id(agent):
    items = agent.read_all()
    source_types = [i["source_type"] for i in items]
    assert source_types == sorted(source_types)


def test_email_text_includes_subject(agent):
    items = agent.read_all()
    emails = [i for i in items if i["source_type"] == "email"]
    for e in emails:
        assert e["metadata"]["subject"] in e["text"]


def test_review_ids_start_with_r(agent):
    items = agent.read_all()
    reviews = [i for i in items if i["source_type"] == "review"]
    for r in reviews:
        assert r["id"].startswith("R")


def test_email_ids_start_with_e(agent):
    items = agent.read_all()
    emails = [i for i in items if i["source_type"] == "email"]
    for e in emails:
        assert e["id"].startswith("E")


def test_no_empty_text(agent):
    for item in agent.read_all():
        assert item["text"].strip() != ""


def test_missing_reviews_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("agents.csv_reader_agent.REVIEWS_FILE", str(tmp_path / "missing.csv"))
    with pytest.raises(Exception):
        CSVReaderAgent().read_all()
