# Bugs and Issues Found During Codebase Exploration

**Created:** 2026-05-06
**Branch:** custom/main
**Status:** Cataloged only — none fixed yet

---

## Tier 1 — Likely Bugs

### B1. XrayProbe uses only first wavelength for SLD calculation
- **File:** `refl1d/probe/probe.py` ~line 1089
- **Issue:** `XrayProbe.scattering_factors()` calls `xsf.xray_sld()` with `self.unique_L[0]` only. For polychromatic X-ray data or energy scans near absorption edges, f' and f'' are assumed constant across all Q points.
- **Impact:** Incorrect SLD for energy-dependent measurements (rare earths near edges, resonant XRR). Silent — no warning emitted.
- **TODO in code:** "TODO: support wavelength dependent systems"

### B2. Mixture fractions can exceed 100% — returns NaN silently
- **File:** `refl1d/sample/material.py` ~line 645-672
- **Issue:** `Mixture._density()` does not penalize or clamp fractions > 1.0. Returns NaN, which propagates silently through fitting.
- **Impact:** Fitting can wander into unphysical parameter space with no feedback. Should either apply a penalty function or clamp.

### B3. `irho` forced positive, may mask absorption sign bugs
- **File:** `refl1d/profile.py` ~line 369
- **Issue:** `irho = abs(irho) + 1e-30` forces imaginary SLD positive. If a material or calculation produces negative irho (which can be physical for certain magnetic configurations), this silently corrects it.
- **Impact:** Could hide bugs in absorption calculations or magnetic SLD profiles.

### B4. Experiment.dz calculation assumes probe has `.Q` attribute directly
- **File:** `refl1d/experiment.py` ~line 416
- **Issue:** `dz = nice((2 * pi / probe.Q.max()) / 10)` — PolarizedNeutronProbe doesn't expose Q directly the same way. May fail or compute wrong dz.
- **Impact:** Potential crash or wrong microslab resolution for polarized experiments.

### B5. Convolve functions fail on unsorted input
- **File:** `refl1d/lib/python/convolve.py` ~lines 165, 197
- **Issue:** FIXME comments: "fails if xin are not sorted; slow if x not sorted". No sort guard or validation.
- **Impact:** Silent wrong results if input Q array is not monotonically increasing.

### B6. Fresnel calculator silently overrides when Srho == Vrho
- **File:** `refl1d/probe/probe.py` ~line 314-315
- **Issue:** When substrate and vacuum SLD are equal, the Fresnel normalization silently changes behavior without warning the user.
- **Impact:** Unexpected normalization in R/Fresnel plots.

---

## Tier 2 — Design Issues / Technical Debt

### B7. ProbeCache uses object `id()` for cache keys
- **File:** `refl1d/sample/material.py` ~line 706
- **Issue:** `id()` can be recycled by Python's memory allocator if a material object is deleted and a new one created. Cache could return stale values for a different material.
- **Impact:** Unlikely in practice but possible during interactive sessions with frequent model rebuilding.

### B8. Deprecated magnetic classes still exported from `names.py`
- **File:** `refl1d/names.py`
- **Issue:** `FreeMagnetic`, `MagneticSlab`, `MagneticStack`, `MagneticTwist` imported from `deprecated/magnetic.py` and re-exported. No deprecation warning emitted.
- **Impact:** Users may unknowingly use old API that lacks features of `sample/magnetism.py`.

### B9. wx_gui still referenced from fitplugin
- **File:** `refl1d/bumps_interface/fitplugin.py` ~line 38
- **Issue:** `data_view()` function imports from `refl1d.wx_gui.data_view` — a deprecated, untested module.
- **Impact:** ImportError if wxPython not installed and bumps tries to use the legacy GUI path.

### B10. LRU cache on sync wrapper for async API function
- **File:** `refl1d/webview/server/api.py` ~line 147
- **Issue:** `@lru_cache` on a synchronous wrapper that bridges to async uncertainty computation. Multiple concurrent WebSocket calls could get stale cached results.
- **Impact:** Uncertainty plots may show stale data after model changes.

### B11. SimpleBuilder only handles single, non-magnetic models
- **File:** `refl1d/webview/client/src/components/SimpleBuilder.vue`
- **Issue:** Hard-coded limitation: "can only deal with a single model". No MixedExperiment, no magnetism support in the UI builder.
- **Impact:** Users must write Python scripts for multi-model or magnetic experiments — the GUI is incomplete.

### B12. `getSlot()` returns dummy value instead of null
- **File:** `refl1d/webview/client/src/components/SimpleBuilder.vue` ~line 162
- **Issue:** When a parameter is not found, returns `{value: 0.0}` instead of null/undefined.
- **Impact:** Type safety violation; could silently display wrong parameter values.

### B13. Frontend e2e and unit tests disabled
- **File:** `.github/workflows/test-webview-client.yaml`
- **Issue:** E2E and unit test steps are commented out. Only build, lint, format, and type checks run.
- **Impact:** No runtime testing of frontend behavior in CI.

### B14. Makefile lint targets reference non-existent paths
- **File:** `Makefile`
- **Issue:** Lint targets reference `bumps/`, `run.py`, `test.py` which don't exist in this repo.
- **Impact:** `make lint` may fail or lint wrong files.

---

## Tier 3 — TODOs and Missing Features

### B15. No beam footprint correction for XRR
- **Issue:** X-ray beam has smaller spot than neutron beam. Comment in `layers.py:19-22` notes this causes different effective roughness and thickness variance. Not implemented.
- **Impact:** XRR fits may not account for footprint effects at low angles.

### B16. FunctionalProfile interface roughness not implemented
- **File:** `refl1d/sample/flayer.py` ~line 99-100
- **Issue:** TODO: interface roughness between FunctionalProfile and adjacent layers is not blended.
- **Impact:** Sharp boundaries at functional layer edges even when roughness is specified.

### B17. MagnetismStack interfaces not implemented
- **File:** `refl1d/sample/magnetism.py` ~line 229
- **Issue:** Magnetic interface blending between sub-layers of a MagnetismStack is not implemented.
- **Impact:** Step-function magnetic profiles even when interface widths are set.

### B18. Resolution guard mentioned but not implemented
- **File:** `refl1d/probe/probe.py` ~line 178
- **Issue:** Comment mentions resolution guard to prevent aliasing, but no code implements it.

### B19. No sigma² effects in NLLF
- **File:** `refl1d/experiment.py` ~line 154
- **Issue:** TODO: "add sigma^2 effects back into nllf" — roughness uncertainty not propagated into likelihood.

### B20. 2D mesh resolution not implemented
- **File:** `refl1d/experiment.py` ~line 424
- **Issue:** TODO: "proper 2D mesh resolution over L, T" — R only calculated for first L. Matters for TOF instruments.

### B21. Pickling shims scheduled for removal
- **File:** `refl1d/sample/layers.py` ~lines 297-304, 609-616
- **Issue:** `__setstate__` shims for pre-2024-10-29 pickled Stack/Repeat objects. Comment says "remove in 2026". It's now 2026.

### B22. `incoherent` scattering raises NotImplementedError
- **File:** `refl1d/sample/material.py` ~lines 207, 684
- **Issue:** `use_incoherent` parameter exists on materials but raises NotImplementedError when True.

### B23. TypeScript probe interface incomplete
- **File:** `refl1d/webview/client/src/model.ts`
- **Issue:** Comment in Probe interface: "W... what? should go here?" — fields are guessed/incomplete.

### B24. `plot_cache.ts` is dead code
- **File:** `refl1d/webview/client/src/plot_cache.ts`
- **Issue:** 2-line file with a TODO. No caching implemented. Referenced nowhere.

### B25. `REFL1D_BACKEND` env var undocumented
- **File:** `refl1d/backends.py`
- **Issue:** The environment variable for selecting the calculation backend is not mentioned in any user-facing documentation.

### B26. Webview server API has no endpoint tests
- **Issue:** No test files exercise the 6 Socket.IO RPC endpoints in `api.py`. Server logic is untested.

### B27. `test_bounds.py` is a placeholder
- **File:** `tests/refl1d/test_bounds.py`
- **Issue:** Contains "TODO test the bounds" — no actual test assertions.

### B28. No validation on file paths in `load_probe_from_file`
- **File:** `refl1d/webview/server/api.py`
- **Issue:** `pathlist` parameter passed directly to file operations. No path traversal checks.
- **Impact:** Potential security issue if webview is exposed to network.

### B29. File browser stalls on network drives (FIXED)
- **File:** bumps `webview/server/api.py` → `get_dirlisting()`
- **Issue:** Three compounding problems:
  1. `p.glob("*")` on every subdirectory counts all contents (N network roundtrips per folder)
  2. Redundant `p.exists()` check on every entry (another roundtrip per entry)
  3. Entire function runs synchronously, blocking the event loop — UI freezes
- **Impact:** Navigating to network drives or folders with many subdirectories hangs the UI for 30+ seconds.
- **Fix:** Overridden in `refl1d/webview/server/api.py` — skips subfolder content counting, removes redundant exists() check, runs in a thread with 10s timeout. Upstream-worthy PR candidate.
- **Status:** Fixed on custom/main branch (2026-05-06)
