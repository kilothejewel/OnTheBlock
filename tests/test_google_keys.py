"""One Google key per Cloud project (#44), falling back to the single key for local dev."""

from app.core.config import settings
from app.services.places import GooglePlacesService


def test_the_split_keys_are_used_when_set(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "single")
    monkeypatch.setattr(settings, "GOOGLE_DISPLAY_KEY", "display")
    monkeypatch.setattr(settings, "GOOGLE_LIVE_KEY", "live")
    service = GooglePlacesService()
    assert (service.api_key, service.live_key) == ("display", "live")


def test_without_them_the_single_key_is_used_for_everything(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_PLACES_API_KEY", "single")
    monkeypatch.setattr(settings, "GOOGLE_DISPLAY_KEY", None)
    monkeypatch.setattr(settings, "GOOGLE_LIVE_KEY", None)
    service = GooglePlacesService()
    assert (service.api_key, service.live_key) == ("single", "single")
