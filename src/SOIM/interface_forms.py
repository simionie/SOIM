"""Field definitions and file formats for the Project Overview forms."""

import csv
import io
import math
import re

import yaml
from spiceypy import tparse

SCENARIO_DEFAULTS = {
    "ShapeSinc": "Ellipsoid",
    "ShapeSbnd": "INTERCEPT/ELLIPSOID",
    "Light": "LT+S",
}


class IntervalEndError(ValueError):
    def __init__(self, row, message):
        super().__init__(message)
        self.row = row


def utc_order(value):
    # TPARSE assumes every day has 86400 seconds. Place a leap second
    # after second 59 of its minute and before the next minute.
    adjusted, leap_second = re.subn(r"(\d{2}:\d{2}):60(?!\d)", r"\1:59", value)
    seconds, error = tparse(adjusted)
    if error:
        return None
    whole_second = math.floor(seconds)
    return whole_second, bool(leap_second), seconds - whole_second


# The field keys are also the SOIM YAML keys for Scenario.
FIELDS = {
    "Timeline": [
        (
            "start",
            "Start (UTC)",
            "First sample time in SPICE format, e.g. 13-Mar-2027 00:27:20.",
            True,
        ),
        (
            "stop",
            "End (UTC)",
            "End of the sampling interval. The end time itself is excluded.",
            True,
        ),
        (
            "step",
            "Step (seconds)",
            "Time between samples. Enter a positive number; fractions are allowed.",
            True,
        ),
        (
            "instruments",
            "Instruments",
            "Select one or more instruments for this interval. The options come from the Instruments tab.",
            True,
        ),
    ],
    "Products": [
        (
            "instrument",
            "Instrument",
            "Select a project instrument or All instruments to apply the product to each instrument used in the timeline.",
            True,
        ),
        (
            "product",
            "Product",
            "Quantity to calculate, e.g. Corners for footprint vertices or Boresight for the pointing direction.",
            True,
        ),
        (
            "mode",
            "Mode",
            "Choose quantities or units. Existing selections keep their CSV order. For Corners, latitude and longitude must come first.",
            True,
        ),
        (
            "output",
            "Output destinations",
            "One code per Mode character: c for CSV, s for shapefile or b for both. An empty field or legacy digits export to both.",
            False,
        ),
    ],
    "Instruments": [
        (
            "name",
            "Instrument name",
            "Reference name used in Timeline and Products, e.g. MPO_SIMBIO-SYS_HRIC_FPAN.",
            True,
        ),
        (
            "id",
            "SPICE instrument ID",
            "Integer NAIF ID used to look up this instrument's field of view, e.g. -121612.",
            True,
        ),
    ],
    "Scenario": [
        (
            "Orbiter",
            "Orbiter",
            "SPICE name of the observing spacecraft, e.g. BEPICOLOMBO MPO.",
            True,
        ),
        ("Target", "Target", "SPICE name of the observed body, e.g. Mercury.", True),
        (
            "Target Frame",
            "Target frame",
            "Body-fixed SPICE coordinate frame for surface geometry, e.g. IAU_Mercury.",
            True,
        ),
        (
            "ShapeSinc",
            "Surface intercept model",
            "SPICE surface model for ray intersections. SOIM defaults to Ellipsoid.",
            False,
        ),
        (
            "ShapeSbnd",
            "Sub-observer point method",
            "SPICE method for finding the point beneath the spacecraft. Defaults to INTERCEPT/ELLIPSOID.",
            False,
        ),
        (
            "Light",
            "Aberration correction",
            "SPICE correction for apparent geometry. LT+S, the default, applies light-time and stellar aberration corrections.",
            False,
        ),
    ],
}


def yaml_mapping(content):
    data = yaml.safe_load(content)
    if not isinstance(data, dict):
        raise TypeError("Expected a YAML mapping.")
    return data


def form_rows(section, content):
    """Read one starter configuration file into display and editor fields."""
    if section == "Scenario":
        data = yaml_mapping(content)
        return [
            {
                key: str(data.get(key, SCENARIO_DEFAULTS.get(key, "")))
                for key, *_ in FIELDS[section]
            }
        ]
    if section == "Instruments":
        return [
            {"name": str(name), "id": str(code)}
            for name, code in yaml_mapping(content).items()
        ]

    if section == "Timeline":
        rows = [line.split("|") for line in content.splitlines() if line.strip()]
        keys = ("start", "step", "stop", "instruments")
    else:
        reader = csv.reader(io.StringIO(content))
        next(reader, None)
        rows = [row + [""] if len(row) == 3 else row for row in reader if row]
        keys = ("instrument", "product", "mode", "output")
    if any(len(row) != len(keys) for row in rows):
        raise ValueError("Unexpected number of fields in a configuration row.")
    return [
        dict(zip(keys, (value.strip() for value in row), strict=True)) for row in rows
    ]


def form_content(section, rows, original):
    """Validate edited fields and serialize them in the format SOIM reads."""
    if not isinstance(rows, list) or (section == "Scenario" and len(rows) != 1):
        raise ValueError("Invalid configuration rows.")
    cleaned = []
    for number, row in enumerate(rows, 1):
        values = {}
        for key, label, _, required in FIELDS[section]:
            value = row.get(key) if isinstance(row, dict) else None
            if (
                not isinstance(value, str)
                or len(value.splitlines()) > 1
                or "\x00" in value
            ):
                raise ValueError(f"Row {number}: {label} must be single-line text.")
            value = value.strip()
            if required and not value:
                raise ValueError(f"Row {number}: {label} is required.")
            values[key] = value
        cleaned.append(values)

    if section == "Timeline":
        for number, row in enumerate(cleaned, 1):
            start, end = utc_order(row["start"]), utc_order(row["stop"])
            if start is None:
                raise ValueError(
                    f"Row {number}: Start is not a recognizable UTC date and time."
                )
            if end is None:
                raise IntervalEndError(number, "Enter a valid UTC date and time.")
            if end <= start:
                raise IntervalEndError(number, "End must be later than Start.")

    if cleaned == form_rows(section, original):
        return original

    if section == "Scenario":
        data = yaml_mapping(original)
        for key, value in cleaned[0].items():
            if not value or (key not in data and SCENARIO_DEFAULTS.get(key) == value):
                data.pop(key, None)
            else:
                data[key] = value
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

    if section == "Instruments":
        data = {}
        for number, row in enumerate(cleaned, 1):
            name, code = row["name"], row["id"]
            if name in data or any(char.isspace() for char in name) or "|" in name:
                raise ValueError(
                    f"Row {number}: use a unique instrument name without spaces or pipes."
                )
            if (
                not re.fullmatch(r"[+-]?[0-9]{1,10}", code)
                or not -(2**31) <= int(code) < 2**31
            ):
                raise ValueError(
                    f"Row {number}: enter a valid integer SPICE instrument ID."
                )
            data[name] = int(code)
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)

    if section == "Timeline":
        lines = []
        for number, row in enumerate(cleaned, 1):
            try:
                step = float(row["step"])
            except ValueError:
                step = 0
            if not math.isfinite(step) or step <= 0:
                raise ValueError(f"Row {number}: the step must be a positive number.")
            if any("|" in value for value in row.values()):
                raise ValueError(
                    f"Row {number}: fields cannot contain the pipe separator."
                )
            lines.append(
                "|".join((row["start"], row["step"], row["stop"], row["instruments"]))
            )
        return "".join(line + "\n" for line in lines)

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["INSTRUMENT", "Product", "Mode", "Sign"])
    for number, row in enumerate(cleaned, 1):
        destination = row["output"]
        if destination and (
            len(destination) != len(row["mode"])
            or not re.fullmatch(r"[csb]+|[0-9]+", destination)
        ):
            raise ValueError(
                f"Row {number}: enter one c, s or b per Mode character, or leave it blank."
            )
        fields = [row["instrument"], row["product"], row["mode"]]
        if destination:
            fields.append(destination)
        writer.writerow(fields)
    return output.getvalue()
