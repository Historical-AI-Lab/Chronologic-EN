"""Hash-stamp fallback for mtime-based instrument skip checks (stages 3/6/7)."""

import os
from types import SimpleNamespace

import run_pipeline as rp


def _pair(tmp_path, out_newer):
    inp, out = tmp_path / "loo.json", tmp_path / "results.json"
    inp.write_text("input")
    out.write_text("output")
    t = 1_700_000_000
    os.utime(inp, (t, t))
    os.utime(out, (t + 10, t + 10) if out_newer else (t - 10, t - 10))
    return out, inp


def test_mtime_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "FRESHNESS_PATH", tmp_path / "stamps.json")
    assert rp._fresh(*_pair(tmp_path, out_newer=True))
    assert not rp._fresh(*_pair(tmp_path, out_newer=False))
    assert not rp._fresh(tmp_path / "missing", tmp_path / "loo.json")


def test_stamp_survives_reset_mtimes_and_voids_on_edit(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "FRESHNESS_PATH", tmp_path / "stamps.json")
    out, inp = _pair(tmp_path, out_newer=True)
    stage = SimpleNamespace(number=6, name="validate", fresh_pair=(out, inp))
    assert rp.stamp_instrument([stage]) == ["validate"]

    t = 1_700_000_000                       # a clone: output now older than input
    os.utime(out, (t - 10, t - 10))
    assert rp._fresh(out, inp)

    inp.write_text("input, edited")         # any content change voids the stamp
    os.utime(inp, (t, t))
    assert not rp._fresh(out, inp)


def test_stamp_refuses_stale_pair(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "FRESHNESS_PATH", tmp_path / "stamps.json")
    out, inp = _pair(tmp_path, out_newer=False)
    stage = SimpleNamespace(number=7, name="calibrate", fresh_pair=(out, inp))
    assert rp.stamp_instrument([stage]) == []
    assert not rp._fresh(out, inp)
