"""The places catalogue ingest (#119), on small fixture GeoParquet files: no network."""

from datetime import date

import duckdb
import pytest

from app.models.place import Place
from scripts.catalogue import ingest
from scripts.catalogue.ingest import Report, build, merge, normalise_name, upsert, Row
from app.core.cities import get_city

CAPE_TOWN = get_city("cape-town")


def write_overture(path, rows):
    """A tiny Overture-shaped places file: the columns the ingest reads, nested as in the real schema."""
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE t (id VARCHAR, names STRUCT("primary" VARCHAR), confidence DOUBLE, operating_status VARCHAR,
                        taxonomy STRUCT("primary" VARCHAR, alternates VARCHAR[]), websites VARCHAR[],
                        bbox STRUCT(xmin DOUBLE, xmax DOUBLE, ymin DOUBLE, ymax DOUBLE))
    """)
    for oid, name, lat, lng, confidence, status, category in rows:
        con.execute(
            "INSERT INTO t VALUES (?, {'primary': ?}, ?, ?, {'primary': ?, 'alternates': []}, ['https://example.com'], {'xmin': ?, 'xmax': ?, 'ymin': ?, 'ymax': ?})",
            [oid, name, confidence, status, category, lng, lng, lat, lat],
        )
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT parquet)")


def write_fsq(path, rows):
    con = duckdb.connect()
    con.execute("CREATE TABLE t (fsq_place_id VARCHAR, name VARCHAR, latitude DOUBLE, longitude DOUBLE, fsq_category_ids VARCHAR[], date_closed VARCHAR, website VARCHAR)")
    for fid, name, lat, lng, categories, closed in rows:
        con.execute("INSERT INTO t VALUES (?, ?, ?, ?, ?, ?, NULL)", [fid, name, lat, lng, categories, closed])
    con.execute(f"COPY t TO '{path.as_posix()}' (FORMAT parquet)")


NIGHT_CLUB = "4bf58dd8d48988d11f941735"  # Foursquare "Night Club"
PARK = "4bf58dd8d48988d163941735"  # Foursquare "Park"

OVERTURE_ROWS = [
    ("ov1", "Kirstenbosch National Botanical Garden", -33.9875, 18.4327, 0.95, None, "botanical_garden"),
    ("ov2", "Club Galaxy", -33.9235, 18.4205, 0.80, None, "dance_club"),
    ("ov3", "Truth Coffee Roasting", -33.9278, 18.4232, 0.90, "open", "coffee_shop"),
    ("ov4", "A Dentist", -33.9240, 18.4210, 0.95, None, "dentist"),  # unmapped category
    ("ov5", "Maybe A Bar", -33.9250, 18.4220, 0.30, None, "bar"),  # low confidence
    ("ov6", "Gone Bistro", -33.9260, 18.4225, 0.90, "permanently_closed", "restaurant"),
    ("ov7", "Joburg Grill", -26.1046, 28.0545, 0.90, None, "restaurant"),  # outside Cape Town
    ("ov8", "Kalk Bay Harbour", -34.1278, 18.4490, 0.70, None, "market"),
]
FSQ_ROWS = [
    ("fsq1", "Club Galaxy", -33.92355, 18.42055, [NIGHT_CLUB], None),  # same place as ov2, about 7 m away
    ("fsq2", "Galaxy Club Annex", -33.9300, 18.4300, [NIGHT_CLUB], None),  # different place
    ("fsq3", "Closed Park", -33.9500, 18.4600, [PARK], "2025-01-01"),
    ("fsq4", "Unknown Thing", -33.9400, 18.4500, ["00000000000000000000dead"], None),
]


@pytest.fixture
def sources(tmp_path):
    overture, fsq = tmp_path / "overture.parquet", tmp_path / "fsq.parquet"
    write_overture(overture, OVERTURE_ROWS)
    write_fsq(fsq, FSQ_ROWS)
    return str(overture), str(fsq)


def built(sources, min_confidence=0.5):
    return build("cape-town", sources[0], sources[1], min_confidence, "2026-10-21.0")


class TestBuild:
    def test_duplicates_across_sources_merge_into_one_row_with_both_ids(self, sources):
        rows, report = built(sources)
        [galaxy] = [r for r in rows if r.name == "Club Galaxy"]
        assert (galaxy.overture_id, galaxy.fsq_id) == ("ov2", "fsq1")
        assert galaxy.interests == ["clubbing"]
        assert report.merged == 1

    def test_unmapped_low_confidence_closed_and_out_of_city_rows_drop(self, sources):
        rows, report = built(sources)
        names = {r.name for r in rows}
        assert names == {"Kirstenbosch National Botanical Garden", "Club Galaxy", "Truth Coffee Roasting", "Kalk Bay Harbour", "Galaxy Club Annex"}
        assert report.read == {"overture": 7, "fsq": 4}  # the Joburg row is outside the bounds
        assert report.dropped == {"unmapped_category": 2, "low_confidence": 1, "closed": 2}

    def test_the_confidence_floor_is_configurable(self, sources):
        rows, _ = built(sources, min_confidence=0.2)
        assert "Maybe A Bar" in {r.name for r in rows}

    def test_places_get_their_area_and_interests(self, sources):
        rows, report = built(sources)
        by_name = {r.name: r for r in rows}
        assert by_name["Kirstenbosch National Botanical Garden"].area_id == "kirstenbosch"
        assert by_name["Kalk Bay Harbour"].area_id == "kalk-bay"
        assert by_name["Truth Coffee Roasting"].interests == ["coffee"]
        assert report.per_interest["clubbing"] == 2 and report.per_interest["nature"] == 1
        assert report.in_an_area == sum(1 for r in rows if r.area_id)

    def test_names_are_compared_without_noise(self):
        assert normalise_name("The Gin Bar & Restaurant") == normalise_name("Gin")
        assert normalise_name("Café Riche") == "riche"

    def test_far_apart_or_differently_named_places_stay_separate(self):
        a = Row("Club Galaxy", -33.9235, 18.4205, [], ["clubbing"], overture_id="o")
        far = Row("Club Galaxy", -33.9300, 18.4205, [], ["clubbing"], fsq_id="f1")
        other = Row("Mama Africa", -33.9235, 18.4205, [], ["food"], fsq_id="f2")
        rows, merged = merge([a, far, other])
        assert (len(rows), merged) == (3, 0)


class TestUpsert:
    def run(self, session, rows, release, today=date(2026, 11, 16)):
        report = Report(city="cape-town", release=release)
        upsert(session, CAPE_TOWN, [Row(**r.__dict__) for r in rows], release, report, today=today)
        return report

    def test_rerunning_the_same_release_changes_nothing(self, sources, db_session):
        rows, _ = built(sources)
        first = self.run(db_session, rows, "2026-10-21.0")
        before = [(p.id, p.name, p.updated_at, p.last_seen) for p in db_session.query(Place).order_by(Place.id)]

        again = self.run(db_session, rows, "2026-10-21.0", today=date(2026, 11, 17))

        assert first.inserted == len(rows)
        assert (again.inserted, again.updated, again.deleted, again.unchanged) == (0, 0, 0, len(rows))
        assert [(p.id, p.name, p.updated_at, p.last_seen) for p in db_session.query(Place).order_by(Place.id)] == before

    def test_a_place_is_matched_by_source_id_and_keeps_its_google_id(self, sources, db_session):
        rows, _ = built(sources)
        self.run(db_session, rows, "2026-10-21.0")
        truth = db_session.query(Place).filter_by(overture_id="ov3").one()
        truth.google_place_id = "ChIJtruth"  # set by the matching job (#120)
        db_session.commit()

        renamed = [Row(**{**r.__dict__, "name": "Truth Coffee"}) if r.overture_id == "ov3" else r for r in rows]
        report = self.run(db_session, renamed, "2026-11-18.0")

        truth = db_session.query(Place).filter_by(overture_id="ov3").one()
        assert (truth.name, truth.google_place_id, report.updated) == ("Truth Coffee", "ChIJtruth", 1)

    def test_a_place_missing_from_two_releases_in_a_row_is_deleted(self, sources, db_session):
        rows, _ = built(sources)
        self.run(db_session, rows, "r1")
        without_kalk_bay = [r for r in rows if r.overture_id != "ov8"]

        self.run(db_session, without_kalk_bay, "r2")
        self.run(db_session, without_kalk_bay, "r2")  # a re-run of the same release isn't a second miss
        assert db_session.query(Place).filter_by(overture_id="ov8").one().missed_releases == 1

        report = self.run(db_session, without_kalk_bay, "r3")
        assert report.deleted == 1
        assert db_session.query(Place).filter_by(overture_id="ov8").count() == 0

    def test_a_place_that_comes_back_is_reset(self, sources, db_session):
        rows, _ = built(sources)
        self.run(db_session, rows, "r1")
        self.run(db_session, [r for r in rows if r.overture_id != "ov8"], "r2")
        self.run(db_session, rows, "r3")
        assert db_session.query(Place).filter_by(overture_id="ov8").one().missed_releases == 0


def test_the_pinned_release_comes_from_sources_yaml():
    assert ingest.pinned_release() == "2026-10-21.0"


def test_the_api_never_imports_duckdb():
    import subprocess
    import sys

    code = "import sys, app.main; print('duckdb' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(ingest.REPO_ROOT),
                         env={**__import__('os').environ, "OTB_SECRET_KEY": "x", "OTB_DATABASE_URL": "sqlite://"})
    assert out.stdout.strip().splitlines()[-1] == "False", out.stderr
