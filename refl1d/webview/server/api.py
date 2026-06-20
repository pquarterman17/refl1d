import asyncio
import os
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Union

# import bumps.webview.server.api as bumps_api
import numpy as np
from bumps.errplot import error_points_from_state
from bumps.webview.server.api import (
    add_notification,
    emit,
    export_fit,
    get_chisq,
    log,
    logger,
    now_string,
    register,
    state,
    to_json_compatible_dict,
    to_thread,
    # For jupyter users:
    set_problem,
    start_fit_thread,
    wait_for_fit_complete,
    get_convergence_plot,
    get_correlation_plot,
    get_data_plot,
    load_session,
    load_problem_file,
    set_session_output_file,
)

from refl1d.uncertainty import calc_errors
from refl1d.experiment import Experiment, ExperimentBase, MixedExperiment
from refl1d.probe.data_loaders.load4 import load4
from refl1d.probe import PolarizedNeutronProbe, ProbeSet
from .profile_uncertainty import show_errors
from .profile_plot import plot_multiple_sld_profiles, ModelSpec
from .scriptify import serialize_fitproblem as scriptify_fitproblem
from .export_csv import write_parameters_csv

# state.problem.serializer = "dataclass"


@register
async def get_plot_data(view: str = "linear", include_data: bool = True):
    # TODO: implement view-dependent return instead of doing this in JS
    # (calculate x,y,dy.dx for given view, excluding log)
    #
    # *include_data* controls whether the static measured arrays (R, dR) are
    # included. During a fit only the theory changes, so the client can fetch
    # the full payload once and then request include_data=False on each update
    # to avoid re-sending the unchanging measured reflectivity.
    if state.problem is None or state.problem.fitProblem is None:
        return None
    fitProblem = state.problem.fitProblem
    chisq = await get_chisq(fitProblem)
    plotdata = []
    result = {"chisq": chisq, "plotdata": plotdata}
    for model in fitProblem.models:
        assert isinstance(model, ExperimentBase)
        theory = model.reflectivity()
        probe = model.probe
        probe_data = get_probe_data(theory, probe, model._substrate, model._surface, include_data=include_data)
        plotdata.append(probe_data)

    return to_json_compatible_dict(result)


async def create_profile_plots(model_specs: List[ModelSpec]):
    if state.problem is None or state.problem.fitProblem is None:
        return None
    fitProblem = state.problem.fitProblem
    plot_items = []
    color_index = 0
    for model_index, model in enumerate(fitProblem.models):
        for sample_index, part in enumerate(getattr(model, "parts", [model])):
            spec = dict(model_index=model_index, sample_index=sample_index)
            if spec in model_specs:
                plot_item = dict(model=part, spec=spec, color_index=color_index)
                plot_items.append(plot_item)
            color_index += 1

    fig = plot_multiple_sld_profiles(plot_items)
    return fig


@register
async def get_profile_plots(model_specs: List[ModelSpec]):
    fig = await create_profile_plots(model_specs)
    output = to_json_compatible_dict(fig.to_dict())
    del fig
    return output


def get_single_probe_data(theory, probe, substrate=None, surface=None, polarization="", include_data=True):
    fresnel_calculator = probe.fresnel(substrate, surface)
    direction_multiplier = -1.0 if probe.back_reflectivity else 1.0
    calc_Q = probe.calc_Q
    Q, FQ = probe.apply_beam(calc_Q, fresnel_calculator(calc_Q * direction_multiplier))
    Q, R = theory
    output: Dict[str, Union[str, np.ndarray]]
    assert isinstance(FQ, np.ndarray)
    if len(Q) != len(probe.Q):
        # Saving interpolated data
        output = dict(Q=Q, theory=R, fresnel=np.interp(Q, probe.Q, FQ))
    elif getattr(probe, "R", None) is not None:
        output = dict(Q=probe.Q, dQ=probe.dQ, theory=R, fresnel=FQ)
        if include_data:
            # R and dR are the measured values; they never change during a fit,
            # so they can be omitted from per-update payloads (see get_plot_data).
            output["R"] = probe.R
            output["dR"] = probe.dR
    else:
        output = dict(Q=probe.Q, dQ=probe.dQ, theory=R, fresnel=FQ)
    output["background"] = probe.background.value
    output["intensity"] = probe.intensity.value
    output["polarization"] = polarization
    output["label"] = probe.label()
    return output


def get_probe_data(theory, probe, substrate=None, surface=None, include_data=True):
    if isinstance(probe, PolarizedNeutronProbe):
        output = []
        for xsi, xsi_th, suffix in zip(probe.xs, theory, ("--", "-+", "+-", "++")):
            if xsi is not None:
                output.append(get_single_probe_data(xsi_th, xsi, substrate, surface, suffix, include_data=include_data))
        return output
    elif isinstance(probe, ProbeSet):
        return [get_single_probe_data(t, p, substrate, surface, include_data=include_data) for p, t in probe.parts(theory)]
    else:
        return [get_single_probe_data(theory, probe, substrate, surface, include_data=include_data)]


@register
async def get_model_names():
    problem = state.problem.fitProblem
    if problem is None:
        return None
    output: List[Dict] = []
    for model_index, model in enumerate(problem.models):
        if isinstance(model, Experiment):
            output.append(dict(name=model.name, part_name=None, model_index=model_index, part_index=0))
        elif isinstance(model, MixedExperiment):
            for part_index, part in enumerate(model.parts):
                output.append(
                    dict(name=model.name, part_name=part.name, model_index=model_index, part_index=part_index)
                )
    return output


@lru_cache(maxsize=30)
def _get_profile_uncertainty_plot(
    auto_align: bool = True,
    align: float = 0.0,
    nshown: int = 5000,
    npoints: int = 5000,
    random: bool = True,
    residuals: bool = False,
    latest_timestamp: Optional[str] = None,
):
    if state.problem is None or state.problem.fitProblem is None:
        return None
    fitProblem = deepcopy(state.problem.fitProblem)
    uncertainty_state = state.fitting.fit_state
    align_arg = "auto" if auto_align else align
    if uncertainty_state is not None and hasattr(uncertainty_state, "draw"):
        import time

        start_time = time.time()
        logger.info(f"queueing new profile uncertainty plot... {start_time}")
        error_points = error_points_from_state(uncertainty_state, nshown=nshown, random=random, portion=None)
        logger.info(f"points calculated: {time.time() - start_time}")
        errs = calc_errors(fitProblem, error_points)
        logger.info(f"errors calculated: {time.time() - start_time}")
        error_result = show_errors(errs, npoints=npoints, align=align_arg, residuals=residuals)
        error_result["fig"] = error_result["fig"].to_dict()
        logger.info(f"time to render but not serialize... {time.time() - start_time}")
        output = to_json_compatible_dict(error_result)
        del error_result
        end_time = time.time()
        logger.info(f"time to draw profile uncertainty plot: {end_time - start_time}")
        return output
    else:
        return None


@register
async def get_profile_uncertainty_plot(
    auto_align: bool = True,
    align: float = 0.0,
    nshown: int = 5000,
    npoints: int = 5000,
    random: bool = True,
    residuals: bool = False,
    latest_timestamp: Optional[str] = None,
):
    result = await asyncio.to_thread(
        _get_profile_uncertainty_plot,
        auto_align=auto_align,
        align=align,
        nshown=nshown,
        npoints=npoints,
        random=random,
        residuals=residuals,
        latest_timestamp=latest_timestamp,
    )
    return result


@register
async def load_probe_from_file(pathlist: List[str], filename: str, model_index: int = 0, fwhm: bool = True):
    path = Path(*pathlist)
    fitProblem = state.problem.fitProblem if state.problem is not None else None
    if fitProblem is None:
        await log("Error: Can't load data if no problem defined")
    else:
        models = list(fitProblem.models)
        num_models = len(models)
        if model_index >= num_models:
            await log(f"Error: Can not access model at model_index {model_index} (only {num_models} defined)")
            return
        model: Experiment = models[model_index]
        probe = load4(str(path / filename), FWHM=fwhm)
        model.probe = probe
        fitProblem.model_reset()
        fitProblem.model_update()
        state.save()
        state.shared.updated_model = now_string()
        state.shared.updated_parameters = now_string()
        await add_notification(content=f"from {filename} to model {model_index}", title="Data loaded:", timeout=2000)


@register
async def export_model_script(pathlist: List[str], filename: str):
    path = Path(*pathlist)
    fitProblem = state.problem.fitProblem if state.problem is not None else None
    if fitProblem is None:
        await log("Error: Can't export model if no problem defined")
    else:
        s = scriptify_fitproblem(fitProblem)
        with open(path / filename, "w") as f:
            f.write(s)
        await add_notification(content=f"to {filename}", title="Model exported:", timeout=2000)


@register
async def export_results(export_path: Union[str, List[str]] = ""):
    """Override bumps' export to also write a spreadsheet-friendly ``<model>-pars.csv``.

    Runs the standard bumps export bundle (.par, .out, plots, -fit.json, ...) and
    then adds an Excel-ready CSV of the fit parameters. See :mod:`.export_csv`.
    """
    problem_state = state.problem
    if problem_state is None or problem_state.fitProblem is None:
        logger.warning("Export failed: no problem loaded.")
        return

    problem = deepcopy(problem_state.fitProblem)
    serializer = problem_state.serializer
    fit = deepcopy(state.fitting)

    if not isinstance(export_path, list):
        export_path = [export_path]
    path = Path(*export_path).expanduser().absolute()
    notification_id = await add_notification(content=f"<span>{str(path)}</span>", title="Export started", timeout=None)
    try:
        await to_thread(_export_with_csv, path, problem, fit, serializer)
    finally:
        await emit("cancel_notification", notification_id)


def _export_with_csv(path, problem, fit, serializer, basename=None):
    # Derive the basename up front (mirrors bumps' export_fit logic) and pass it
    # explicitly to both writers. This guarantees the CSV sits next to the rest of
    # the bundle with the same prefix, and -- crucially -- lets us write the CSV
    # even when export_fit dies partway through.
    if not basename:
        problem_name = getattr(problem, "name", None) or "model"
        problem_path = getattr(problem, "path", None) or f"{problem_name}.py"
        basename = Path(problem_path).with_suffix("").name

    # Standard bumps bundle (.par, .out, plots, -fit.json, ...). The regular files
    # are written early; the uncertainty/error plots run last and are NOT guarded
    # by bumps. On a large simultaneous DREAM fit that tail can raise after the
    # regular files already landed -- which previously skipped the CSV entirely.
    export_error: Optional[Exception] = None
    try:
        export_fit(path, problem, fit, serializer, basename)
    except Exception as exc:
        export_error = exc
        logger.error(f"Standard export bundle failed partway: {exc}", exc_info=True)

    # The CSV is logically independent of export_fit -- always attempt it.
    try:
        out = write_parameters_csv(problem, fit, Path(path) / f"{basename}-pars.csv")
        logger.info(f"Wrote fit-parameter CSV: {out}")
    except Exception as exc:  # never let the CSV break the rest of the export
        logger.error(f"Error writing {basename}-pars.csv: {exc}", exc_info=True)

    # Re-surface the original export failure after the CSV has been salvaged, so
    # the user is still told the standard bundle was incomplete.
    if export_error is not None:
        raise export_error


@lru_cache(maxsize=1)
def _get_drives() -> List[str]:
    if hasattr(os, "listdrives"):
        return os.listdrives()
    if sys.platform == "win32":
        import ctypes

        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        return [f"{chr(65 + i)}:\\" for i in range(26) if bitmask & (1 << i)]
    return ["/"]


def _get_dirlisting_sync(pathlist: Optional[List[str]] = None):
    """Directory listing that avoids per-subfolder glob (network drive safe)."""
    subfolders = []
    files = []
    path = Path(state.base_path) if (pathlist is None or len(pathlist) == 0) else Path(*pathlist)
    if not path.exists():
        return {"error": f"Path does not exist: {path}"}

    abs_path = path.absolute()
    try:
        entries = list(abs_path.iterdir())
    except PermissionError:
        return {"error": f"Permission denied: {abs_path}"}
    except OSError as exc:
        return {"error": f"Cannot read directory: {exc}"}

    for p in entries:
        try:
            stat = p.stat()
        except (OSError, PermissionError):
            continue
        mtime = stat.st_mtime
        fileinfo = {"name": p.name, "modified": mtime}
        if p.is_dir():
            fileinfo["size"] = 0
            subfolders.append(fileinfo)
        else:
            fileinfo["size"] = stat.st_size
            files.append(fileinfo)

    drives = _get_drives()
    return dict(drives=drives, pathlist=abs_path.parts, subfolders=subfolders, files=files)


@register
async def get_dirlisting(pathlist: Optional[List[str]] = None):
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_get_dirlisting_sync, pathlist),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        path_str = str(Path(*pathlist)) if pathlist else "(base)"
        return {"error": f"Timed out reading {path_str} — network drive may be unreachable"}
    return result
