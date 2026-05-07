# Refl1d Codebase Baseline Map

**Created:** 2026-05-06
**Branch:** custom/main (fork of reflectometry/refl1d)

## Architecture Overview

Refl1d is a full-stack reflectometry fitting tool: Python backend (with C++/Numba reflectivity kernels) + Vue 3/TypeScript webview frontend, built on top of the **bumps** optimization framework.

```
refl1d/
├── sample/          # Domain model: layers, materials, magnetism
│   ├── layers.py        # Slab, Stack, Repeat — operator-overloaded DSL (Si | Ni | air)
│   ├── material.py      # Scatterer hierarchy: SLD, Material variants, Mixture, Compound
│   ├── magnetism.py     # BaseMagnetism, Magnetism, MagnetismTwist, FreeMagnetism
│   ├── reflectivity.py  # Dispatcher to backend (Abeles matrix algorithm)
│   ├── flayer.py        # FunctionalProfile — arbitrary SLD(z) from user function
│   ├── polymer.py       # PolymerBrush, PolymerMushroom, EndTetheredPolymer
│   ├── cheby.py         # Chebyshev polynomial SLD profiles
│   ├── mono.py          # FreeLayer / FreeInterface (monospline control points)
│   └── materialdb.py    # Pre-built materials (air, silicon, gold, etc.)
│
├── probe/           # Instrument model: probes, resolution, data loading
│   ├── probe.py         # BaseProbe → Probe → XrayProbe / NeutronProbe
│   │                    # QProbe (Q-space only), ProbeSet, PolarizedNeutronProbe
│   ├── resolution.py    # Q↔(θ,λ) conversions, dQ broadening
│   ├── fresnel.py       # Single-interface Fresnel reflectivity
│   ├── instrument.py    # Monochromatic / Pulsed instrument definitions
│   ├── oversampling.py  # Critical-edge and general oversampling
│   ├── stitch.py        # Multi-angle data stitching
│   └── data_loaders/    # NCNR, SNS, ANSTO, ORSO (.ort), MLayers (.staj)
│
├── lib/             # Reflectivity calculation backends
│   ├── python/          # Pure Python reference (Abeles matrix, convolution)
│   ├── numba/           # Numba @njit wrappers (default backend)
│   └── c/               # C++ extension (reflmodule.cc) — optional, fastest
│
├── experiment.py    # Experiment + MixedExperiment — connects sample+probe, computes R(Q)
├── profile.py       # Microslabs — renders layer stack to discrete SLD profile
├── uncertainty.py   # MCMC error propagation and profile uncertainty contours
├── backends.py      # Backend selector (REFL1D_BACKEND env var: numba|python|c_ext)
├── names.py         # Public API surface — all user-facing imports
│
├── bumps_interface/ # Integration with bumps optimizer
│   ├── fitplugin.py     # Model loader/saver, bumps plugin registration
│   └── migrations.py    # JSON schema version migrations
│
├── webview/         # Web-based GUI
│   ├── server/          # Flask-like API over Socket.IO (via bumps webview)
│   │   ├── cli.py           # Entry point: refl1d CLI + Jupyter launcher
│   │   ├── api.py           # 6 RPC endpoints (plot data, profiles, uncertainty, load, export)
│   │   ├── profile_plot.py  # Plotly SLD profile figures
│   │   ├── profile_uncertainty.py  # Uncertainty contour generation
│   │   ├── scriptify.py     # FitProblem → executable Python script export
│   │   └── colors.py        # Colorblind-friendly palette
│   └── client/          # Vue 3 + TypeScript SPA (Vite build)
│       ├── src/
│       │   ├── main.js              # App entry, socket.io init
│       │   ├── components/
│       │   │   ├── DataView.vue         # Reflectivity plot (4 view modes)
│       │   │   ├── ModelView.vue        # SLD profile plot
│       │   │   ├── SimpleBuilder.vue    # Layer editor UI (non-magnetic only)
│       │   │   └── ProfileUncertaintyView.vue  # MCMC uncertainty contours
│       │   ├── model.ts             # TypeScript interfaces for serialized models
│       │   ├── panels.ts            # Panel definitions (extends bumps panels)
│       │   └── fitter_defaults.ts   # Default params for 6 fitting algorithms
│       └── package.json
│
├── wx_gui/          # DEPRECATED — legacy wxPython GUI (excluded from tests)
├── deprecated/      # Old magnetic/freeform APIs (still re-exported for compat)
├── validation/      # Gepore Fortran reference implementation for cross-validation
└── utils/           # Support utilities
```

---

## Key Design Patterns

### 1. DSL-style model building (operator overloading)
```python
sample = Si(0, 5) | SiO2(25, 3) | Au(100, 5) | air
```
`Scatterer.__or__` and `__call__` are monkey-patched at import time in `layers.py:680-721`. Materials become Slabs automatically when piped together.

### 2. Pluggable reflectivity backends
Three implementations of the same algorithms (Abeles matrix, Nevot-Croce roughness, resolution convolution). Selected at runtime via `REFL1D_BACKEND` env var or `refl1d.use("numba")`. Default: numba.

### 3. Bumps parameter system
All fittable values are `bumps.Parameter` objects. Constraints are expressions between parameters. The `Experiment` class implements bumps' `Fitness` interface (nllf, residuals, parameters).

### 4. Event-driven webview
Socket.IO WebSocket with RPC-style calls. Server holds all scientific state; client is a thin display layer. Events: `updated_parameters`, `model_loaded`, `updated_uncertainty`.

### 5. Microslabbing
Continuous SLD profiles are discretized into thin slabs (`profile.py:Microslabs`). Roughness is applied via error-function blending (Nevot-Croce), then similar slabs are contracted to a tolerance `dA`.

---

## Probe Types and Radiation Support

| Probe Type | Radiation | Composition Lookup | Polarized | Q-only |
|---|---|---|---|---|
| `NeutronProbe` | neutron | neutron_sld() | No | No |
| `XrayProbe` | xray | xray_sld() | No | No |
| `QProbe` | — | No | No | Yes |
| `PolarizedNeutronProbe` | neutron | neutron_sld() | Yes (4 xs) | No |
| `PolarizedQProbe` | — | No | Yes | Yes |
| `ProbeSet` | any | Varies | No | No |

**XRR-specific note:** `XrayProbe` uses only the first wavelength (`unique_L[0]`) for scattering factor calculation — no polychromatic or energy-dependent support.

---

## Data Flow: Fitting

```
User defines model (Python script or Builder UI)
  → Experiment(sample, probe) created
  → FitProblem(experiment) wraps for bumps
  → bumps optimizer calls experiment.nllf()
    → experiment.reflectivity()
      → sample.render() → Microslabs
      → reflectivity_amplitude(kz, depth, rho, irho, sigma) [Abeles matrix]
      → convolve() with instrument resolution
    → residuals = (R_theory - R_data) / dR
    → nllf = 0.5 * sum(residuals²)
```

---

## Build & CI

- **Package manager:** uv
- **Version:** versioningit from git tags (current: 1.0.1b0)
- **C extension:** Optional, built via `setup.py` when `BUILD_EXTENSION` set
- **CI matrix:** Linux (3.10-3.13), Windows (3.12, 3.14), macOS (3.12)
- **Frontend:** Vite build, bun or npm; eslint + biome linting
- **Docs:** Sphinx with haiku theme, deployed to ReadTheDocs + GitHub Pages
- **Distributables:** NSIS (Windows), DMG with notarization (macOS), tar.gz (Linux)

---

## Entry Points

| Command | What it does |
|---|---|
| `refl1d` | Launch webview server (primary) |
| `refl1d align <model> <store>` | Regenerate profile uncertainty |
| `python -m refl1d` | Same as `refl1d` |
| `python -m refl1d.webview.server` | Same as `refl1d` |

---

## Test Coverage Summary

| Area | Coverage | Notes |
|---|---|---|
| Reflectivity calc | Good | abeles, fresnel tests |
| Resolution | Good | resolution, oversampling |
| Data loaders | Moderate | NCNR, SNS, ANSTO, ORSO |
| Sample models | Moderate | stack, polymer; missing mixture/compound |
| Magnetism | Moderate | polarized probe, alignment |
| Experiment serialization | Good | 8 test classes in test_experiment |
| Webview frontend | Minimal | Only build/lint/type checks; e2e commented out |
| Webview server API | None | No endpoint tests |
| Functional layers | Sparse | No dedicated tests |
| Constraints/bounds | Sparse | TODOs in test_bounds.py |

---

## Dependencies on Bumps

Refl1d is tightly coupled to bumps for:
- Parameter system (`bumps.parameter.Parameter`)
- Fitting algorithms (DREAM, LM, DE, Amoeba, MPFit, Newton)
- FitProblem / MultiFitProblem wrappers
- Webview server infrastructure (Socket.IO, state management, file browser)
- JSON serialization schema (bumps-draft-02)
- CLI framework

Breaking changes in bumps directly break refl1d. The dependency is pinned to `>=1.0.0a12`.
