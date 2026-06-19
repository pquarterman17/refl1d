"""Tests for the export-results UI feedback (fork feature).

The ``export_results`` override in :mod:`refl1d.webview.server.api` writes the
Excel-friendly ``<model>-pars.csv`` and must surface the outcome in the UI: a
confirmation when the CSV is written, and a visible error notification when it
fails (previously such failures were only logged to the server console, so it
looked like nothing happened).

These tests exercise the wrapper logic only; ``export_fit`` (the standard bumps
bundle, which needs a reflectivity backend) is stubbed out so the tests stay
fast and backend-independent.
"""

import asyncio

import numpy as np

from bumps.fitproblem import FitProblem

from refl1d.experiment import Experiment
from refl1d.probe.probe import NeutronProbe
from refl1d.sample.material import SLD
from refl1d.sample.materialdb import air, silicon
from refl1d.webview.server import api


def _make_problem():
    T = np.linspace(0.5, 5.0, 20)
    probe = NeutronProbe(
        T=T,
        dT=0.01 * np.ones_like(T),
        L=5.0 * np.ones_like(T),
        dL=0.1 * np.ones_like(T),
        data=(np.exp(-T), 0.05 * np.exp(-T)),
        name="SampleA",
    )
    nickel = SLD("Ni", rho=9.4)
    sample = silicon(0, 5) | nickel(100, 5) | air
    sample[1].thickness.range(50, 150)
    sample[1].material.rho.range(8, 10)
    return FitProblem(Experiment(sample=sample, probe=probe))


class _ProblemState:
    def __init__(self, problem):
        self.fitProblem = problem
        self.serializer = "dataclass"


def _patch_state_and_notifications(monkeypatch, problem):
    """Stub websocket-bound helpers; capture notifications. Returns the list."""
    notifications = []

    async def fake_add_notification(content, title="Notification", timeout=None):
        notifications.append({"title": title, "content": content, "timeout": timeout})
        return len(notifications)

    async def fake_emit(*args, **kwargs):
        return None

    # Don't run the full bumps export bundle (needs a reflectivity backend).
    def fake_export_fit(*args, **kwargs):
        return None

    monkeypatch.setattr(api, "add_notification", fake_add_notification)
    monkeypatch.setattr(api, "emit", fake_emit)
    monkeypatch.setattr(api, "export_fit", fake_export_fit)
    monkeypatch.setattr(api.state, "problem", _ProblemState(problem))
    monkeypatch.setattr(api.state, "fitting", None)
    return notifications


def test_success_emits_confirmation_and_writes_csv(tmp_path, monkeypatch):
    notifications = _patch_state_and_notifications(monkeypatch, _make_problem())

    asyncio.run(api.export_results([str(tmp_path)]))

    csvs = list(tmp_path.glob("*-pars.csv"))
    assert csvs, "expected a <model>-pars.csv to be written"
    titles = [n["title"] for n in notifications]
    assert any("exported" in t.lower() for t in titles), titles


def test_failure_surfaces_error_notification(tmp_path, monkeypatch):
    notifications = _patch_state_and_notifications(monkeypatch, _make_problem())

    def boom(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(api, "write_parameters_csv", boom)

    asyncio.run(api.export_results([str(tmp_path)]))

    assert not list(tmp_path.glob("*-pars.csv")), "no CSV should exist on failure"
    error_notes = [n for n in notifications if "not written" in n["title"].lower()]
    assert error_notes, [n["title"] for n in notifications]
    # The actual reason must be carried to the user, not swallowed.
    assert "synthetic failure" in error_notes[0]["content"]
    assert error_notes[0]["timeout"]  # finite, self-clearing (not stuck)
