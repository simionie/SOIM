from math import radians

import numpy as np
import pytest
import spiceypy as spice
from click import ClickException

from SOIM.lib import IO_functions as io
from SOIM.lib import utility
from SOIM.lib.classes import (
    Aquisition,
    Product,
    Timeline,
    get_NordAz,
    instr,
    listproducts,
)
from SOIM.lib.simulator import timelog


def test_yaml_includes_and_scenario_defaults(tmp_path):
    (tmp_path / "nested.yml").write_text("A: 3\n")
    folder = tmp_path / "scenario.yml"
    folder.write_text(
        "Instruments: !include nested.yml\nShapeSinc: DSK/UNPRIORITIZED\n"
    )
    config = io.LoadScenarioFile(folder, tmp_path / "log")
    assert config["Instruments"] == {"A": 3}
    assert config["ShapeSinc"] == "DSK/UNPRIORITIZED"
    assert config["ShapeSbnd"] == "INTERCEPT/ELLIPSOID" and config["Light"] == "LT+S"


def test_project_input_cardinality(tmp_path):
    with pytest.raises(SystemExit):
        io.checkPrjTxtItem("demo", tmp_path, "scenario", "yml", False)
    base = tmp_path / "scenario.yml"
    base.touch()
    assert io.checkPrjTxtItem("demo", tmp_path, "scenario", "yml", False) == base
    (tmp_path / "scenario-extra.yml").touch()
    with pytest.raises(SystemExit):
        io.checkPrjTxtItem("demo", tmp_path, "scenario", "yml", False)
    assert io.checkPrjFolder("demo", tmp_path, "results", True).is_dir()


def test_legacy_instrument_and_kernel_inputs(tmp_path, monkeypatch):
    instruments = tmp_path / "instruments.txt"
    instruments.write_text("HRIC | -121612\nSTC | -121625\n")
    assert io.checkInstrumentFile(instruments, tmp_path / "log") == ["HRIC", "STC"]
    assert instr("HRIC", -121612).naifID == -121612
    pathfile = tmp_path / "paths.yml"
    pathfile.write_text("MICE: unused\n")
    assert not io.checkPathFile("sample", pathfile)
    pathfile.write_text(f"SPICE: {tmp_path / 'missing.tm'}\n")
    assert not io.checkPathFile("sample", pathfile)
    mk = tmp_path / "sample.tm"
    mk.touch()
    pathfile.write_text(f"SPICE: {mk}\n")
    monkeypatch.setattr(spice, "kclear", lambda: None)
    requested = []
    monkeypatch.setattr(spice, "furnsh", requested.append)
    assert io.checkPathFile("sample", pathfile)
    assert requested == [str(mk)]

    def fail(_path):
        raise RuntimeError("invalid kernel")

    monkeypatch.setattr(spice, "furnsh", fail)
    with pytest.raises(SystemExit) as exc:
        io.checkPathFile("sample", pathfile)
    assert exc.value.code == 1


def test_output_modes_and_hidden_boresight(tmp_path, scenario):
    path = tmp_path / "products.csv"
    path.write_text("Instrument,Product,Mode,Output\nHRIC,Pog,m\nHRIC,VelBor,k,3\n")
    products = io.LoadProductsFile(path, scenario, tmp_path / "log")
    products, instruments = io.VelidateProducts(products)
    assert instruments == ["HRIC"]
    assert products[0].getPrintMode() == ([True, True], [True, True])
    automatic_boresight = next(p for p in listproducts("HRIC", products) if p.boresight)
    assert automatic_boresight.getPrintMode() == ([False] * 3, [False] * 3)
    with pytest.raises(ClickException, match="expected output modes"):
        io.VelidateProducts([Product("HRIC", "Corners", "L", "z")])
    with pytest.raises(SystemExit):
        Product("HRIC", "Corn", "LR", "b")


@pytest.mark.parametrize(
    "name,mode,point,expected",
    [
        ("Boresight", "X", [1, 2, 3], [1, 2, 3]),
        ("Pog", "km", [3, 4, 0], [5, 5000]),
        (
            "Swath",
            "dkm",
            [0.1, 0.2, 100],
            [np.degrees(0.1), np.degrees(0.2), 10, 20, 10000, 20000],
        ),
        ("VelBor", "kpd", [2, 0.02, 100], [2, 10, np.degrees(0.02)]),
        ("Smearing", "ms", [2, 0.02, 100], [2.5, 0.0025]),
    ],
)
def test_product_units_and_export_schema(name, mode, point, expected, scenario):
    product = Product("ALL", name, mode, "b" * len(mode))
    product.addScenario(scenario)
    assert product.convert(np.array(point)) == pytest.approx(expected)
    assert (
        len(product.getNames())
        == len(product.getLabels())
        == len(product.getInstr("HRIC"))
    )
    assert all(all(mask) for mask in product.getPrintMode())
    assert listproducts("STC", [product]) == [product]


def test_surface_cache_is_scoped_to_epoch_and_reuses_vector(
    scenario, fake_spice, monkeypatch
):
    bore = Product("HRIC", "Boresight", "XLDRPIENS", "b" * 9)
    nadir = Product("HRIC", "Subnadiral", "LD", "bb")
    for product in (bore, nadir):
        product.addScenario(scenario)
    spkpos = spice.spkpos
    calls = []

    def counted(body, *args):
        calls.append(body)
        return spkpos(body, *args)

    monkeypatch.setattr(spice, "spkpos", counted)
    point = np.array([2439.4, 0.0, 1.0])
    for et in (0, 1):
        acquisition = Aquisition("HRIC", et)
        values = acquisition.surface_values(bore, point)
        assert acquisition.surface_values(bore, point.copy()) is values
        assert np.isnan(acquisition.surface_values(bore, point, found=False)).all()
        acquisition.surface_values(nadir, point)
        assert len(values) == len(bore.getNamesPost("0"))
    assert calls == ["MPO", "SUN", "MPO", "SUN"]


def test_azimuth_near_pole_and_antimeridian():
    point = spice.latrec(2439.4, radians(179.99), radians(89.99))
    sun = point + np.array([1.0, 1000.0, 10.0])
    assert 0 <= get_NordAz(point, sun, 30) < 360
    assert np.isnan(get_NordAz(point, sun, 90))


def test_time_and_row_helpers(fake_spice, tmp_path):
    with pytest.raises(SystemExit):
        Timeline("bad", "2027-03-13T00:00:02", 1, ["HRIC"])
    with pytest.raises(SystemExit):
        Timeline("2027-03-13T00:00:00", "bad", 1, ["HRIC"])
    timeline = Timeline("2027-03-13T00:00:00", "2027-03-13T00:00:02", 1, ["HRIC"])
    timeline.add_incidence([1, 2])
    assert timeline.incidence == [1, 2]
    assert np.array_equal(timeline.t, [0, 1])
    assert [timelog(x) for x in (5, 120, 36000)] == ["5.00 s", "2.00 m", "10.00 h"]
    assert utility.appendHOR([[1], [2]], [[3], [4]]) == [[1, 3], [2, 4]]
    assert utility.appendHOR([], [[3]]) == [[3]]
    utility.pprint("test message")
    with pytest.raises(SystemExit) as exc:
        utility.soimExit()
    assert exc.value.code == 0
