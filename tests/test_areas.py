"""Areas per city (#35): the data files, the loader and GET /cities/{slug}/areas."""

from dataclasses import replace

import pytest
import yaml

from app.core import cities as cities_module
from app.core.cities import CITIES, get_city, visible_cities
from app.services.areas import AreasFileError, area_at, areas_for, find_area, load_areas


def test_cape_town_has_10_to_15_areas():
    assert 10 <= len(areas_for("cape-town")) <= 15


@pytest.mark.parametrize("city", [c.slug for c in visible_cities()])
def test_every_visible_city_has_at_least_4_areas_inside_its_bounds(city):
    areas = areas_for(city)
    assert len(areas) >= 4
    assert all(get_city(city).contains(a.lat, a.lng) for a in areas)


def test_every_area_is_a_draft_until_a_local_reviews_it():
    """reviewed: true is Cameron's to set (#35); nothing is marked checked by the draft."""
    assert all(not a.reviewed for city in CITIES for a in areas_for(city))


def test_night_safe_is_never_assumed_in_south_africa_except_the_waterfront():
    night_safe = {a.slug for c in CITIES.values() if c.is_south_african for a in areas_for(c.slug) if a.night_safe}
    assert night_safe == {"va-waterfront"}


@pytest.mark.parametrize("text, slug", [
    ("Obs", "observatory"), ("the Waterfront", "va-waterfront"), ("bo-kaap", "bo-kaap"), ("Kalk Bay", "kalk-bay"),
    ("Lion's Head", "kirstenbosch"), ("Long Street", "city-bowl"), ("CAMPS BAY", "camps-bay"),
])
def test_areas_are_found_by_name_or_alias(text, slug):
    assert find_area("cape-town", text).slug == slug


def test_unknown_names_find_nothing():
    assert find_area("cape-town", "Atlantis") is None


def test_a_point_is_in_the_nearest_area_that_covers_it():
    assert area_at("cape-town", -34.1270, 18.4470).slug == "kalk-bay"
    assert area_at("cape-town", -33.9046, 18.4190).slug == "va-waterfront"
    assert area_at("cape-town", -33.80, 18.70) is None


def test_a_city_without_an_areas_file_has_none():
    assert load_areas(replace(get_city("durban"), areas_file="areas/not-yet.yaml")) == []


@pytest.mark.parametrize("change, message", [
    (lambda d: d["areas"][0].update(radius_m=0), "radius_m"),
    (lambda d: d["areas"][0].update(centre={"lat": -26.2, "lng": 28.0}), "outside Cape Town's bounds: city-bowl"),
    (lambda d: d["areas"].append(dict(d["areas"][0])), "duplicate Area slugs: city-bowl"),
    (lambda d: d["areas"][0].update(safety="ok"), "Extra inputs are not permitted"),
])
def test_an_invalid_areas_file_fails_clearly(tmp_path, change, message):
    data = yaml.safe_load(get_city("cape-town").areas_path.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "cape-town.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(AreasFileError, match=message):
        load_areas(get_city("cape-town"), path)


class TestEndpoint:
    def test_returns_a_citys_areas(self, client):
        resp = client.get("/api/v1/cities/cape-town/areas")
        assert resp.status_code == 200
        areas = resp.json()
        assert len(areas) == len(areas_for("cape-town"))
        waterfront = next(a for a in areas if a["slug"] == "va-waterfront")
        assert waterfront["night_safe"] is True and waterfront["reviewed"] is False
        assert "Waterfront" in waterfront["aliases"]

    def test_is_open_without_signing_in(self, client):
        assert client.get("/api/v1/cities/durban/areas").status_code == 200

    def test_an_unknown_city_is_a_404(self, client):
        resp = client.get("/api/v1/cities/paris/areas")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "We don't plan in that city yet."

    def test_a_hidden_city_is_a_404(self, client, monkeypatch):
        changed = dict(CITIES)
        changed["durban"] = replace(CITIES["durban"], launch_status="hidden")
        monkeypatch.setattr(cities_module, "CITIES", changed)
        from app.routers import cities as cities_router
        monkeypatch.setattr(cities_router, "CITIES", changed)
        assert client.get("/api/v1/cities/durban/areas").status_code == 404
