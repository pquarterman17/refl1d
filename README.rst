Refl1D
======

Refl1D is a program for analyzing 1-D reflectometry measurements made with
X-ray and neutron beamlines.  The 1-D models give the depth profile for
material scattering density composed of a mixture of flat and continuously
varying freeform layers. With polarized neutron measurements, scientists
can study the sub-surface structure of magnetic samples. The architecture
supports the addition of specialized layer types such as models for the
density distribution of polymer brushes, and volume space modeling for
proteins in bio-membranes. We provide a number of these models as well as
supporting user defined layer types for both structural and magnetic
scattering densities.

Fitting is provided by Bumps, a bayesian uncertainty analysis program.  In
addition to the usual uncertain estimated from the covariance at the best
fit location, Bumps includes a Markov chain Monte Carlo analysis code which
more completely describes the uncertain and correlations between parameters.
Fitting is done in parallel, either using python multiprocessing on a
multicore machine, or using MPI for running on a cluster.

**This is a fork.** `pquarterman17/refl1d <https://github.com/pquarterman17/refl1d>`_ tracks
`reflectometry/refl1d <https://github.com/reflectometry/refl1d>`_ and adds X-ray reflectivity,
webview, and file-browser improvements. Fork-specific notes — install, scripting, fit settings,
and divergence from upstream — live in the `fork wiki
<https://github.com/pquarterman17/refl1d/wiki>`_.

Upstream documentation is available at `<https://refl1d.readthedocs.io>`_. See
`CHANGES.rst <https://github.com/reflectometry/refl1d/blob/master/CHANGES.rst>`_
for details on recent changes.


Installation
------------

There are several ways to install, depending on whether you want a turnkey app or a developer
checkout. Full details are on the
`How-To-Install <https://github.com/pquarterman17/refl1d/wiki/How-To-Install>`_ wiki page.

**Windows installer (recommended for most users).** Download
``refl1d-<version>-Windows-x86_64-installer.exe`` from the fork's
`releases page <https://github.com/pquarterman17/refl1d/releases>`_ and run it. It bundles its
own Python environment (nothing else to install), installs per-user (no administrator rights),
and adds Start Menu shortcuts. The fork build is unsigned, so Windows SmartScreen will warn —
choose *More info → Run anyway*.

**From PyPI (upstream release).** ``pip install refl1d`` installs the upstream package from PyPI.
Note that this does **not** include this fork's changes — use the Windows installer or a source
install for those.

**From source (developers).** Requires `uv <https://docs.astral.sh/uv/>`_ and git::

    git clone https://github.com/pquarterman17/refl1d.git
    cd refl1d
    uv sync

Then launch the two dev servers (``make dev-backend`` + ``make dev-frontend``) for the webview UI.

**Offline / restricted machines.** Download the ``offline-install`` branch as a zip (no git
required) and run ``pip install .``. An air-gapped wheel bundle is also documented on the wiki.


Running Refl1D
--------------

The ``refl1d`` command starts the webview application; point it at a model script to load a model,
or run a fit headlessly with no browser. See
`How-To-Run-A-Fit <https://github.com/pquarterman17/refl1d/wiki/How-To-Run-A-Fit>`_ (interactive)
and `How-To-Command-Line <https://github.com/pquarterman17/refl1d/wiki/How-To-Command-Line>`_
(headless/batch and every option) for the full workflow.

**Graphical (webview).** ::

    refl1d                 # open the web UI
    refl1d model.py        # open the UI with a model loaded

**Headless / batch (no browser).** ::

    refl1d model.py --chisq                                # evaluate the model and exit
    refl1d --batch --session=fit.h5 model.py --fit=dream   # run a fit to completion, save to a session
    refl1d -x model.py                                     # run the server without opening a browser

A model file may live anywhere on disk — Refl1D switches into the script's own directory when it
loads, so relative data paths resolve next to the model and a self-contained model folder is
portable.

**Profile uncertainty (after a DREAM fit).** ::

    refl1d align model.py fit.h5

For what each optimizer setting does (population, restarts, burn-in, tolerances), see
`Fit-Settings <https://github.com/pquarterman17/refl1d/wiki/Fit-Settings>`_.


Contributing
------------

Submit issues and pull requests on the fork's
`GitHub page <https://github.com/pquarterman17/refl1d>`_. Changes that are useful beyond the fork
are sent upstream to `reflectometry/refl1d <https://github.com/reflectometry/refl1d>`_; when
contributing there, branch from ``upstream/master`` so fork-only files don't land in the PR.

|CI| |RTD| |DOI|

.. |CI| image:: https://github.com/pquarterman17/refl1d/actions/workflows/test.yml/badge.svg
   :alt: Build status
   :target: https://github.com/pquarterman17/refl1d/actions

.. |DOI| image:: https://zenodo.org/badge/DOI/10.5281/zenodo.1249715.svg
   :alt: DOI tag
   :target: https://zenodo.org/doi/10.5281/zenodo.1249715

.. |RTD| image:: https://readthedocs.org/projects/refl1d/badge/?version=latest
   :alt: Documentation status
   :target: https://refl1d.readthedocs.io/en/latest
