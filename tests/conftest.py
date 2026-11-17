from datetime import datetime, timedelta

import numpy as np
import pytest
import spiceypy as spice

from SOIM.lib import utility


@pytest.fixture
def scenario():
    return {
        "Orbiter": "MPO",
        "Target": "MERCURY",
        "Target Frame": "IAU_MERCURY",
        "ShapeSinc": "Ellipsoid",
        "ShapeSbnd": "INTERCEPT/ELLIPSOID",
        "Light": "LT+S",
        "Instruments": {"HRIC": -121612, "STC": -121625},
    }


@pytest.fixture
def project(tmp_path):
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "instruments.yml").write_text("HRIC: -121612\nSTC: -121625\n")
    (folder / "scenario.yml").write_text(
        "Orbiter: MPO\nTarget: MERCURY\nTarget Frame: IAU_MERCURY\n"
    )
    (folder / "timeline.txt").write_text(
        "2027-03-13T00:00:00|1|2027-03-13T00:00:04|HRIC\n\n"
    )
    (folder / "products.csv").write_text(
        "Instrument,Product,Mode,Output\n"
        "HRIC,Boresight,DLRPIENS,ccccbbbb\n"
        "HRIC,Corners,L,b\n"
        "HRIC,Subnadiral,LD,cc\n"
        "HRIC,VelBor,kpd,ccc\n"
        "HRIC,Coverage,d,c\n"
        "HRIC,MTA,d,c\n"
        "HRIC,Swath,dk,cb\n"
        "HRIC,Pog,m,b\n"
        "HRIC,Smearing,m,c\n"
        "HRIC,Subsolar,L,c\n"
    )
    return folder


@pytest.fixture
def fake_spice(monkeypatch):
    """Deterministic Mercury geometry, using real SPICE coordinate transforms."""
    start = datetime(2027, 3, 13)
    bore = np.array([1.0, 0.0, 0.0])
    corners = np.array(
        [[1, -0.01, -0.01], [1, -0.01, 0.01], [1, 0.01, 0.01], [1, 0.01, -0.01]]
    )
    monkeypatch.setattr(
        spice, "str2et", lambda s: (datetime.fromisoformat(s) - start).total_seconds()
    )
    monkeypatch.setattr(
        spice,
        "et2utc",
        lambda et, *_args: (start + timedelta(seconds=float(et))).isoformat(),
    )
    monkeypatch.setattr(utility, "et2utc", spice.et2utc)
    monkeypatch.setattr(
        spice, "getfov", lambda *_: ("RECTANGLE", "HRIC", bore, 4, corners)
    )
    monkeypatch.setattr(spice, "gdpool", lambda *_: np.array([1024.0]))
    monkeypatch.setattr(
        spice,
        "sincpt",
        lambda _method, _target, et, _frame, _light, _obs, _fov, ray: (
            np.array([2439.4, float(et) + 2439.4 * ray[1], 2439.4 * ray[2]]),
            et,
            ray,
        ),
    )
    monkeypatch.setattr(spice, "subpnt", lambda *_: (np.array([2439.4, 1, 0]), 0, bore))
    monkeypatch.setattr(spice, "subsol", lambda *_: np.array([2439.4, 2, 0]))
    monkeypatch.setattr(spice, "ilumin", lambda *_: (0, bore, 0.1, 0.2, 0.3))
    monkeypatch.setattr(
        spice,
        "spkpos",
        lambda body, *_: (
            np.array([3000.0, 6000.0, 3.0])
            if body == "SUN"
            else np.array([3000.0, 0.0, 0.0]),
            0,
        ),
    )
    monkeypatch.setattr(spice, "spkezr", lambda *_: (np.zeros(6), 0))
    monkeypatch.setattr(spice, "oscltx", lambda *_: [0] * 8 + [0.5])
    monkeypatch.setattr(spice, "bodvrd", lambda *_: (1, [132712440041.9394]))
    return bore, corners
