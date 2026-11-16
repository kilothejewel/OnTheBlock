"""app/data/sources.yaml (ADR 0007, #111): every source is complete and credited in the web footer."""

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
SOURCES = yaml.safe_load((REPO / "app" / "data" / "sources.yaml").read_text(encoding="utf-8"))["sources"]
FIELDS = {"key", "name", "use", "credit", "url", "licence", "licence_url", "release", "we_store"}


def test_every_source_named_in_adr_0007_is_listed():
    keys = {source["key"] for source in SOURCES}
    assert {"overture_places", "foursquare_os_places", "wikivoyage", "wikipedia", "curated", "google_places", "open_meteo"} <= keys
    assert len(keys) == len(SOURCES)


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s["key"])
def test_every_source_has_a_licence_url_and_release(source):
    assert set(source) == FIELDS
    assert all(str(source[field]).strip() for field in FIELDS)
    assert source["url"].startswith("https://") and source["licence_url"].startswith("https://")


def test_reddit_and_paid_web_search_are_not_sources():
    text = " ".join(str(value).lower() for source in SOURCES for value in source.values())
    assert "reddit" not in text
    assert "web search" not in text


def test_every_outside_credit_is_in_the_web_footer():
    footer = (REPO / "web" / "src" / "components" / "AppShell.jsx").read_text(encoding="utf-8")
    credits = {source["credit"] for source in SOURCES if source["key"] != "curated"}
    missing = [credit for credit in credits if f"name: '{credit}'" not in footer]
    assert missing == []
