"""Tests for the Excel-friendly fit-parameter CSV export (fork feature).

Covers :func:`refl1d.webview.server.export_csv.write_parameters_csv`:
- header row and column layout,
- free (fitted) parameters with bounds and ``state=free``,
- fixed parameters (intensity, background, ...) with ``state=fixed`` and blank
  uncertainty/bounds,
- free parameters listed before fixed ones.
"""

import csv

import numpy as np

from bumps.fitproblem import FitProblem

from refl1d.experiment import Experiment
from refl1d.probe.probe import NeutronProbe
from refl1d.sample.material import SLD
from refl1d.sample.materialdb import air, silicon
from refl1d.webview.server import api
from refl1d.webview.server.export_csv import (
    HEADER,
    write_parameters_by_dataset_csv,
    write_parameters_csv,
)


def _make_problem():
    # NeutronProbe carries angle + wavelength, so the sample SLD can render.
    T = np.linspace(0.5, 5.0, 40)
    dT = 0.01 * np.ones_like(T)
    L = 5.0 * np.ones_like(T)
    dL = 0.1 * np.ones_like(L)
    R = np.exp(-T)
    dR = 0.05 * R
    probe = NeutronProbe(T=T, dT=dT, L=L, dL=dL, data=(R, dR), name="SampleA")

    nickel = SLD("Ni", rho=9.4)
    sample = silicon(0, 5) | nickel(100, 5) | air
    sample[1].thickness.range(50, 150)
    sample[1].material.rho.range(8, 10)
    return FitProblem(Experiment(sample=sample, probe=probe))


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as fd:
        return list(csv.reader(fd))


# Column accessors by name so the tests survive column additions/reordering.
def _col(row, name):
    return row[HEADER.index(name)]


def _by_name(rows):
    return {_col(r, "parameter"): r for r in rows}


def test_header(tmp_path):
    out = write_parameters_csv(_make_problem(), None, tmp_path / "model-pars.csv")
    rows = _read_csv(out)
    assert rows[0] == HEADER


def test_free_params_have_bounds_and_state(tmp_path):
    out = write_parameters_csv(_make_problem(), None, tmp_path / "model-pars.csv")
    by_name = _by_name(_read_csv(out)[1:])

    for name, value, lo, hi in [
        ("Ni thickness", 100.0, 50.0, 150.0),
        ("Ni rho", 9.4, 8.0, 10.0),
    ]:
        assert name in by_name, f"{name} missing from CSV"
        row = by_name[name]
        assert float(_col(row, "value")) == value
        assert float(_col(row, "lower_bound")) == lo
        assert float(_col(row, "upper_bound")) == hi
        assert _col(row, "state") == "free"
        # Covariance gives a finite uncertainty for this well-posed problem.
        assert _col(row, "uncertainty") != "", f"{name} missing uncertainty"
        float(_col(row, "uncertainty"))  # parses as a number


def test_fixed_params_present_and_blank(tmp_path):
    out = write_parameters_csv(_make_problem(), None, tmp_path / "model-pars.csv")
    rows = _read_csv(out)[1:]
    fixed = _by_name([r for r in rows if _col(r, "state") == "fixed"])

    # intensity/background are fixed probe parameters; for a named probe they are
    # suffixed with the probe name (e.g. "intensity SampleA").
    assert any(name.startswith("intensity") for name in fixed), list(fixed)
    assert any(name.startswith("background") for name in fixed), list(fixed)

    # A fixed row has blank uncertainty, bounds, and CI columns.
    fixed_row = next(iter(fixed.values()))
    assert _col(fixed_row, "uncertainty") == ""
    assert _col(fixed_row, "lower_bound") == "" and _col(fixed_row, "upper_bound") == ""
    assert _col(fixed_row, "ci68_low") == "" and _col(fixed_row, "ci68_high") == ""


def test_free_params_listed_before_fixed(tmp_path):
    out = write_parameters_csv(_make_problem(), None, tmp_path / "model-pars.csv")
    states = [_col(r, "state") for r in _read_csv(out)[1:]]
    first_fixed = states.index("fixed")
    assert all(s == "free" for s in states[:first_fixed]), states


def _make_multimodel_problem():
    """Two datasets fit simultaneously: a shared film rho, per-model thickness.

    Both models reuse the same layer/material names, so the parameter names
    collide ("film thickness" appears in each) -- the model column is what
    disambiguates them.
    """
    film = SLD("film", rho=4.0)
    film.rho.range(2, 6)  # ONE shared free parameter across both models

    def one(idx):
        T = np.linspace(0.5, 5.0, 20)
        probe = NeutronProbe(
            T=T,
            dT=0.01 * np.ones_like(T),
            L=5.0 * np.ones_like(T),
            dL=0.1 * np.ones_like(T),
            data=(np.exp(-T), 0.05 * np.exp(-T)),
            name=f"Sample{idx}",
        )
        sample = silicon(0, 5) | film(100, 5) | air
        sample[1].thickness.range(50, 150)  # same name "film thickness" in each model
        return Experiment(sample=sample, probe=probe, name=f"m{idx}")

    return FitProblem([one(0), one(1)])


def test_model_column_disambiguates_simultaneous_fit(tmp_path):
    out = write_parameters_csv(_make_multimodel_problem(), None, tmp_path / "model-pars.csv")
    rows = _read_csv(out)
    assert rows[0][0] == "model"  # model is the leading column

    body = rows[1:]
    # The same-named per-model thickness appears once per model, each tagged.
    thick = [r for r in body if _col(r, "parameter") == "film thickness"]
    assert {_col(r, "model") for r in thick} == {"m0", "m1"}, thick

    # The tied film rho appears once, labelled shared.
    rho = [r for r in body if _col(r, "parameter") == "film rho"]
    assert len(rho) == 1 and _col(rho[0], "model") == "shared", rho


def test_model_column_populated_for_single_model(tmp_path):
    # Every row gets a non-blank model label, even for a single (unnamed) model.
    out = write_parameters_csv(_make_problem(), None, tmp_path / "model-pars.csv")
    models = {_col(r, "model") for r in _read_csv(out)[1:]}
    assert len(models) == 1 and "" not in models, models


def test_csv_written_even_when_export_fit_raises(tmp_path, monkeypatch):
    """The CSV must survive a partial bumps export.

    ``export_fit`` writes the regular bundle (.par/.out/plots) early, then does
    unguarded uncertainty/error plotting last. On a large simultaneous DREAM fit
    that tail can raise *after* the regular files already landed -- which used to
    skip the parameter CSV entirely. The CSV is logically independent, so it must
    still be written, and the export failure must be reported (not swallowed,
    not allowed to abort the CSV).
    """

    def boom(path, problem, fit, serializer, basename):
        # Emulate the regular files landing before the failure.
        (tmp_path / f"{basename}.par").write_text("regular file\n")
        raise RuntimeError("simulated calc_errors failure on uncertainty plots")

    monkeypatch.setattr(api, "export_fit", boom)

    csv_path, _by_dataset, csv_error, export_error = api._export_with_csv(
        str(tmp_path), _make_problem(), None, "dataclass"
    )

    # CSV salvaged despite the bundle failure ...
    assert csv_path is not None and csv_path.exists()
    assert csv_error is None
    assert _read_csv(csv_path)[0] == HEADER
    # ... and the bundle failure is reported back for the UI, not lost.
    assert export_error is not None
    assert "simulated calc_errors failure" in export_error


def test_csv_written_when_export_fit_dies_before_mkdir(tmp_path, monkeypatch):
    """The CSV must be salvaged even into a directory export_fit never created.

    bumps' ``export_fit`` creates the output dir as its first step; the salvage
    code must not depend on that having run. Here ``export_fit`` raises before
    creating anything and the target is a not-yet-existing subdirectory, so the
    CSV writer must create the dir itself.
    """
    target = tmp_path / "subdir_that_does_not_exist_yet"

    def boom_before_mkdir(path, problem, fit, serializer, basename):
        raise RuntimeError("crashed before mkdir ran")

    monkeypatch.setattr(api, "export_fit", boom_before_mkdir)

    csv_path, _by_dataset, csv_error, export_error = api._export_with_csv(
        str(target), _make_problem(), None, "dataclass"
    )

    assert csv_error is None, csv_error
    assert csv_path is not None and csv_path.exists()
    assert csv_path.parent == target
    assert export_error is not None and "before mkdir" in export_error


# --- wide per-dataset comparison table (fork feature) -----------------------


def test_by_dataset_csv_layout(tmp_path):
    out = write_parameters_by_dataset_csv(_make_multimodel_problem(), None, tmp_path / "m-by-dataset.csv")
    assert out is not None
    rows = _read_csv(out)
    header = rows[0]

    # datafile first, then a value+error column PAIR per parameter.
    assert header[0] == "datafile"
    assert "film thickness" in header and "film thickness error" in header
    ti = header.index("film thickness")
    assert header[ti + 1] == "film thickness error"  # error follows its value

    body = rows[1:]
    assert {r[0] for r in body} == {"m0", "m1"}, body  # one row per dataset

    # film rho is shared -> identical value on both rows, and (being free) has an error.
    rho_i = header.index("film rho")
    assert len({r[rho_i] for r in body}) == 1
    assert all(r[rho_i + 1] != "" for r in body)

    # each dataset carries its own fitted thickness value + error.
    for r in body:
        assert r[ti] != "" and r[ti + 1] != ""


def test_by_dataset_csv_skipped_for_single_model(tmp_path):
    target = tmp_path / "single-by-dataset.csv"
    assert write_parameters_by_dataset_csv(_make_problem(), None, target) is None
    assert not target.exists()  # writes nothing for a single-dataset fit


def test_by_dataset_csv_includes_probe_description_and_comment(tmp_path):
    problem = _make_multimodel_problem()
    # description is a real probe field; comment is read defensively (stock Probe
    # has none) -- set one on a single model to prove per-cell population.
    # problem.models is a generator, so materialize once before indexing.
    models = list(problem.models)
    for i, m in enumerate(models):
        m.probe.description = f"run{i} 300K"
    models[0].probe.comment = "outlier removed"

    rows = _read_csv(write_parameters_by_dataset_csv(problem, None, tmp_path / "m-by-dataset.csv"))
    header = rows[0]
    assert header[:3] == ["datafile", "description", "comment"], header

    body = rows[1:]
    di, ci = header.index("description"), header.index("comment")
    assert {r[di] for r in body} == {"run0 300K", "run1 300K"}
    # only one model carries a comment; the other cell is blank.
    assert sorted(r[ci] for r in body) == ["", "outlier removed"]


def test_by_dataset_csv_omits_metadata_columns_when_absent(tmp_path):
    # The default fixture has no probe description/comment -> no such columns.
    rows = _read_csv(write_parameters_by_dataset_csv(_make_multimodel_problem(), None, tmp_path / "m.csv"))
    assert "description" not in rows[0]
    assert "comment" not in rows[0]
    assert rows[0][0] == "datafile"


def test_export_with_csv_writes_by_dataset_for_multimodel(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "export_fit", lambda *a, **k: None)  # skip the heavy bundle
    csv_path, by_dataset_path, csv_error, export_error = api._export_with_csv(
        str(tmp_path), _make_multimodel_problem(), None, "dataclass", basename="multi"
    )
    assert csv_error is None and export_error is None
    assert csv_path is not None and csv_path.name == "multi-pars.csv"
    assert by_dataset_path is not None and by_dataset_path.exists()
    assert by_dataset_path.name == "multi-by-dataset.csv"
    assert _read_csv(by_dataset_path)[0][0] == "datafile"
