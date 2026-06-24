"""Excel-friendly CSV export of fit parameters (fork feature).

The stock bumps export writes a ``.par`` file (``name value`` pairs, space
separated, no header). That is awkward to drop into a spreadsheet. This module
writes a ``<model>-pars.csv`` with a header row and one column per useful field:

    parameter, value, uncertainty, lower_bound, upper_bound, state, ci68_low, ci68_high

* Free (fitted) parameters are listed first, in fit order, followed by the fixed
  parameters (intensity, background, fixed thicknesses, etc.).
* ``uncertainty`` and the 68% credible interval come from the DREAM posterior
  when a DREAM fit was run; otherwise ``uncertainty`` falls back to the
  covariance estimate at the best fit and the CI columns are left blank. Any
  value that cannot be computed is left blank rather than guessed.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from bumps.parameter import Parameter, unique


def _g(x: Optional[float]) -> str:
    """Format a float for the CSV (15 significant figures), blank for None."""
    if x is None:
        return ""
    try:
        return f"{float(x):.15g}"
    except (TypeError, ValueError):
        return ""


def _value(p) -> Optional[float]:
    """Read ``p.value`` defensively.

    For tied/expression parameters (common in simultaneous fits) ``.value`` is a
    property that evaluates the expression and may raise something other than
    ``AttributeError`` -- which a plain ``getattr(p, "value", None)`` would let
    through. Return ``None`` on any failure so one odd parameter can't abort the
    whole CSV.
    """
    try:
        return p.value
    except Exception:
        return None


def _limits(p) -> Tuple[Optional[float], Optional[float]]:
    """Return finite (lower, upper) bounds for a parameter, or None where unbounded."""
    try:
        lo, hi = p.prior.limits
        lo = float(lo)
        hi = float(hi)
    except Exception:
        return None, None
    return (lo if np.isfinite(lo) else None, hi if np.isfinite(hi) else None)


def _free_uncertainty(problem, fit) -> Tuple[List, List, List]:
    """Best-effort (stderr, ci68_low, ci68_high) per free parameter, aligned to ``labels()``.

    Prefers the DREAM posterior (68% interval); falls back to the covariance
    estimate at the current point. Returns lists of ``None`` where unavailable.
    """
    n = len(problem.labels())
    stderr: List[Optional[float]] = [None] * n
    ci_lo: List[Optional[float]] = [None] * n
    ci_hi: List[Optional[float]] = [None] * n

    fit_state = None
    if fit is not None:
        fit_state = getattr(fit, "fit_state", getattr(fit, "state", None))

    # Prefer the MCMC posterior if a DREAM fit produced one.
    if fit_state is not None and hasattr(fit_state, "draw"):
        try:
            from bumps.dream.stats import var_stats

            vstats = var_stats(fit_state.draw())
            for i, v in enumerate(vstats[:n]):
                p68 = getattr(v, "p68", None)
                if p68 is not None:
                    ci_lo[i], ci_hi[i] = float(p68[0]), float(p68[1])
                    stderr[i] = (float(p68[1]) - float(p68[0])) / 2
                std = getattr(v, "std", None)
                if std is not None:
                    stderr[i] = float(std)
            return stderr, ci_lo, ci_hi
        except Exception:
            pass  # fall through to covariance

    # Fall back to the covariance estimate at the current point.
    try:
        from bumps.lsqerror import stderr as cov_stderr

        dx = np.asarray(cov_stderr(problem.cov(problem.getp()))).ravel()
        for i in range(min(n, len(dx))):
            val = float(dx[i])
            stderr[i] = val if np.isfinite(val) else None
    except Exception:
        pass

    return stderr, ci_lo, ci_hi


def _model_map(problem) -> dict:
    """Map ``id(parameter) -> model label`` so each CSV row can name its dataset.

    In a simultaneous (multi-dataset) fit, parameters from different models often
    share a name (six ``film thickness`` rows, etc.); the model label is what
    tells them apart. A parameter tied across several models is labelled
    ``"shared"``. Best-effort: returns ``{}`` if the model structure can't be
    walked, leaving the column blank rather than failing the export.
    """
    mapping: dict = {}
    try:
        models = list(problem.models)
    except Exception:
        return mapping
    for i, m in enumerate(models):
        label = getattr(m, "name", None) or f"model{i}"
        try:
            leaves = unique(m.parameters())
        except Exception:
            continue
        for p in leaves:
            if not isinstance(p, Parameter):
                continue
            prev = mapping.get(id(p))
            if prev is None:
                mapping[id(p)] = label
            elif prev != label:
                mapping[id(p)] = "shared"
    return mapping


HEADER = [
    "model",
    "parameter",
    "value",
    "uncertainty",
    "lower_bound",
    "upper_bound",
    "state",
    "ci68_low",
    "ci68_high",
]


def write_parameters_csv(problem, fit, path: Path | str) -> Path:
    """Write the fit parameters of *problem* to *path* as a spreadsheet-friendly CSV.

    *problem* is a bumps ``FitProblem``; *fit* is the fork's ``FitResult`` (or
    ``None`` before a fit). Returns the path written.
    """
    path = Path(path)
    free = list(problem._parameters)
    free_ids = {id(p) for p in free}
    stderr, ci_lo, ci_hi = _free_uncertainty(problem, fit)
    model_of = _model_map(problem)

    rows: List[List[str]] = []

    # Free (fitted) parameters first, in fit order (matches labels()/getp()).
    for i, p in enumerate(free):
        lo, hi = _limits(p)
        rows.append(
            [
                model_of.get(id(p), ""),
                getattr(p, "name", f"p{i}"),
                _g(_value(p)),
                _g(stderr[i]),
                _g(lo),
                _g(hi),
                "free",
                _g(ci_lo[i]),
                _g(ci_hi[i]),
            ]
        )

    # Then the fixed parameters (no uncertainty/bounds shown).
    for p in unique(problem.model_parameters()):
        if not isinstance(p, Parameter) or id(p) in free_ids:
            continue
        if not getattr(p, "fixed", True):
            continue
        rows.append(
            [
                model_of.get(id(p), ""),
                getattr(p, "name", "?"),
                _g(_value(p)),
                "",
                "",
                "",
                "fixed",
                "",
                "",
            ]
        )

    with open(path, "w", newline="", encoding="utf-8") as fd:
        writer = csv.writer(fd)
        writer.writerow(HEADER)
        writer.writerows(rows)

    return path


def _oneline(s) -> str:
    """Collapse a possibly multi-line metadata string to a single trimmed line."""
    return " ".join(str(s).splitlines()).strip() if s else ""


def _dataset_label(m, idx: int) -> str:
    """Best 'datafile name' for a model: the probe's filename (basename) if it
    loaded from a file, else the model/probe name, else a positional fallback."""
    probe = getattr(m, "probe", None)
    fname = getattr(probe, "filename", None)
    if fname:
        return Path(str(fname)).name
    return getattr(m, "name", None) or getattr(probe, "name", None) or f"model{idx}"


def _probe_meta(m) -> Tuple[str, str]:
    """(description, comment) from the model's probe, blank when absent.

    The stock refl1d ``Probe`` carries ``description`` but no ``comment``
    attribute; ``comment`` is read defensively so a loader/metadata that adds one
    is picked up, and the column is simply blank (and later omitted) otherwise.
    """
    probe = getattr(m, "probe", None)
    return _oneline(getattr(probe, "description", None)), _oneline(getattr(probe, "comment", None))


def write_parameters_by_dataset_csv(problem, fit, path: Path | str) -> Optional[Path]:
    """Write a wide per-dataset comparison table (fork feature).

    One row per model (dataset), two columns per parameter -- ``value`` and
    ``<name> error`` -- so the same model fit across several datasets can be
    compared at a glance::

        datafile,   description, film thickness, film thickness error, film rho, film rho error
        data_A.dat, run1 300K,   100.2,          0.5,                  2.07,     0.01
        data_B.dat, run2 300K,   98.7,           0.4,                  2.07,     0.01

    After ``datafile`` come optional ``description`` and ``comment`` columns,
    taken from each dataset's probe -- included only when at least one dataset
    actually has that field. Parameter columns are the ordered union of names
    across models (so "similar" models line up, and a parameter missing from one
    model leaves a blank cell). Both free and fixed parameters are included;
    fixed parameters get a blank error. Tied/shared parameters repeat their value
    on every row that uses them.

    Only meaningful for simultaneous (multi-dataset) fits: returns ``None``
    without writing when the problem has fewer than two models.
    """
    path = Path(path)
    try:
        models = list(problem.models)
    except Exception:
        return None
    if len(models) < 2:
        return None

    # Per free-parameter stderr, keyed by id() so any parameter we meet while
    # walking a model can look up its error (fixed params won't be present).
    free = list(problem._parameters)
    stderr, _ci_lo, _ci_hi = _free_uncertainty(problem, fit)
    err_by_id = {id(p): stderr[i] for i, p in enumerate(free) if i < len(stderr)}

    # Walk each model: capture its datafile label + probe metadata, record
    # {name: (value, err)}, and build the ordered union of names (first model's
    # order first, then any newcomers).
    col_names: List[str] = []
    seen = set()
    per_model: List[Tuple[str, str, str, dict]] = []
    any_desc = any_comment = False
    for i, m in enumerate(models):
        label = _dataset_label(m, i)
        desc, comment = _probe_meta(m)
        any_desc = any_desc or bool(desc)
        any_comment = any_comment or bool(comment)
        try:
            leaves = unique(m.parameters())
        except Exception:
            leaves = []
        pmap: dict = {}
        for p in leaves:
            if not isinstance(p, Parameter):
                continue
            name = getattr(p, "name", None)
            if not name or name in pmap:  # first occurrence within a model wins
                continue
            pmap[name] = (_value(p), err_by_id.get(id(p)))
            if name not in seen:
                seen.add(name)
                col_names.append(name)
        per_model.append((label, desc, comment, pmap))

    # description / comment columns appear only if some dataset populated them.
    header = ["datafile"]
    if any_desc:
        header.append("description")
    if any_comment:
        header.append("comment")
    for name in col_names:
        header.append(name)
        header.append(f"{name} error")

    rows: List[List[str]] = []
    for label, desc, comment, pmap in per_model:
        row = [label]
        if any_desc:
            row.append(desc)
        if any_comment:
            row.append(comment)
        for name in col_names:
            val, err = pmap.get(name, (None, None))
            row.append(_g(val))
            row.append(_g(err))
        rows.append(row)

    with open(path, "w", newline="", encoding="utf-8") as fd:
        writer = csv.writer(fd)
        writer.writerow(header)
        writer.writerows(rows)

    return path
