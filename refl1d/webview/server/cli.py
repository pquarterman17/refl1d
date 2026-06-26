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


def _check_client_build() -> str:
    """Verify the built webview client the server will serve actually exists.

    The server serves ``client/dist/index.html`` at ``/`` and the hashed
    ``client/dist/assets/*`` bundles it references. A missing ``dist`` or a
    referenced bundle that isn't on disk is exactly what produces a blank white
    tab at runtime. Mirror the build-time guard here so an end user can confirm
    the packaged client is intact without DevTools.
    """
    import re

    dist = CLIENT_PATH / "dist"
    index_html = dist / "index.html"
    if not index_html.exists():
        return f"PROBLEM: built client missing ({index_html} not found) -- this causes a blank page"
    try:
        html = index_html.read_text(encoding="utf-8")
    except Exception as exc:
        return f"PROBLEM: could not read {index_html}: {exc}"
    referenced = re.findall(r'(?:src|href)="\.?/?(assets/[^"]+\.(?:js|css))"', html)
    if not referenced:
        return f"PROBLEM: {index_html} references no local JS/CSS bundles (stale/partial build)"
    missing = [ref for ref in referenced if not (dist / ref).exists()]
    if missing:
        return f"PROBLEM: index.html references {len(missing)} missing bundle(s): {missing} -- this causes a blank page"
    return f"OK ({len(referenced)} bundle(s) present at {dist})"


def _default_browser() -> str:
    """Best-effort Windows default-browser check.

    An Internet Explorer / legacy default browser can't run the ES-module client
    and shows a blank tab even when everything else is fine, so flag it.
    """
    if sys.platform != "win32":
        return f"(not checked on {sys.platform})"
    try:
        import winreg

        key = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            prog_id, _ = winreg.QueryValueEx(k, "ProgId")
        if "IE" in prog_id or "InternetExplorer" in prog_id:
            return f"{prog_id}  <-- WARNING: Internet Explorer cannot run Refl1D; set Chrome or Edge as default, or paste the URL into Chrome/Edge"
        return prog_id
    except Exception as exc:
        return f"(could not determine: {exc})"


def run_self_diagnostic() -> None:
    """Write a human-readable diagnostic report, print it, and open it.

    Runs directly under ``python.exe`` (``python -m refl1d --diagnose``) so it
    works on locked-down machines where ``.bat``/PowerShell scripts are blocked.
    Writes the report next to the bundled ``python.exe`` (and falls back to the
    temp dir), then opens it so the user can read/screenshot/send it without
    needing DevTools or knowing how to copy from a console.
    """
    import os
    import platform
    import tempfile

    lines = ["Refl1D self-diagnostic", "======================", ""]
    lines.append("[build]")
    lines.append(_build_identity())
    lines.append("")
    lines.append(f"[python]  {sys.version.splitlines()[0]}")
    lines.append(f"[platform]  {platform.platform()}")
    lines.append("")

    lines.append("[CSV parameter export feature]")
    try:
        import refl1d.webview.server.export_csv as _m

        present = hasattr(_m, "write_parameters_csv")
        lines.append("  present" if present else "  MISSING")
    except Exception as exc:
        lines.append(f"  MISSING ({exc})")
    lines.append("")

    lines.append("[webview client build]  (a problem here = blank white tab)")
    lines.append(f"  {_check_client_build()}")
    lines.append("")

    lines.append("[default browser]")
    lines.append(f"  {_default_browser()}")
    lines.append("")
    lines.append("Done. Please send this file to support.")

    report = "\n".join(lines)
    print(report)

    out_path = None
    for candidate in (Path(sys.executable).parent / "refl1d_diag.txt", Path(tempfile.gettempdir()) / "refl1d_diag.txt"):
        try:
            candidate.write_text(report, encoding="utf-8")
            out_path = candidate
            break
        except Exception:
            continue
    if out_path is not None:
        print(f"\nSaved to: {out_path}")
        try:
            os.startfile(str(out_path))  # type: ignore[attr-defined]  # Windows-only; opens in Notepad
        except Exception:
            pass


def main():
    # Fork-only: a quick, non-launching "which build am I?" probe. Uses --where
    # so it does not collide with bumps' own --version (handled by plugin_main).
    if len(sys.argv) > 1 and sys.argv[1] in ("--where", "--build-info"):
        print(_build_identity())
        return
    # Fork-only: a script-free self-diagnostic (writes + opens a report file),
    # for locked-down machines where the .bat/PowerShell diagnostics are blocked.
    if len(sys.argv) > 1 and sys.argv[1] in ("--diagnose", "--selfcheck", "--doctor"):
        run_self_diagnostic()
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
