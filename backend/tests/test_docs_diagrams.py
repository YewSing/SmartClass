"""T103: the Lucidchart design diagrams match the code.

`docs/diagrams/build_lucid.py` builds the ERD page from the SQLAlchemy models. These tests fail
when a table is added without a place on the ERD, or when the committed import file is stale.
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS = ROOT / "docs" / "diagrams"


def _builder():
    spec = importlib.util.spec_from_file_location("build_lucid", DIAGRAMS / "build_lucid.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_erd_places_every_table():
    from app.core.database import Base
    import app.models  # noqa: F401

    placed = [n for col in _builder().ERD_COLUMNS for n in col]
    assert len(placed) == len(set(placed))
    assert set(placed) == set(Base.metadata.tables)


def test_erd_draws_every_foreign_key():
    from app.core.database import Base
    import app.models  # noqa: F401

    doc = _builder().build()
    erd = next(p for p in doc["pages"] if p["id"] == "erd")
    drawn = {(ln["endpoint1"]["shapeId"], ln["endpoint2"]["shapeId"]) for ln in erd["lines"]}
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            assert (f"t_{table.name}", f"t_{fk.column.table.name}") in drawn, fk


def test_committed_import_file_is_current():
    committed = json.loads((DIAGRAMS / "smartclass-diagrams.lucid.json").read_text(encoding="utf-8"))
    built = _builder().build()
    assert [p["id"] for p in committed["pages"]] == [p["id"] for p in built["pages"]]
    erd = lambda d: next(p for p in d["pages"] if p["id"] == "erd")  # noqa: E731
    assert [s["text"] for s in erd(committed)["shapes"]] == [s["text"] for s in erd(built)["shapes"]]


def test_png_exports_exist():
    pngs = sorted(p.name for p in DIAGRAMS.glob("*.png"))
    assert len(pngs) == 11, pngs
