# Category lists

Pinned copies of each data source's category list. `tests/test_interests.py` checks every entry in `app/data/interests.yaml` against them, so a typo or a category that doesn't exist fails the suite.

| File | Source | Version | Licence |
| --- | --- | --- | --- |
| `google_place_types_table_a.txt` | [Places API (New) place types, Table A](https://developers.google.com/maps/documentation/places/web-service/place-types) | page updated 2026-11-09, copied 2026-11-16 (478 types) | type names from Google's documentation ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)) |
| `overture_categories.txt` | [Overture Maps places taxonomy](https://github.com/OvertureMaps/web-tools/tree/main/tools/taxonomy-explorer/public/taxonomy/2026-10-21.0) (`taxonomy.csv`, `primary` column) | release 2026-10-21.0 (2,302 categories) | © Overture Maps Foundation, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| `fsq_os_places_categories.csv` | [Foursquare OS Places categories](https://docs.foursquare.com/data-products/docs/categories) (the flat-file table) | copied 2026-11-16 (1,279 categories) | Foursquare OS Places, [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) |

## Updating

When #119 moves to a new Overture or Foursquare release, or Google adds types, replace the file with the new list and update its version here and in the file's header. Then run `pytest tests/test_interests.py`: any Interest using a category the new list dropped fails and needs a replacement.
