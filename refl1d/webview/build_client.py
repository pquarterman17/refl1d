import os
from pathlib import Path
import re
import shutil
import subprocess

from bumps import webview as bumps_webview


def _run(cmd: str) -> None:
    """Run a shell command and raise if it fails.

    Uses ``subprocess.run(..., check=True)`` so a non-zero exit raises a
    ``CalledProcessError`` on both POSIX and Windows. The original build used
    ``os.system`` and effectively ignored the status, so a failed ``npm
    install`` or ``npm run build`` printed "Done." and exited 0 — shipping an
    empty or partial ``dist`` that serves a blank page to users. Fail loudly
    instead, in CI where it belongs. (``os.system`` also returns a wait-status
    on POSIX, not a plain exit code, so the old comparison was wrong there.)
    """
    subprocess.run(cmd, shell=True, check=True)


def build_client(
    no_deps=False,
    sourcemap=False,
    cleanup=False,
):
    """Build the refl1d webview client."""

    def cleanup_bumps_packages():
        for bumps_package_file in client_dir.glob("bumps-webview-client*.tgz"):
            bumps_package_file.unlink()

    if shutil.which("bun"):
        tool = "bun"
    elif shutil.which("npm"):
        tool = "npm"
    else:
        raise RuntimeError("npm/bun is not installed. Please install either npm or bun.")

    client_dir = (Path(__file__).parent / "client").resolve()
    node_modules = client_dir / "node_modules"
    os.chdir(client_dir)

    if not no_deps or not node_modules.exists():
        print("Installing node modules...")
        _run(f"{tool} install")

    print("Reinstalling bumps...")
    cleanup_bumps_packages()

    # pack it up for install...
    bumps_dir = Path(bumps_webview.__file__).parent / "client"
    if tool == "bun":
        os.chdir(bumps_dir)
        _run(f"bun pm pack {bumps_dir} --destination {client_dir}")
        os.chdir(client_dir)
    else:
        _run(f"npm pack {bumps_dir} --quiet")

    # install packed library
    bumps_package_file = next(client_dir.glob("bumps-webview-client*.tgz"))
    _run(f"{tool} install {bumps_package_file} --no-save")

    # build the client
    print("Building the webview client...")
    cmd = f"{tool} run build"
    if sourcemap:
        cmd += " -- --sourcemap"
    _run(cmd)

    # Verify the build actually produced a servable client. The server serves
    # client/dist/index.html at "/" and client/dist/assets/* for the JS bundle;
    # a missing index.html shows a "Client not built" page, and missing assets
    # show a blank white page. Catch both here so a broken build never ships.
    dist_dir = client_dir / "dist"
    index_html = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"
    if not index_html.exists():
        raise RuntimeError(f"Build did not produce {index_html}")
    if not assets_dir.is_dir() or not any(assets_dir.iterdir()):
        raise RuntimeError(f"Build did not produce any assets in {assets_dir}")

    # "assets dir is non-empty" is not enough: a stale or partially written dist
    # can leave index.html pointing at a hashed bundle that isn't actually
    # present, which 404s the JS/CSS at runtime and serves a blank white tab with
    # no visible error. Parse index.html and confirm every local JS/CSS bundle it
    # references exists on disk. (External URLs like the MathJax CDN don't start
    # with ./assets and are intentionally ignored.)
    html = index_html.read_text(encoding="utf-8")
    referenced = re.findall(r'(?:src|href)="\.?/?(assets/[^"]+\.(?:js|css))"', html)
    if not referenced:
        raise RuntimeError(f"Build index.html references no local JS/CSS assets: {index_html}")
    missing = [ref for ref in referenced if not (dist_dir / ref).exists()]
    if missing:
        raise RuntimeError(f"Build index.html references missing assets: {missing}")

    if cleanup:
        print("Cleaning up...")
        shutil.rmtree(node_modules)
        cleanup_bumps_packages()
        print("Removed node_modules folders.")

    print("Done.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build the webview client.")
    parser.add_argument("--no-deps", action="store_true", help="Don't install npm dependencies.")
    parser.add_argument("--sourcemap", action="store_true", help="Generate sourcemaps.")
    parser.add_argument("--cleanup", action="store_true", help="Remove the node_modules directory.")
    args = parser.parse_args()
    build_client(
        no_deps=args.no_deps,
        sourcemap=args.sourcemap,
        cleanup=args.cleanup,
    )
