"""Named surface extraction and CSV ordering across products and corners."""

import csv
from types import SimpleNamespace

import numpy as np
import pytest
import spiceypy as spice

from SOIM.lib.classes import Product, Timeline
from SOIM.lib.simulator import convert_Acqs2TabData, evalTimeline


def evaluate(products, scenario, fake_spice):
    bore, corners = fake_spice
    for product in products:
        product.addScenario(scenario)
    acquisitions, *_ = evalTimeline(
        SimpleNamespace(t=[0, 1]),
        "HRIC",
        corners,
        products,
        scenario,
        "HRIC",
        bore,
        np.zeros(3),
        np.zeros(3),
    )
    return acquisitions


def table(acquisitions, products):
    return convert_Acqs2TabData(
        acquisitions, [], [], [], products, "HRIC", True, [], False
    )


def test_surface_dictionary_uses_names_and_mode_order(scenario, fake_spice):
    product = Product("HRIC", "Boresight", "NIELRXPDS", "b" * 9)
    acquisitions = evaluate([product], scenario, fake_spice)
    first, second = acquisitions
    params = first.results[product]
    assert isinstance(params, dict)
    assert params["incidence"] == pytest.approx(np.degrees(0.2))
    assert params["emission"] == pytest.approx(np.degrees(0.3))
    assert params["phase"] == pytest.approx(np.degrees(0.1))
    assert params["latitude"] == params["longitude"] == 0
    assert first.ill_ise == pytest.approx(
        [
            params["incidence"],
            params["phase"],
            params["emission"],
        ]
    )
    assert len(first.boresight_latlong) == len(second.boresight_latlong) == 2
    assert first.boresight_latlong is not second.boresight_latlong
    # Neither dictionary insertion order nor repeated mode fields control CSV.
    reversed_params = dict(reversed(list(params.items())))
    assert product.surface_row(reversed_params) == product.surface_row(params)


@pytest.mark.parametrize(
    "mode,output,labels,exported_labels",
    [
        ("RL", "bb", ["R[km]", "La[°]", "Lo[°]"], ["R[km]", "La[°]", "Lo[°]"]),
        (
            "LRX",
            "bsc",
            ["La[°]", "Lo[°]", "R[km]", "X[km]", "Y[km]", "Z[km]"],
            ["La[°]", "Lo[°]", "X[km]", "Y[km]", "Z[km]"],
        ),
        (
            "RLR",
            "bbb",
            ["R[km]", "La[°]", "Lo[°]", "R[km]"],
            ["R[km]", "La[°]", "Lo[°]", "R[km]"],
        ),
    ],
)
def test_corner_csv_follows_product_vertex_mode_order(
    mode, output, labels, exported_labels, scenario, fake_spice, tmp_path
):
    corner = Product("HRIC", "Corners", mode, output)
    bore = Product("HRIC", "Boresight", "X", "b")
    # Corner product precedes boresight, just as rows in products.csv can do.
    products = [corner, bore]
    acquisitions = evaluate(products, scenario, fake_spice)
    corners = acquisitions[0].results[corner]
    assert list(corners) == [0, 1, 2, 3]
    for index, params in corners.items():
        radius, lon, lat = spice.reclat(acquisitions[0].pcorners[index])
        assert params["radius"] == pytest.approx(radius)
        assert params["latitude"] == pytest.approx(np.degrees(lat))
        assert params["longitude"] == pytest.approx(np.degrees(lon))
        # Deliberately reorder named data before exporting.
        corners[index] = dict(reversed(list(params.items())))
    rows, h1, h2, h3, csv_mask, _, start, step = table(acquisitions, products)
    assert h3[3 : 3 + 4 * len(labels)] == labels * 4
    assert h2[3 : 3 + 4 * len(labels)] == [
        corner.name + str(index) for index in range(4) for _ in labels
    ]
    assert h2[-3:] == [bore.name] * 3
    assert start == 3 and step == len(labels)
    expected = []
    for index in range(4):
        params = corners[index]
        for label in labels:
            key = {
                "R[km]": "radius",
                "La[°]": "latitude",
                "Lo[°]": "longitude",
                "X[km]": "x",
                "Y[km]": "y",
                "Z[km]": "z",
            }[label]
            expected.append(params[key])
    assert rows[0][3 : 3 + len(expected)] == pytest.approx(expected)
    path = tmp_path / "corners.csv"
    Timeline.write2file(
        None,
        path,
        h1,
        h2,
        h3,
        rows,
        tmp_path / "log.txt",
        print_csv=csv_mask,
    )
    with path.open(encoding="utf-8-sig", newline="") as stream:
        exported = list(csv.reader(stream))
    assert len({len(row) for row in exported}) == 1
    assert exported[2][3:-3] == exported_labels * 4


def test_failed_surface_results_remain_nan_at_export(scenario, fake_spice, monkeypatch):
    products = [
        Product("HRIC", name, "LR", "bb")
        for name in ("Boresight", "Corners", "Subnadiral", "Subsolar")
    ]

    def missing(*args):
        raise spice.NotFoundError()

    for name in ("sincpt", "subpnt", "subsol"):
        monkeypatch.setattr(spice, name, missing)
    acquisitions = evaluate(products, scenario, fake_spice)
    rows, *_ = table(acquisitions, products)
    assert np.isnan(np.asarray(rows[0][3:], dtype=float)).all()


def test_corner_extra_pair_schema(scenario, fake_spice):
    product = Product("HRIC", "Corners", "LR2", "bbb")
    acquisitions = evaluate([product], scenario, fake_spice)
    rows, h1, h2, h3, csv_mask, shp_mask, _, step = table(acquisitions, [product])
    assert (
        len(rows[0]) == len(h1) == len(h2) == len(h3) == len(csv_mask) == len(shp_mask)
    )
    assert step == 3
    assert h2[-4:] == ["CornS0", "CornS0", "CornS1", "CornS1"]
    assert h3[-4:] == ["La[°]", "Lo[°]"] * 2
    assert rows[0][-4:] == pytest.approx(
        [
            acquisitions[0].results[product][index][key]
            for index in (0, 1)
            for key in ("latitude", "longitude")
        ]
    )
