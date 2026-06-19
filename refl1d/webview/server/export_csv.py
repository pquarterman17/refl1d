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


HEADER = [
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

    rows: List[List[str]] = []

    # Free (fitted) parameters first, in fit order (matches labels()/getp()).
    for i, p in enumerate(free):
        lo, hi = _limits(p)
        rows.append(
            [
                getattr(p, "name", f"p{i}"),
                _g(getattr(p, "value", None)),
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
                getattr(p, "name", "?"),
                _g(getattr(p, "value", None)),
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
