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
from refl1d.webview.server.export_csv import HEADER, write_parameters_csv


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


def test_header(tmp_path):
    out = write_parameters_csv(_make_problem(), None, tmp_path / "model-pars.csv")
    rows = _read_csv(out)
    assert rows[0] == HEADER


def test_free_params_have_bounds_and_state(tmp_path):
    out = write_parameters_csv(_make_problem(), None, tmp_path / "model-pars.csv")
    by_name = {r[0]: r for r in _read_csv(out)[1:]}

    for name, value, lo, hi in [
        ("Ni thickness", 100.0, 50.0, 150.0),
        ("Ni rho", 9.4, 8.0, 10.0),
    ]:
        assert name in by_name, f"{name} missing from CSV"
        row = by_name[name]
        assert float(row[1]) == value  # value
        assert float(row[3]) == lo  # lower_bound
        assert float(row[4]) == hi  # upper_bound
        assert row[5] == "free"  # state
        # Covariance gives a finite uncertainty for this well-posed problem.
        assert row[2] != "", f"{name} missing uncertainty"
        float(row[2])  # parses as a number


def test_fixed_params_present_and_blank(tmp_path):
    out = write_parameters_csv(_make_problem(), None, tmp_path / "model-pars.csv")
    rows = _read_csv(out)[1:]
    fixed = {r[0]: r for r in rows if r[5] == "fixed"}

    # intensity/background are fixed probe parameters; for a named probe they are
    # suffixed with the probe name (e.g. "intensity SampleA").
    assert any(name.startswith("intensity") for name in fixed), list(fixed)
    assert any(name.startswith("background") for name in fixed), list(fixed)

    # A fixed row has blank uncertainty, bounds, and CI columns.
    fixed_row = next(iter(fixed.values()))
    assert fixed_row[2] == ""  # uncertainty
    assert fixed_row[3] == "" and fixed_row[4] == ""  # bounds
    assert fixed_row[6] == "" and fixed_row[7] == ""  # ci68


def test_free_params_listed_before_fixed(tmp_path):
    out = write_parameters_csv(_make_problem(), None, tmp_path / "model-pars.csv")
    states = [r[5] for r in _read_csv(out)[1:]]
    first_fixed = states.index("fixed")
    assert all(s == "free" for s in states[:first_fixed]), states
