"""The cost model (#96): a per-person range for every Stop, from the evidence we have."""

import logging
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from app.core.cities import CITIES
from app.services import costs as costs_module
from app.services.costs import COSTS_DIR, CostFileError, Cost, estimate_stop, load_costs

REPO_ROOT = Path(__file__).resolve().parents[1]
CAPE_TOWN, MIAMI, TOKYO, DURBAN = CITIES["cape-town"], CITIES["miami"], CITIES["tokyo"], CITIES["durban"]
SOURCE = {"source_url": "https://example.com/menu", "checked_on": "2026-11-10"}


def cape_town_file(**sections):
    data = {
        "city": "cape-town",
        "currency": "ZAR",
        "fees": [
            {"key": "cableway", "name": "Cableway", "value": 475, "match_names": ["Table Mountain Aerial Cableway"], **SOURCE},
            {"key": "aquarium", "name": "Aquarium", "value": 250, "match_names": ["Two Oceans Aquarium"], "area": "va-waterfront", **SOURCE},
            {"key": "zeitz", "name": "Zeitz MOCAA", "value": 260, "place_id": "ChIJzeitz00001", **SOURCE},
            {"key": "kirstenbosch", "name": "Kirstenbosch", "value": None, "match_names": ["Kirstenbosch"], "todo": "TODO(cameron): fee", "source_url": "https://example.com"},
        ],
        "price_level_bands": {**SOURCE, "lunch": {0: None, 1: [60, 120], 2: [120, 220], 3: None, 4: None}, "nightlife": {2: [150, 300]}},
        "category_bands": {**SOURCE, "night_club": [100, 250], "museum": [0, 120], "bar": None},
        "defaults": {**SOURCE, "lunch": [100, 200], "nightlife": 200, "dinner": None},
        "e_hailing": {"todo": "later"},
        "parking": {"todo": "later"},
    }
    data.update(sections)
    return data


def default_file(**rows):
    return {
        "city": "_default", "currency": "USD", "fees": [],
        "price_level_bands": {**SOURCE, "dinner": {2: [20, 40]}},
        "category_bands": {"todo": "none yet"},
        "defaults": {**SOURCE, "lunch": [10, 20], **rows},
        "e_hailing": {"todo": "later"}, "parking": {"todo": "later"},
    }


def write(tmp_path, *files):
    for data in files:
        (tmp_path / f"{data['city']}.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return tmp_path


@pytest.fixture
def costs(tmp_path):
    return load_costs(write(tmp_path, cape_town_file(), default_file()))


def estimate(costs, place, slot="lunch", city=CAPE_TOWN):
    return estimate_stop(place, slot, city, costs=costs)


class TestEvidenceOrder:
    def test_1_fee_table_by_name(self, costs):
        assert estimate(costs, {"name": "Table Mountain Aerial Cableway"}, "activity") == Cost(480, 480, "fee_table")

    def test_1_fee_table_by_name_needs_the_area_when_the_row_has_one(self, costs):
        assert estimate(costs, {"name": "Two Oceans Aquarium", "area": "va-waterfront"}, "activity").basis == "fee_table"
        assert estimate(costs, {"name": "Two Oceans Aquarium", "area": "sea-point"}, "activity").basis != "fee_table"

    def test_1_fee_table_by_place_id_beats_google_prices(self, costs):
        place = {"google_place_id": "ChIJzeitz00001", "name": "Some museum", "confirmed": True, "price_level": 4,
                 "price_range": {"startPrice": {"currencyCode": "ZAR", "units": "900"}}}
        assert estimate(costs, place, "activity") == Cost(260, 260, "fee_table")

    def test_a_fee_row_without_a_price_falls_through(self, costs):
        assert estimate(costs, {"name": "Kirstenbosch Gardens", "categories": ["museum"]}, "activity") == Cost(0, 120, "category_band")

    def test_2_google_price_range_when_confirmed(self, costs):
        place = {"name": "Bistro", "confirmed": True, "price_level": 2, "price_range": {
            "startPrice": {"currencyCode": "ZAR", "units": "200"}, "endPrice": {"currencyCode": "ZAR", "units": "404"}}}
        assert estimate(costs, place) == Cost(200, 400, "google_price_range")

    def test_2_an_open_ended_range_uses_its_start(self, costs):
        place = {"confirmed": True, "price_range": {"startPrice": {"currencyCode": "ZAR", "units": "500"}}}
        assert estimate(costs, place) == Cost(500, 500, "google_price_range")

    def test_2_a_range_in_dollars_is_converted_and_logged(self, costs, caplog):
        place = {"confirmed": True, "price_range": {
            "startPrice": {"currencyCode": "USD", "units": "10"}, "endPrice": {"currencyCode": "USD", "units": "20", "nanos": 500000000}}}
        with caplog.at_level(logging.INFO, logger="app.services.costs"):
            assert estimate(costs, place) == Cost(180, 370, "google_price_range")
        assert any("converted a Google price range" in r.getMessage() for r in caplog.records)

    def test_2_a_range_in_a_currency_we_cant_convert_falls_through(self, costs):
        place = {"confirmed": True, "price_level": 1, "price_range": {"startPrice": {"currencyCode": "EUR", "units": "10"}}}
        assert estimate(costs, place).basis == "google_price_level"

    @pytest.mark.parametrize("level", [2, "PRICE_LEVEL_MODERATE"])
    def test_3_google_price_level_band_for_the_slot(self, costs, level):
        assert estimate(costs, {"confirmed": True, "price_level": level}) == Cost(120, 220, "google_price_level")

    def test_3_a_level_with_no_band_falls_through(self, costs):
        assert estimate(costs, {"confirmed": True, "price_level": 4}) == Cost(100, 200, "default")

    def test_4_category_band(self, costs):
        assert estimate(costs, {"name": "Club X", "categories": ["night_club"]}, "nightlife") == Cost(100, 250, "category_band")

    def test_a_club_with_no_google_price_data(self, costs):
        club = {"name": "Club X", "confirmed": True, "categories": ["night_club"]}  # live check found no price fields
        assert estimate(costs, club, "nightlife") == Cost(100, 250, "category_band")

    def test_an_unconfirmed_stop_ignores_google_prices(self, costs):
        """The live check was skipped (quota used): Google's fields aren't trusted for this Stop."""
        place = {"name": "Bistro", "confirmed": False, "price_level": 2, "categories": ["museum"],
                 "price_range": {"startPrice": {"currencyCode": "ZAR", "units": "200"}}}
        assert estimate(costs, place) == Cost(0, 120, "category_band")

    def test_5_slot_default(self, costs):
        assert estimate(costs, {"name": "Somewhere", "categories": ["bar"]}) == Cost(100, 200, "default")
        assert estimate(costs, {"name": "Somewhere"}, "nightlife") == Cost(200, 200, "default")

    def test_then_the_shared_file_as_a_rough_estimate(self, costs):
        """Cape Town has no dinner default: the shared USD file gives one, converted and marked."""
        assert estimate(costs, {"confirmed": True, "price_level": 2}, "dinner") == Cost(360, 720, "beta_estimate")

    def test_nothing_known_is_unknown_not_made_up(self, costs):
        assert estimate(costs, {"name": "Somewhere"}, "breakfast") == Cost(None, None, "unknown")


class TestBetaCities:
    def test_a_city_without_a_file_uses_the_shared_one_converted(self, costs):
        assert estimate(costs, {"name": "Diner"}, "lunch", city=MIAMI) == Cost(10, 20, "beta_estimate")
        assert estimate(costs, {"name": "Shokudo"}, "lunch", city=TOKYO) == Cost(1500, 3000, "beta_estimate")
        assert estimate(costs, {"name": "Bunny chow"}, "lunch", city=DURBAN) == Cost(180, 360, "beta_estimate")

    def test_the_shared_file_never_uses_another_citys_fees(self, costs):
        assert estimate(costs, {"name": "Table Mountain Aerial Cableway"}, "activity", city=MIAMI).basis == "unknown"


class TestRounding:
    @pytest.mark.parametrize("band, expected", [([64, 126], (60, 130)), ([0, 4], (0, 0)), ([85, 95], (90, 100)), ([12.4, 12.6], (10, 10))])
    def test_rands_are_whole_and_rounded_to_r10(self, tmp_path, band, expected):
        costs = load_costs(write(tmp_path, cape_town_file(defaults={**SOURCE, "lunch": band}), default_file()))
        cost = estimate(costs, {})
        assert (cost.min, cost.max) == expected
        assert all(isinstance(n, int) and n % 10 == 0 for n in (cost.min, cost.max))


class TestTheRealFiles:
    def test_they_load(self):
        assert {"cape-town", "_default"} <= set(load_costs())

    def test_every_stop_gets_a_known_basis_and_unknown_is_never_a_number(self):
        for slot in ("breakfast", "activity", "lunch", "dinner", "nightlife"):
            for city in CITIES.values():
                cost = estimate_stop({"name": "Somewhere"}, slot, city)
                assert cost.basis in costs_module.BASES
                assert (cost.min is None) == (cost.basis == "unknown")


class TestInvalidFiles:
    @pytest.mark.parametrize("change, message", [
        (lambda d: d["fees"][1].update(value=-5), "cape-town.yaml is invalid:\n  fees[aquarium].value"),
        (lambda d: d["fees"][0].pop("checked_on"), "fees[cableway]: Value error, has amounts but no source_url"),
        (lambda d: d["category_bands"].update(museum=[200, 100]), "category_bands: museum: needs 0 <= min <= max"),
        (lambda d: d["category_bands"].update(museum="cheap"), "category_bands: museum: expected [min, max]"),
        (lambda d: d["price_level_bands"].update(brunch={1: [1, 2]}), "price_level_bands: brunch: unknown Slot kind"),
        (lambda d: d["price_level_bands"]["lunch"].update({7: [1, 2]}), "price_level_bands: lunch: expected price levels 0-4"),
        (lambda d: d["defaults"].update(beach=[0, 0]), "defaults: beach: defaults are per Slot kind"),
        (lambda d: d["defaults"].pop("source_url"), "defaults: Value error, has amounts but no source_url"),
        (lambda d: d.update(currency=None), "currency: needed once the file has amounts"),
        (lambda d: d.update(surprise=1), "surprise: Extra inputs are not permitted"),
    ])
    def test_a_bad_row_names_the_file_and_row(self, tmp_path, change, message):
        data = cape_town_file()
        change(data)
        with pytest.raises(CostFileError) as exc:
            load_costs(write(tmp_path, data, default_file()))
        assert message.replace("Value error, ", "") in str(exc.value).replace("Value error, ", "")

    def test_the_file_name_must_match_a_city(self, tmp_path):
        (tmp_path / "atlantis.yaml").write_text(yaml.safe_dump({**cape_town_file(), "city": "atlantis"}), encoding="utf-8")
        with pytest.raises(CostFileError, match="'atlantis' isn't in app/data/cities.yaml"):
            load_costs(write(tmp_path, default_file()))

    def test_the_shared_file_is_required(self, tmp_path):
        with pytest.raises(CostFileError, match="_default.yaml is missing"):
            load_costs(write(tmp_path, cape_town_file()))

    def test_the_api_does_not_start_with_a_bad_file(self, tmp_path):
        data = cape_town_file()
        data["fees"][0]["value"] = "lots"
        write(tmp_path, data, default_file())
        code = (
            "import app.services.costs as c, pathlib, sys;"
            f"c.load_costs(pathlib.Path(r'{tmp_path}'))"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True)
        assert result.returncode != 0
        assert "fees[cableway].value" in result.stderr


def test_no_amounts_live_in_the_code():
    source = (REPO_ROOT / "app" / "services" / "costs.py").read_text(encoding="utf-8")
    assert "COSTS_DIR" in source and not any(word in source for word in ("475", "R120", "usd_rate *"))


PLAN = {"city": "cape-town", "budget": "$$", "duration_days": 1}


def test_demo_plans_keep_their_own_table(client, auth_headers):
    resp = client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers)
    assert resp.status_code == 200 and resp.json()["demo"] is True
    assert all(item.get("cost_basis") is None and item["estimated_cost"] > 0 for item in resp.json()["items"])


def test_live_plans_use_the_cost_model(client, auth_headers, monkeypatch, costs):
    from app.services import itinerary as itinerary_module

    monkeypatch.setattr(costs_module, "COSTS", costs)
    monkeypatch.setattr(itinerary_module.places_service, "api_key", "test-key")
    found = {
        "breakfast": {"google_place_id": "ChIJbreakfast001", "name": "Early Bird", "price_level": None},
        "lunch": {"google_place_id": "ChIJlunch0000001", "name": "Bistro", "price_level": 2},
        "dinner": {"google_place_id": "ChIJdinner000001", "name": "Grill", "price_level": 2},
    }

    async def fake_search(city, category, budget, max_results=5):
        return [found[category]]

    monkeypatch.setattr(itinerary_module.places_service, "search_places_for_slot", fake_search)
    resp = client.post("/api/v1/itineraries/generate", json=PLAN, headers=auth_headers)

    assert resp.status_code == 200, resp.text
    by_place = {i["location"]: i for i in resp.json()["items"]}
    assert (by_place["Bistro"]["cost_min"], by_place["Bistro"]["cost_max"], by_place["Bistro"]["cost_basis"]) == (120, 220, "google_price_level")
    assert by_place["Bistro"]["estimated_cost"] == 220
    assert by_place["Grill"]["cost_basis"] == "beta_estimate"
    early = by_place["Early Bird"]
    assert (early["cost_min"], early["cost_max"], early["cost_basis"], early["estimated_cost"]) == (None, None, "unknown", 0)
