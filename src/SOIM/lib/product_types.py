"""Accepted SOIM product names and their internal representations."""

# Internal output label, Product flag, and aliases with the preferred name first.
PRODUCT_TYPES = (
    ("Bor", "boresight", ("Boresight", "boresight", "BORESIGHT")),
    ("SbNd", "subnadiral", ("Subnadiral", "subnadiral", "SUBNADIRAL")),
    ("Corn", "corners", ("Corners", "corners", "CORNERS")),
    ("PoG", "pog", ("Pog", "pog", "POG", "PoG")),
    ("Vel@B", "vel", ("VelBor", "velbor", "VELBOR")),
    ("Sme1/4", "smearing", ("Smearing", "smearing", "Smear")),
    ("Swath", "f_swath", ("Swath", "swath", "SWATH")),
    ("Cover", "f_coverage", ("Coverage", "coverage")),
    ("Sbsol", "subsolar", ("Subsolar", "subsolar", "SubSolar")),
    ("mta", "mta", ("MTA", "mta", "MercuryTrueAnomaly")),
)

PRODUCT_BY_ALIAS = {
    alias: (internal_name, flag)
    for internal_name, flag, aliases in PRODUCT_TYPES
    for alias in aliases
}

SURFACE_MODES = {
    "L": "Latitude and longitude (°)",
    "R": "Radius (km)",
    "D": "Distance from the observer (km)",
    "S": "Distance from the Sun (km)",
    "X": "Cartesian coordinates (km)",
    "I": "Incidence angle (°)",
    "E": "Emission angle (°)",
    "P": "Phase angle (°)",
    "N": "Solar azimuth from north (°)",
}

MODES_BY_FLAG = {
    "boresight": SURFACE_MODES,
    "subnadiral": SURFACE_MODES,
    "corners": SURFACE_MODES,
    "subsolar": SURFACE_MODES,
    "pog": {"k": "Ground pixel size (km)", "m": "Ground pixel size (m)"},
    "vel": {
        "k": "Ground speed (km/s)",
        "m": "Ground speed (m/s)",
        "d": "Angular speed (°/s)",
        "p": "Ground pixel crossing time (ms/pixel)",
    },
    "smearing": {"m": "Quarter-pixel time (ms)", "s": "Quarter-pixel time (s)"},
    "f_swath": {
        "k": "Swath width and height (km)",
        "m": "Swath width and height (m)",
        "d": "Angular width and height (°)",
    },
    "f_coverage": {"d": "Latitude and longitude span (°)"},
    "mta": {"d": "Mercury true anomaly (°)"},
}

PRODUCT_MODES = {
    "Time": {
        "s": "UTC (automatic)",
        "e": "Ephemeris seconds (automatic)",
        "o": "Orbit number (automatic)",
    },
    **{alias: MODES_BY_FLAG[flag] for alias, (_, flag) in PRODUCT_BY_ALIAS.items()},
}
