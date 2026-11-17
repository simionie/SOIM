import csv
from concurrent.futures import Future

import geopandas as gpd
import numpy as np
import pytest
import spiceypy as spice
from click import ClickException
from click.testing import CliRunner
from spiceypy.utils.exceptions import SpiceNOFRAMECONNECT, SpiceSPKINSUFFDATA

from SOIM import SOIM_simulation as simulation
from SOIM import core, starter
from SOIM.lib import IO_functions as io
from SOIM.lib import Verify_DarkSide as dark
from SOIM.lib import simulator
from SOIM.lib.classes import Product


def setup_inputs(project, log, instruments=None):
    scenario = io.LoadScenarioFile(project / "scenario.yml", log)
    scenario["Instruments"] = io.LoadInstrumentFile(project / "instruments.yml", log)
    products, _ = io.VelidateProducts(
        io.LoadProductsFile(project / "products.csv", scenario, log)
    )
    timelines = io.LoadTimingFile(project / "timeline.txt", log)
    if instruments:
        timelines[0].instr = instruments
    return timelines, scenario, products


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def test_starter_writes_products(project, fake_spice, tmp_path, monkeypatch):
    monkeypatch.setattr(starter, "load_metakernel", lambda *_: None)
    mk = tmp_path / "sample.tm"
    mk.touch()
    command = starter.main
    monkeypatch.delenv("SOIM_METAKERNEL", raising=False)
    res = CliRunner().invoke(
        command,
        [
            "-p",
            str(project),
            "--name",
            "test",
            "--metakernel",
            str(mk),
            "--workers",
            "1",
        ],
    )
    assert res.exit_code == 0, (res.output, res.exception)
    assert "Total elapsed time" in res.output
    result = project / "test/results"
    rows = read_csv(result / "tot_timeline.csv")
    assert len(rows) == 7 and len({len(row) for row in rows}) == 1
    assert {"Sme1/4", "Cover", "mta"} <= set(rows[1])
    vector = gpd.read_file(result / "tot_timeline.shp")
    assert len(vector) == 4 and vector.geometry.is_valid.all()
    assert vector.crs.ellipsoid.semi_major_metre == 2439400
    assert "BorNaZ°" in vector.columns
    assert (
        "Simulation and save ended"
        in (project / "test/logs/test_output.log").read_text()
    )


def test_core_project_generates_csv(project, fake_spice, tmp_path):
    (project / "timeline.txt").write_text(
        "2027-03-13T00:00:00|1|2027-03-13T00:02:02|HRIC\n"
    )
    core.main("sample", project, tmp_path / "output", True)
    out = tmp_path / "output/sample/results"
    assert len(read_csv(out / "tot_timeline.csv")) == 123
    assert list(out.glob("*.shp")) == []


def test_parallel_blocks_match_serial(project, fake_spice, tmp_path, monkeypatch):
    # Extend past a block boundary without depending on spacecraft kernels.
    before = simulation.evaluate_timeline_block
    completed = []

    def evaluate(epochs, *args):
        completed.append(len(epochs))
        return before(epochs, *args)

    monkeypatch.setattr(simulation, "evaluate_timeline_block", evaluate)

    class InlineExecutor:
        def submit(self, function, *args):
            future = Future()
            future.set_result(function(*args))
            return future

    timings, scenario, products = setup_inputs(project, tmp_path / "setup.log")
    timings[0].t = np.arange(4098, dtype=float)
    for label, executor in [("serial", None), ("parallel", InlineExecutor())]:
        out = tmp_path / label
        out.mkdir()
        simulation.SOIM_simulation(
            timings,
            scenario,
            products,
            out,
            True,
            False,
            False,
            out / "log.txt",
            executor=executor,
            workers=2,
        )
    old, new = (tmp_path / key / "tot_timeline.csv" for key in ("serial", "parallel"))
    assert old.read_bytes() == new.read_bytes()
    assert completed == [4096, 2, 4096, 2]
    rows = read_csv(new)
    assert len(rows) == 4101
    assert [float(row[1]) for row in rows[3:]] == list(range(4098))


def test_two_instruments_keep_their_columns_in_per_timeline_export(
    project, fake_spice, tmp_path
):
    timelines, scenario, products = setup_inputs(
        project, tmp_path / "setup.log", ["HRIC", "STC"]
    )
    stc = Product("STC", "Boresight", "L", "c")
    stc.addScenario(scenario)
    products.append(stc)
    simulation.SOIM_simulation(
        timelines,
        scenario,
        products,
        tmp_path,
        False,
        False,
        False,
        tmp_path / "run.log",
    )
    rows = read_csv(next(tmp_path.glob("timeline_*.csv")))
    assert rows[0][-2:] == ["STC", "STC"]
    assert rows[2][-2:] == ["La[°]", "Lo[°]"]
    assert len(rows) == 7 and len({len(row) for row in rows}) == 1


def test_daylight_filter_rejects_empty_result(
    project, fake_spice, tmp_path, monkeypatch
):
    log = tmp_path / "run.log"
    timelines, scenario, products = setup_inputs(project, log)
    monkeypatch.setattr(spice, "ilumin", lambda *_: (0, np.zeros(3), 0, 2, 0))
    with pytest.raises(ClickException, match="No timeline passed the daylight filter"):
        dark.Verify_DarkSide(timelines, scenario, products, 1, log)
    assert "Simulation stopped before writing" in log.read_text()


@pytest.mark.parametrize(
    "angles,expected",
    [
        ([2, 1, 1, 2], (1, 2)),
        ([1, 1, 2, 2], (0, 2)),
    ],
)
def test_daylight_transitions(
    project, fake_spice, tmp_path, monkeypatch, angles, expected
):
    log = tmp_path / "run.log"
    timelines, scenario, products = setup_inputs(project, log)
    monkeypatch.setattr(
        spice, "ilumin", lambda *args: (0, np.zeros(3), 0, angles[int(args[2])], 0)
    )
    (filtered,) = dark.Verify_DarkSide(timelines, scenario, products, 1, log)
    assert (filtered.t0, filtered.te) == expected


def test_no_frame_connection_reports_instrument_and_epoch(
    project, fake_spice, tmp_path, monkeypatch
):
    log = tmp_path / "run.log"
    timelines, scenario, products = setup_inputs(project, log)

    def no_frame(*_args):
        raise SpiceNOFRAMECONNECT()

    monkeypatch.setattr(spice, "sincpt", no_frame)
    with pytest.raises(
        ClickException, match=r"HRIC.*2027-03-13T00:00:00.*NOFRAMECONNECT"
    ):
        dark.Verify_DarkSide(timelines, scenario, products, 1, log)
    with pytest.raises(ClickException, match="matching spacecraft clock"):
        simulation.SOIM_simulation(
            timelines, scenario, products, tmp_path, True, True, False, log
        )
    assert list(tmp_path.glob("tot_timeline.*")) == []
    assert list(tmp_path.glob(".soim-*")) == []


def test_intersection_failures_and_gravitational_fallback(
    project, fake_spice, tmp_path, monkeypatch
):
    log = tmp_path / "run.log"
    timelines, scenario, products = setup_inputs(project, log)
    bore, corners = fake_spice

    def not_found(*_args):
        raise spice.NotFoundError()

    def insufficient(*_args):
        raise SpiceSPKINSUFFDATA()

    for error, expected in [
        (not_found, [8, 0, 4, 0, 20, 0]),
        (insufficient, [0, 8, 0, 4, 0, 20]),
    ]:
        monkeypatch.setattr(spice, "sincpt", error)
        monkeypatch.setattr(spice, "subpnt", error)
        acq, *counts = simulator.evalTimeline(
            timelines[0],
            "HRIC",
            corners,
            products[:-1],
            scenario,
            "HRIC",
            bore,
            np.zeros(3),
            np.zeros(3),
        )
        assert counts == expected
        assert np.isnan(acq[0].swath_vect).all()
    monkeypatch.setattr(spice, "bodvrd", insufficient)
    assert simulator.solar_gravitational_parameter() == 132712440041.9394
    assert simulator.mercury_true_anomaly(0) == pytest.approx(np.degrees(0.5))


def test_blocks_cancel_remaining_work_on_worker_error():
    pending = []

    class FailingExecutor:
        def submit(self, _callback, *args):
            future = Future()
            pending.append(future)
            if len(pending) == 1:
                future.set_exception(RuntimeError("worker failed"))
            return future

    with pytest.raises(RuntimeError, match="worker failed"):
        list(
            simulation.ordered_timeline_blocks(
                np.arange(10000), "HRIC", None, [], {}, None, FailingExecutor(), 1
            )
        )
    assert pending[1].cancelled()


def test_empty_instrument_and_scenario_files_have_useful_defaults(tmp_path):
    log = tmp_path / "log"
    config = tmp_path / "empty.yml"
    config.write_text("{}\n")
    assert io.LoadInstrumentFile(config, log) == {}
    assert io.LoadScenarioFile(config, log)["ShapeSinc"] == "Ellipsoid"


def test_dayside_logs_failed_intersections(project, fake_spice, tmp_path, monkeypatch):
    log = tmp_path / "run.log"
    timelines, scenario, products = setup_inputs(project, log)

    def not_found(*_args):
        raise spice.NotFoundError()

    def insufficient(*_args):
        raise SpiceSPKINSUFFDATA()

    for error in (not_found, insufficient):
        monkeypatch.setattr(spice, "sincpt", error)
        filtered = dark.Verify_DarkSide(timelines, scenario, products, 1, log)
        assert len(filtered) == 1  # Current filter retains undetermined illumination.


def test_combined_timeline_export_contains_both_instruments_and_all_epochs(
    project, fake_spice, tmp_path
):
    from copy import copy

    timelines, scenario, products = setup_inputs(
        project, tmp_path / "setup.log", ["HRIC", "STC"]
    )
    stc = Product("STC", "Boresight", "X", "b")
    stc.addScenario(scenario)
    products.append(stc)
    second = copy(timelines[0])
    second.t = timelines[0].t + 10
    simulation.SOIM_simulation(
        [timelines[0], second],
        scenario,
        products,
        tmp_path,
        True,
        False,
        False,
        tmp_path / "run.log",
    )
    rows = read_csv(tmp_path / "tot_timeline.csv")
    assert len(rows) == 11
    assert rows[0][-3:] == ["STC"] * 3
    assert [float(row[1]) for row in rows[3:]] == [0, 1, 2, 3, 10, 11, 12, 13]


def test_starter_dayside_option_preserves_exit_message(
    project, fake_spice, tmp_path, monkeypatch
):
    monkeypatch.setattr(starter, "load_metakernel", lambda *_: None)
    monkeypatch.setattr(spice, "ilumin", lambda *_: (0, np.zeros(3), 0, 2, 0))
    monkeypatch.delenv("SOIM_METAKERNEL", raising=False)
    mk = tmp_path / "sample.tm"
    mk.touch()
    result = CliRunner().invoke(
        starter.main, ["-p", str(project), "--metakernel", str(mk), "--dayside"]
    )
    assert result.exit_code == 1 and "No timeline passed" in result.output
    assert not list((project / "my_project_results/results").iterdir())
