"""The Brief schema (#87): readable validation, apply_patch, and the endpoints."""

from datetime import date, datetime, time, timezone

import pytest
from pydantic import ValidationError

from app.schemas import brief as brief_module
from app.schemas.brief import Brief, BriefError, BriefPatch, apply_patch

TODAY = date(2026, 11, 20)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    # 21:30 UTC on 19 Nov is already 20 Nov in Cape Town (UTC+2).
    monkeypatch.setattr(brief_module, "utc_now", lambda: datetime(2026, 11, 19, 22, 30, tzinfo=timezone.utc))


def make(**fields):
    return Brief.model_validate({"city": "cape-town", "date": TODAY.isoformat(), **fields})


def messages(**fields):
    with pytest.raises(ValidationError) as error:
        make(**fields)
    return " ".join(e["msg"] for e in error.value.errors())


class TestValidation:
    def test_a_minimal_brief_gets_its_defaults(self):
        brief = make()
        assert (brief.mode, brief.party_size, brief.budget_basis, brief.transport, brief.pace) == ("day", 1, "per_person", "e_hailing", "relaxed")
        assert brief.window() == (time(9, 0), time(18, 0))

    def test_today_is_the_citys_today(self):
        # Still 19 Nov in UTC, but the Plan is for Cape Town, where it's the 20th.
        assert make().date == TODAY
        assert "has already passed in Cape Town" in messages(date="2026-11-19")

    def test_a_date_in_the_past_is_rejected_readably(self):
        assert "01 November 2026 has already passed in Cape Town" in messages(date="2026-11-01")

    def test_at_most_14_days_ahead(self):
        assert make(date="2026-12-04").date == date(2026, 12, 4)
        assert "up to 14 days ahead" in messages(date="2026-12-05")

    def test_an_unknown_interest_is_rejected(self):
        assert "'karaoke-ish' isn't one of our Interests" in messages(interests=[{"interest": "karaoke-ish"}])

    def test_interests_are_deduplicated_keeping_the_strongest(self):
        brief = make(interests=[{"interest": "wine", "weight": 0.4}, {"interest": "wine", "weight": 0.9}, {"interest": "beach"}])
        assert [(i.interest, i.weight) for i in brief.interests] == [("wine", 0.9), ("beach", 1.0)]

    def test_a_total_budget_needs_the_party_size(self):
        assert "needs the party size" in messages(budget_amount=2000, budget_basis="total")
        brief = make(budget_amount=2000, budget_basis="total", party_size=4)
        assert brief.budget_per_person() == 500

    def test_a_per_person_budget_doesnt(self):
        assert make(budget_amount=600).budget_per_person() == 600

    def test_a_budget_over_the_cap_for_the_currency(self):
        assert "above ZAR 50,000" in messages(budget_amount=60_000)

    def test_an_area_must_be_one_of_the_citys(self):
        assert make(area="kalk-bay").area == "kalk-bay"
        assert "'shoreditch' isn't an Area of Cape Town" in messages(area="shoreditch")

    def test_hidden_and_unknown_cities_are_rejected(self):
        assert "Unknown city" in messages(city="paris")

    @pytest.mark.parametrize("field, value, text", [
        ("must_include", ["a"] * 6, "at most 5 items"),
        ("avoid", ["x" * 61], "at most 60 characters"),
        ("party_size", 13, "less than or equal to 12"),
        ("dietary", ["paleo"], "Input should be"),
        ("mode", "brunch", "Input should be"),
    ])
    def test_field_limits(self, field, value, text):
        assert text in messages(**{field: value})

    def test_free_text_is_trimmed(self):
        assert make(must_include=["  Lion's Head ", ""], avoid=["no alcohol"]).must_include == ["Lion's Head"]

    def test_mode_windows(self):
        assert make(mode="night").window() == (time(19, 0), time(2, 0))
        assert make(mode="full_day", end_time="22:00").window() == (time(9, 0), time(22, 0))


class TestApplyPatch:
    def test_only_the_patchs_fields_change(self):
        brief = make(area="sea-point", party_size=2, budget_amount=800, interests=[{"interest": "beach"}], dietary=["halaal"])
        patched = apply_patch(brief, BriefPatch(mode="night", budget_amount=1200))
        assert (patched.mode, patched.budget_amount) == ("night", 1200)
        assert (patched.area, patched.party_size, [i.interest for i in patched.interests], patched.dietary) == ("sea-point", 2, ["beach"], ["halaal"])

    def test_an_empty_patch_changes_nothing(self):
        brief = make(area="observatory", pace="packed")
        assert apply_patch(brief, BriefPatch()) == brief

    def test_null_clears_only_fields_that_can_be_empty(self):
        brief = make(area="kalk-bay", budget_amount=500)
        patched = apply_patch(brief, BriefPatch(area=None, mode=None, date=None))
        assert patched.area is None
        assert (patched.mode, patched.date) == ("day", TODAY)

    def test_party_size_given_earlier_still_counts_for_a_total_budget(self):
        brief = make(party_size=3)
        assert apply_patch(brief, BriefPatch(budget_amount=900, budget_basis="total")).budget_per_person() == 300

    def test_an_invalid_result_raises_readable_messages(self):
        with pytest.raises(BriefError) as error:
            apply_patch(make(), BriefPatch(budget_amount=1000, budget_basis="total"))
        assert error.value.messages == ["A total budget needs the party size, so it can be split per person"]

    def test_changing_city_rechecks_the_area(self):
        with pytest.raises(BriefError, match="isn't an Area of Johannesburg"):
            apply_patch(make(area="kalk-bay"), BriefPatch(city="johannesburg"))


class TestEndpoints:
    def test_check_fills_defaults(self, client):
        resp = client.post("/api/v1/briefs/check", json={"city": "durban", "date": TODAY.isoformat(), "mode": "night"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["party_size"] == 1 and resp.json()["transport"] == "e_hailing"

    def test_check_lists_problems_in_plain_words(self, client):
        resp = client.post("/api/v1/briefs/check", json={"city": "cape-town", "date": "2026-01-01"})
        assert resp.status_code == 422
        assert any("has already passed in Cape Town" in m for m in resp.json()["detail"])

    def test_apply(self, client):
        resp = client.post("/api/v1/briefs/apply", json={
            "brief": {"city": "cape-town", "date": TODAY.isoformat(), "area": "bo-kaap"},
            "patch": {"interests": [{"interest": "food", "weight": 0.8}]},
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["area"] == "bo-kaap" and resp.json()["interests"] == [{"interest": "food", "weight": 0.8}]
