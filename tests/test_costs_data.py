"""The curated cost data (#95): every number has a source and a recent date, and nothing is guessed."""

import warnings
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

COSTS = Path(__file__).resolve().parents[1] / "app" / "data" / "costs"
META = ("todo", "source_url", "checked_on")


class StaleCostData(UserWarning):
    """A curated price that should be re-checked."""


SECTIONS = ("price_level_bands", "category_bands", "defaults", "e_hailing", "parking")


def load(name):
    return yaml.safe_load((COSTS / name).read_text(encoding="utf-8"))


def numbers(value):
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, list):
        return [n for v in value for n in numbers(v)]
    if isinstance(value, dict):
        return [n for k, v in value.items() if k not in META for n in numbers(v)]
    return []


def recent(checked_on):
    """
    A real check date, not in the future. Older than 3 months is a warning
    rather than a failure, so a price going stale never breaks unrelated PRs;
    the warning shows in every test run until someone re-checks it.
    """
    if not isinstance(checked_on, date) or checked_on > date.today():
        return False
    if checked_on < date.today() - timedelta(days=92):
        warnings.warn(f"cost data checked on {checked_on} is over 3 months old: re-check it (#95)", StaleCostData)
    return True


@pytest.mark.parametrize("name", ["cape-town.yaml", "_default.yaml"])
def test_every_section_is_present(name):
    assert {"city", "currency", "fees", *SECTIONS} <= set(load(name))


def test_every_fee_has_a_source_and_a_price_only_with_a_recent_date():
    for fee in load("cape-town.yaml")["fees"]:
        assert fee["source_url"].startswith("https://"), fee["key"]
        if fee["value"] is None:
            assert str(fee.get("todo", "")).startswith("TODO(cameron)"), f"{fee['key']}: an unknown value needs a TODO"
        else:
            assert fee["value"] >= 0
            assert recent(fee["checked_on"]), f"{fee['key']}: a price needs a checked_on date"


@pytest.mark.parametrize("section", SECTIONS)
def test_sections_have_amounts_only_with_a_source_and_date(section):
    rows = load("cape-town.yaml")[section]
    if numbers(rows):
        assert rows["source_url"] and recent(rows["checked_on"]), f"{section} has amounts without a recent source"
    else:
        assert str(rows["todo"]).startswith("TODO(cameron)")


def test_bands_are_min_max_pairs():
    for section in ("price_level_bands", "category_bands"):
        for key, value in load("cape-town.yaml")[section].items():
            if key in META:
                continue
            for band in (value.values() if isinstance(value, dict) else [value]):
                assert band is None or (len(band) == 2 and 0 <= band[0] <= band[1]), f"{section}.{key}: {band}"


def test_parking_areas_exist():
    areas = {a["slug"] for a in yaml.safe_load((COSTS.parent / "areas" / "cape-town.yaml").read_text(encoding="utf-8"))["areas"]}
    parking = {k for k in load("cape-town.yaml")["parking"] if k not in META}
    assert parking <= areas


def test_the_default_file_guesses_nothing():
    data = load("_default.yaml")
    assert data["fees"] == []
    assert all(numbers(data[section]) == [] for section in SECTIONS)


def test_the_cableway_price_is_the_one_checked():
    [cableway] = [f for f in load("cape-town.yaml")["fees"] if f["key"] == "table-mountain-cableway"]
    assert cableway["value"] == 475 and cableway["checked_on"] == date(2026, 11, 16)
