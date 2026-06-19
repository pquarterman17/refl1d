"""
Tests for dataset-name export filenames and the comment/description header.

Covers:
- ``load4(description=...)`` and the ``# comment:`` header fallback.
- ``Probe.save`` writing ``# name:`` and ``# comment:`` into ``-refl.dat``.
- ``Experiment._export_basename`` appending the dataset name to the basename
  for multi-dataset (indexed) fits only.
"""

import numpy as np

from refl1d.experiment import Experiment, _filename_tag
from refl1d.probe.data_loaders.load4 import load4
from refl1d.probe.probe import NeutronProbe, QProbe
from refl1d.sample.materialdb import air, silicon


def _make_qprobe(name="SampleA", description=None):
    Q = np.linspace(0.01, 0.2, 25)
    dQ = 0.001 * np.ones_like(Q)
    R = np.exp(-Q * 50)
    dR = 0.05 * R
    return QProbe(Q, dQ, R=R, dR=dR, name=name, description=description)


def _make_neutron_probe(name="SampleA", description=None):
    # A NeutronProbe carries angle + wavelength, so the sample SLD can render
    # (needed for a full Experiment.save round-trip).
    T = np.linspace(0.5, 5.0, 25)
    dT = 0.01 * np.ones_like(T)
    L = 5.0 * np.ones_like(T)
    dL = 0.1 * np.ones_like(L)
    R = np.exp(-T)
    dR = 0.05 * R
    return NeutronProbe(T=T, dT=dT, L=L, dL=dL, data=(R, dR), name=name, description=description)


# ---------------------------------------------------------------------------
# load4: description argument and # comment: header fallback
# ---------------------------------------------------------------------------


def _write_refl(path, comment_line=None):
    lines = []
    if comment_line is not None:
        lines.append("# comment: %s" % comment_line)
    Q = np.linspace(0.01, 0.1, 6)
    R = np.exp(-Q * 40)
    dR = 0.05 * R
    dQ = 0.001 * np.ones_like(Q)
    for q, r, dr, dq in zip(Q, R, dR, dQ):
        lines.append("%.6g %.6g %.6g %.6g" % (q, r, dr, dq))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_load4_description_argument(tmp_path):
    filename = _write_refl(tmp_path / "data.refl")
    probe = load4(filename, description="5K field cooled")
    assert probe.description == "5K field cooled"


def test_load4_reads_comment_header(tmp_path):
    filename = _write_refl(tmp_path / "data.refl", comment_line="20K warming, run 3")
    probe = load4(filename)
    assert probe.description == "20K warming, run 3"


def test_load4_argument_overrides_comment_header(tmp_path):
    filename = _write_refl(tmp_path / "data.refl", comment_line="from file")
    probe = load4(filename, description="from script")
    assert probe.description == "from script"


def test_load4_no_comment_leaves_description_none(tmp_path):
    filename = _write_refl(tmp_path / "data.refl")
    probe = load4(filename)
    assert probe.description is None


# ---------------------------------------------------------------------------
# Probe.save: comment + name written into the -refl.dat header
# ---------------------------------------------------------------------------


def test_probe_save_writes_comment_and_name(tmp_path):
    probe = _make_qprobe(name="SampleA", description="5K field cooled")
    out = tmp_path / "out-refl.dat"
    probe.save(str(out), theory=(probe.Q, probe.R))
    text = out.read_text(encoding="utf-8")
    assert "# name: SampleA" in text
    assert "# comment: 5K field cooled" in text


def test_probe_save_omits_intensity_and_background(tmp_path):
    probe = _make_qprobe(name="SampleA", description="note")
    out = tmp_path / "out-refl.dat"
    probe.save(str(out), theory=(probe.Q, probe.R))
    text = out.read_text(encoding="utf-8")
    assert "# intensity:" not in text
    assert "# background:" not in text


def test_probe_save_units_on_separate_row(tmp_path):
    probe = _make_qprobe(name="SampleA")
    out = tmp_path / "out-refl.dat"
    probe.save(str(out), theory=(probe.Q, probe.R))
    text = out.read_text(encoding="utf-8")
    # Units are no longer parenthesised after the column name.
    assert "(1/Å)" not in text
    header_lines = [ln for ln in text.splitlines() if ln.startswith("#")]
    # One row holds the column names (no units)...
    name_rows = [ln for ln in header_lines if "theory" in ln and "fresnel" in ln]
    assert len(name_rows) == 1
    assert "1/Å" not in name_rows[0]
    assert "Q" in name_rows[0] and "dQ" in name_rows[0] and "dR" in name_rows[0]
    # ...and a separate row holds the units, using the Ångström symbol.
    unit_rows = [ln for ln in header_lines if "1/Å" in ln]
    assert len(unit_rows) == 1
    assert "theory" not in unit_rows[0]


def test_probe_save_without_comment_has_no_comment_line(tmp_path):
    probe = _make_qprobe(name="SampleA", description=None)
    out = tmp_path / "out-refl.dat"
    probe.save(str(out), theory=(probe.Q, probe.R))
    text = out.read_text(encoding="utf-8")
    assert "# comment:" not in text
    assert "# name: SampleA" in text


def test_probe_save_multiline_comment_collapsed(tmp_path):
    probe = _make_qprobe(description="line one\nline two")
    out = tmp_path / "out-refl.dat"
    probe.save(str(out), theory=(probe.Q, probe.R))
    comment_lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.startswith("# comment:")]
    assert comment_lines == ["# comment: line one line two"]


# ---------------------------------------------------------------------------
# Experiment basename: append name for indexed (multi-dataset) exports only
# ---------------------------------------------------------------------------


def test_filename_tag_sanitizes():
    assert _filename_tag("Sample A (5K)") == "Sample_A_5K"
    assert _filename_tag("  spaces  ") == "spaces"
    assert _filename_tag("a/b\\c") == "a_b_c"
    assert _filename_tag(None) == ""
    assert _filename_tag("***") == ""


def _make_experiment(name="SampleA"):
    probe = _make_neutron_probe(name=name)
    sample = silicon(0, 10) | air
    return Experiment(sample=sample, probe=probe, name=name)


def test_export_basename_appends_name_for_indexed(tmp_path):
    M = _make_experiment("SampleA")
    base = str(tmp_path / "myfit-1")
    assert M._export_basename(base) == base + "-SampleA"


def test_export_basename_unchanged_for_single(tmp_path):
    M = _make_experiment("SampleA")
    base = str(tmp_path / "myfit")
    assert M._export_basename(base) == base


def test_export_basename_sanitizes_name(tmp_path):
    M = _make_experiment("Sample A (5K)")
    base = str(tmp_path / "myfit-2")
    assert M._export_basename(base) == base + "-Sample_A_5K"


def test_experiment_save_includes_name_in_filenames(tmp_path):
    M = _make_experiment("SampleA")
    M.probe.description = "5K field cooled"
    M.save(str(tmp_path / "myfit-1"))
    refl = tmp_path / "myfit-1-SampleA-refl.dat"
    profile = tmp_path / "myfit-1-SampleA-profile.dat"
    assert refl.exists()
    assert profile.exists()
    assert "# comment: 5K field cooled" in refl.read_text(encoding="utf-8")
