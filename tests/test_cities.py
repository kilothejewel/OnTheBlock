"""The city registry (app/data/cities.yaml, #85): loading, validation, bounds and GET /cities."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from app.core import cities as cities_module
from app.core.cities import CITIES, CITIES_FILE, CityRegistryError, city_at, get_city, load_cities, visible_cities
from app.services.demo_places import demo_slot

REPO_ROOT = Path(__file__).resolve().parents[1]
SA_CITIES = ["cape-town", "johannesburg", "durban", "pretoria", "stellenbosch"]


def registry_with(tmp_path, change):
    """A copy of the real registry with `change(data)` applied, written to a temp file."""
    data = yaml.safe_load(CITIES_FILE.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "cities.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


class TestRegistry:
    def test_every_city_loads(self):
        assert list(CITIES) == SA_CITIES + ["miami", "london", "tokyo"]
        for slug in SA_CITIES:
            city = get_city(slug)
            assert (city.country_code, city.currency, city.timezone) == ("ZA", "ZAR", "Africa/Johannesburg")
            assert city.launch_status == "beta"
            assert city.areas_file == f"areas/{slug}.yaml"

    def test_international_cities_keep_their_currency_and_are_beta(self):
        assert {slug: (get_city(slug).currency, get_city(slug).launch_status) for slug in ("miami", "london", "tokyo")} == {
            "miami": ("USD", "beta"), "london": ("GBP", "beta"), "tokyo": ("JPY", "beta"),
        }

    def test_a_missing_areas_file_is_allowed_for_now(self):
        """#35 adds the Areas files; until then a city's areas_path is just None."""
        city = _with(get_city("durban"), areas_file="areas/not-written-yet.yaml")
        assert city.areas_path is None

    @pytest.mark.parametrize("change, message", [
        (lambda d: d["cities"][0].pop("timezone"), "city cape-town.timezone: Field required"),
        (lambda d: d["cities"][1].update(timezone="Africa/Joburg"), "city johannesburg: Value error, unknown time zone 'Africa/Joburg'"),
        (lambda d: d["cities"][2].update(launch_status="soon"), "city durban.launch_status"),
        (lambda d: d["cities"][0]["bounds"].update(sw={"lat": -33.0, "lng": 18.3}), "city cape-town.bounds: Value error, sw must be south-west of ne"),
        (lambda d: d["cities"][3].update(centre={"lat": -33.9, "lng": 18.4}), "city pretoria: Value error, centre must be inside bounds"),
        (lambda d: d["cities"][0].update(currency="rand"), "city cape-town.currency"),
        (lambda d: d["cities"][0].update(colour="red"), "city cape-town.colour: Extra inputs are not permitted"),
        (lambda d: d["cities"].append(dict(d["cities"][0])), "duplicate slug cape-town"),
        (lambda d: d.update(cities=[]), "cities: List should have at least 1 item"),
    ])
    def test_an_invalid_registry_fails_with_a_clear_error(self, tmp_path, change, message):
        with pytest.raises(CityRegistryError) as error:
            load_cities(registry_with(tmp_path, change))
        assert message in str(error.value)

    def test_unreadable_files_fail_clearly(self, tmp_path):
        with pytest.raises(CityRegistryError, match="is missing"):
            load_cities(tmp_path / "nope.yaml")
        broken = tmp_path / "broken.yaml"
        broken.write_text("cities: [\n", encoding="utf-8")
        with pytest.raises(CityRegistryError, match="isn't valid YAML"):
            load_cities(broken)

    def test_the_api_does_not_start_with_an_invalid_registry(self, tmp_path):
        """Importing the app loads the registry, so a broken file stops startup with the reason."""
        bad = registry_with(tmp_path, lambda d: d["cities"][0].update(timezone="Mars/Olympus"))
        script = (
            "import pathlib, app.core.cities as c\n"
            f"c.load_cities(pathlib.Path({str(bad)!r}))\n"
        )
        result = subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True)
        assert result.returncode != 0
        assert "CityRegistryError" in result.stderr
        assert "unknown time zone 'Mars/Olympus'" in result.stderr


class TestBounds:
    @pytest.mark.parametrize("place, lat, lng, slug", [
        ("Sandton", -26.1046, 28.0545, "johannesburg"),
        ("Soweto", -26.2485, 27.8540, "johannesburg"),
        ("Centurion", -25.8364, 28.1803, "pretoria"),
        ("Hatfield", -25.7490, 28.2386, "pretoria"),
        ("Bo-Kaap", -33.9205, 18.4155, "cape-town"),
        ("Muizenberg", -34.1083, 18.4695, "cape-town"),
        ("Stellenbosch town", -33.9344, 18.8692, "stellenbosch"),
        ("Umhlanga", -29.7262, 31.0844, "durban"),
        ("Shoreditch", 51.5260, -0.0780, "london"),
    ])
    def test_a_point_is_in_the_right_city(self, place, lat, lng, slug):
        assert city_at(lat, lng).slug == slug, place

    def test_sandton_is_in_johannesburg_not_pretoria(self):
        assert get_city("johannesburg").contains(-26.1046, 28.0545)
        assert not get_city("pretoria").contains(-26.1046, 28.0545)

    @pytest.mark.parametrize("lat, lng", [(-28.7, 24.7), (0, 0), (-33.0, 18.0)])  # Kimberley, Null Island, the Atlantic
    def test_a_point_outside_every_city_is_in_none(self, lat, lng):
        assert city_at(lat, lng) is None


class TestCitiesEndpoint:
    def test_lists_visible_cities_south_africa_first(self, client):
        resp = client.get("/api/v1/cities")
        assert resp.status_code == 200
        cities = resp.json()
        assert [c["slug"] for c in cities] == SA_CITIES + ["miami", "london", "tokyo"]
        assert cities[0] == {
            "slug": "cape-town", "name": "Cape Town", "province": "Western Cape",
            "country_code": "ZA", "currency": "ZAR", "status": "beta",
        }
        assert all(c["status"] == "beta" for c in cities if c["country_code"] != "ZA")

    def test_is_open_without_signing_in(self, client):
        assert client.get("/api/v1/cities").status_code == 200

    def test_live_cities_come_before_beta_ones_and_hidden_ones_are_left_out(self, client, monkeypatch):
        changed = dict(CITIES)
        changed["durban"] = _with(CITIES["durban"], launch_status="live")
        changed["pretoria"] = _with(CITIES["pretoria"], launch_status="hidden")
        changed["london"] = _with(CITIES["london"], launch_status="live")
        monkeypatch.setattr(cities_module, "CITIES", changed)

        slugs = [c["slug"] for c in client.get("/api/v1/cities").json()]
        assert slugs == ["durban", "cape-town", "johannesburg", "stellenbosch", "london", "miami", "tokyo"]
        assert [c.slug for c in visible_cities()] == slugs


def _with(city, **changes):
    from dataclasses import replace
    return replace(city, **changes)


class TestHiddenCities:
    @pytest.fixture
    def durban_hidden(self, monkeypatch):
        changed = dict(CITIES)
        changed["durban"] = _with(CITIES["durban"], launch_status="hidden")
        monkeypatch.setattr(cities_module, "CITIES", changed)

    def test_planning_in_a_hidden_city_is_refused(self, client, auth_headers, durban_hidden):
        resp = client.post("/api/v1/itineraries/generate", json={"city": "durban", "budget": "$", "duration_days": 1}, headers=auth_headers)
        assert resp.status_code == 422
        assert "isn't open for planning yet" in resp.text

    def test_searching_a_hidden_city_is_refused(self, client, auth_headers, durban_hidden):
        resp = client.get("/api/v1/hotspots/recommend?query=bunny%20chow&city=durban", headers=auth_headers)
        assert resp.status_code == 422

    def test_a_saved_plan_in_a_hidden_city_still_opens(self, client, auth_headers, durban_hidden):
        saved = client.post("/api/v1/itineraries/", headers=auth_headers, json={
            "title": "Durban day", "destination": "Durban", "budget": "$", "city": "durban",
            "items": [{"day": 1, "activity": "Beach"}],
        })
        assert saved.status_code == 201, saved.text
        assert client.get(f"/api/v1/itineraries/{saved.json()['id']}", headers=auth_headers).json()["city"] == "durban"

    def test_an_unknown_city_is_refused(self, client, auth_headers):
        resp = client.post("/api/v1/itineraries/generate", json={"city": "paris", "budget": "$", "duration_days": 1}, headers=auth_headers)
        assert resp.status_code == 422


@pytest.mark.parametrize("slug", list(CITIES))
def test_every_city_has_demo_places_for_every_slot(slug):
    city = get_city(slug)
    for slot in ("breakfast", "activity", "nightlife"):
        assert demo_slot(city, slot), f"{slug} has no Demo place for {slot}"
    assert len(demo_slot(city, "lunch")) >= 2, f"{slug} needs two food places so lunch and dinner differ"


@pytest.mark.parametrize("slug", SA_CITIES)
def test_a_demo_plan_works_in_every_south_african_city(client, auth_headers, slug):
    resp = client.post("/api/v1/itineraries/generate", json={"city": slug, "budget": "$$", "duration_days": 1, "preferences": "nightlife"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["destination"] == get_city(slug).name
