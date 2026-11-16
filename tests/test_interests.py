"""The Interest taxonomy (#86): app/data/interests.yaml, checked against pinned category lists."""

import csv
from pathlib import Path

import pytest
import yaml

from app.services.interests import INTERESTS, INTERESTS_FILE, InterestsFileError, load_interests, match_interests, wants_slot

TAXONOMY = Path(__file__).resolve().parents[1] / "app" / "data" / "taxonomy"
LAUNCH_INTERESTS = [
    "nature", "hiking", "beach", "wine", "food", "coffee", "markets", "art", "history", "museums",
    "live_music", "clubbing", "bars", "rooftop", "shopping", "adventure", "family", "sport",
]


def _lines(name):
    return {line.strip() for line in (TAXONOMY / name).read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}


GOOGLE_TABLE_A = _lines("google_place_types_table_a.txt")
OVERTURE = _lines("overture_categories.txt")
FSQ = {row["category_id"]: row for row in csv.DictReader(open(TAXONOMY / "fsq_os_places_categories.csv", encoding="utf-8"))}


def keys(text):
    return [key for key, _ in match_interests(text)]


class TestFile:
    def test_has_every_launch_interest(self):
        assert set(LAUNCH_INTERESTS) <= set(INTERESTS)

    def test_the_pinned_lists_are_complete(self):
        # Guards against a truncated copy: the sizes of the pinned releases.
        assert len(GOOGLE_TABLE_A) == 478
        assert len(OVERTURE) == 2302
        assert len(FSQ) == 1279

    @pytest.mark.parametrize("key", sorted(INTERESTS))
    def test_every_google_type_is_in_table_a(self, key):
        unknown = [t for t in INTERESTS[key].included_types if t not in GOOGLE_TABLE_A]
        assert unknown == [], f"{key}: not Places API (New) Table A types: {unknown}"

    @pytest.mark.parametrize("key", sorted(INTERESTS))
    def test_every_overture_category_is_in_the_taxonomy(self, key):
        unknown = [c for c in INTERESTS[key].overture_categories if c not in OVERTURE]
        assert unknown == [], f"{key}: not Overture categories: {unknown}"

    @pytest.mark.parametrize("key", sorted(INTERESTS))
    def test_every_foursquare_id_is_a_category(self, key):
        unknown = [c for c in INTERESTS[key].fsq_category_ids if c not in FSQ]
        assert unknown == [], f"{key}: not Foursquare OS Places category ids: {unknown}"

    def test_the_comment_next_to_each_foursquare_id_is_its_category(self):
        for line in INTERESTS_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith('- "') and "#" in line:
                category_id = line.split('"')[1]
                assert line.split("#", 1)[1].strip() == FSQ[category_id]["category_label"]

    @pytest.mark.parametrize("change, message", [
        (lambda d: d["interests"]["nature"].pop("description"), "nature.description: Field required"),
        (lambda d: d["interests"]["bars"].update(time_of_day=["midnight"]), "bars.time_of_day.0"),
        (lambda d: d["interests"]["wine"].update(slot_kinds=["brunch"]), "wine.slot_kinds.0"),
        (lambda d: d["interests"]["food"].update(colour="red"), "food.colour: Extra inputs are not permitted"),
        (lambda d: d["interests"].update({"Live Music": d["interests"]["live_music"]}), "Live Music: keys are lower_snake_case"),
    ])
    def test_an_invalid_file_fails_with_a_clear_error(self, tmp_path, change, message):
        data = yaml.safe_load(INTERESTS_FILE.read_text(encoding="utf-8"))
        change(data)
        path = tmp_path / "interests.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(InterestsFileError) as error:
            load_interests(path)
        assert message in str(error.value)

    def test_clubbing_is_late_night_and_needs_fewer_reviews(self):
        clubbing = INTERESTS["clubbing"]
        assert clubbing.time_of_day == ("late_night",)
        assert clubbing.slot_kinds == ("nightlife",)
        assert clubbing.min_reviews == 15
        assert INTERESTS["nature"].outdoor and not clubbing.outdoor


class TestMatching:
    def test_nature_and_clubbing(self):
        assert keys("I love nature and want to go clubbing") == ["nature", "clubbing"]

    @pytest.mark.parametrize("text", ["barbecue", "a barbecue lunch", "Barbarella's", "embargo"])
    def test_whole_words_only_so_barbecue_is_not_bars(self, text):
        assert "bars" not in keys(text)

    @pytest.mark.parametrize("text, expected", [
        ("wine farms in Stellenbosch", "wine"),
        ("a jol on Saturday", "clubbing"),
        ("amapiano and house music", "clubbing"),
        ("braai and shisa nyama", "food"),
        ("Lion's Head at sunrise", "hiking"),
        ("rooftop sundowners", "rooftop"),
        ("live music", "live_music"),
        ("something for the kids", "family"),
        ("watch the Springboks", "sport"),
        ("Street-art walk in Woodstock", "art"),
        ("FLAT WHITES", "coffee"),
    ])
    def test_south_african_and_everyday_words(self, text, expected):
        assert expected in keys(text)

    def test_plurals_and_hyphens(self):
        assert "beach" in keys("beaches")
        assert "museums" in keys("museums")
        assert "art" in keys("street art") and "art" in keys("street-art")

    def test_weights_rank_the_most_mentioned_first(self):
        result = match_interests("coffee, more coffee, then a museum")
        assert result[0] == ("coffee", 1.0)
        assert ("museums", 0.5) in result

    def test_place_names_are_not_interests(self):
        # Cape Town Areas that contain everyday words.
        assert keys("dinner in Green Point") == ["food"]
        assert keys("a walk along Sea Point") == ["hiking"]

    @pytest.mark.parametrize("text", ["", "   ", None, "surprise me"])
    def test_no_interests(self, text):
        assert match_interests(text) == []

    def test_wants_slot(self):
        assert wants_slot("food, nightlife", "nightlife")
        assert wants_slot("cocktails", "nightlife")
        assert not wants_slot("barbecue", "nightlife")
        assert not wants_slot("museums and hiking", "nightlife")
