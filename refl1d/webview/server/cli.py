"""
***Warning***: importing cli modifies the behaviour of bumps
"""

import sys
import asyncio
from pathlib import Path

from bumps.webview.server import cli

from . import api  # uses side-effects to register refl1d functions
from refl1d import __version__

# Register the refl1d model loader
# and the serialized model migrations
from refl1d.bumps_interface import fitplugin
from bumps.cli import install_plugin

install_plugin(fitplugin)

CLIENT_PATH = Path(__file__).parent.parent / "client"


def _build_identity() -> str:
    """One-glance "which install is this?" summary (fork-only diagnostic).

    The classic trap on a shared/work machine is a stale ``pip install refl1d``
    on PATH shadowing the fork build. The ``+local`` segment in the version
    (e.g. ``1.0.2+pq3``) is the fork fingerprint; printing the executable and
    package paths makes it unambiguous which copy is actually running.
    """
    import os

    import refl1d

    try:
        import bumps

        bumps_ver = bumps.__version__
    except Exception:
        bumps_ver = "?"
    pkg = os.path.dirname(os.path.abspath(refl1d.__file__))
    tag = " (fork build)" if "+" in __version__ else ""
    return (
        f"refl1d {__version__}{tag}\n"
        f"  executable : {sys.executable}\n"
        f"  package    : {pkg}\n"
        f"  bumps      : {bumps_ver}"
    )


def main():
    # Fork-only: a quick, non-launching "which build am I?" probe. Uses --where
    # so it does not collide with bumps' own --version (handled by plugin_main).
    if len(sys.argv) > 1 and sys.argv[1] in ("--where", "--build-info"):
        print(_build_identity())
        return
    if len(sys.argv) > 1 and sys.argv[1] == "align":
        # Command line tool to regenerate the profile uncertainty plot:
        #
        #   refl1d align <model>.py <store> [<layer>.<offset>] [0|1|2|n]
        #
        from refl1d.uncertainty import run_errors

        del sys.argv[1]
        run_errors()
    else:
        # Fork-only: stamp the running install on stderr so the startup banner
        # makes a shadowing stock install immediately obvious.
        print(_build_identity(), file=sys.stderr)
        cli.plugin_main(name="refl1d", client=CLIENT_PATH, version=__version__)


def start_refl1d_server():
    """
    Start a Jupyter server for the webview.
    This returns an asyncio.Task object that should be awaited
    to ensure the server starts without exceptions.
    """
    from bumps.webview.server import api
    from bumps.webview.server.webserver import start_app

    api.state.app_name = "refl1d"
    api.state.app_version = __version__
    api.state.client_path = CLIENT_PATH

    return asyncio.create_task(start_app(jupyter_link=True))


if __name__ == "__main__":
    main()
