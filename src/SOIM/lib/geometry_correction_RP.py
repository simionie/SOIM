from math import isfinite

import numpy as np
from shapely.geometry import MultiPolygon, Polygon


def footprint_polygon(longitudes, latitudes):
    """Build one export geometry, with multipart output at the antimeridian."""
    polygon = Polygon(zip(longitudes, latitudes, strict=True))
    if polygon.is_empty:
        return polygon
    crosses_meridian = max(longitudes) - min(longitudes) > 180
    near_pole = max(map(abs, latitudes)) > 80
    if not crosses_meridian and (not near_pole or polygon.is_valid):
        return polygon
    if not all(map(isfinite, (*longitudes, *latitudes))):
        return polygon

    try:
        rings, changed = correct_meridian(longitudes, latitudes)
    except ValueError:
        rings, changed = (), False
    if changed:
        parts = [Polygon(zip(ring["l"], ring["L"], strict=True)) for ring in rings]
        corrected = parts[0] if len(parts) == 1 else MultiPolygon(parts)
        if corrected.is_valid and not corrected.is_empty:
            return corrected

    if near_pole and not crosses_meridian and not polygon.is_valid:
        # Close to a pole, straight segments in lon/lat can cross even when the
        # corresponding spherical edges do not. Sample the short spherical arcs.
        lon, lat = np.radians([longitudes, latitudes])
        xyz = np.column_stack(
            (np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat))
        )
        following = np.roll(xyz, -1, axis=0)
        corners = np.column_stack((longitudes, latitudes))
        for subdivisions in (8, 16, 32, 64):
            weight = np.arange(subdivisions)[:, None] / subdivisions
            points = xyz[:, None, :] * (1 - weight) + following[:, None, :] * weight
            x, y, z = points.reshape(-1, 3).T
            vertices = np.degrees(
                np.column_stack((np.arctan2(y, x), np.arctan2(z, np.hypot(x, y))))
            )
            vertices[::subdivisions] = corners
            corrected = Polygon(vertices)
            if corrected.is_valid and not corrected.is_empty:
                return corrected

    return polygon


def correct_meridian(l, L, VISUALIZE=False):

    thLAT = 80.0

    ris, changed = duplicate_in_case_of_meridian(
        l, L, VISUALIZE
    )

    if changed:

        ris[0], changed1 = extends_in_case_of_poles(
            ris[0]['l'], ris[0]['L'],
            VISUALIZE, thLAT,
            ris[0]['l0'], ris[0]['L0'],
            ris[0]['l1'], ris[0]['L1']
        )

        ris[1], changed2 = extends_in_case_of_poles(
            ris[1]['l'], ris[1]['L'],
            VISUALIZE, thLAT,
            ris[1]['l0'], ris[1]['L0'],
            ris[1]['l1'], ris[1]['L1']
        )

    else:

        ris[0], changed = extends_in_case_of_poles(
            ris[0]['l'], ris[0]['L'],
            VISUALIZE, thLAT,
            ris[0]['l0'], ris[0]['L0'],
            ris[0]['l1'], ris[0]['L1']
        )

    return ris, changed


def area_tri(x, y):
    """
    Calculate the area of a triangle defined by 3 points.
    """

    M = np.column_stack((
        np.asarray(x),
        np.asarray(y),
        np.ones(3)
    ))

    return abs(np.linalg.det(M)) / 2.0


def area_triangle_and_point(x, y, x0, y0):
    """
    Calculate the sum of the areas of three triangles
    obtained by connecting the point (x0,y0) to each
    side of the original triangle.
    """

    A = 0.0

    tbc = np.array([
        [0, 1],
        [1, 2],
        [2, 0]
    ])

    for p in tbc:

        A1 = area_tri(
            [x[p[0]], x[p[1]], x0],
            [y[p[0]], y[p[1]], y0]
        )

        A += A1

    return A


def consider_poles(L, l, thLAT):

    L = np.asarray(L, dtype=float)
    l = np.asarray(l, dtype=float)

    isexternal = False
    x = np.array([])
    y = np.array([])

    SIGN = np.sign(np.mean(np.degrees(L)))

    if np.any((L < -thLAT) | (L > thLAT)):

        x = np.cos(L) * np.sin(l)
        y = np.cos(L) * np.cos(l)

        At1 = area_tri(x[[0, 1, 2]], y[[0, 1, 2]])

        At1p = area_triangle_and_point(
            x[[0, 1, 2]],
            y[[0, 1, 2]],
            0, 0
        )

        At2 = area_tri(x[[2, 3, 0]], y[[2, 3, 0]])

        At2p = area_triangle_and_point(
            x[[2, 3, 0]],
            y[[2, 3, 0]],
            0, 0
        )

        isexternal = (
            (At1p - At1 > 1e-10) and
            (At2p - At2 > 1e-10)
        )

    else:

        isexternal = True

    return isexternal, x, y, SIGN


def consider_poles4(L, l, thLAT):

    return consider_poles(L, l, thLAT)


def consider_poles5(L, l, thLAT):

    L = np.asarray(L, dtype=float)
    l = np.asarray(l, dtype=float)

    isexternal1, x1, y1, SIGN1 = consider_poles4(
        L[:4], l[:4], thLAT
    )

    isexternal2, x2, y2, SIGN2 = consider_poles4(
        L[[0, 1, 3, 4]],
        l[[0, 1, 3, 4]],
        thLAT
    )

    isexternal = isexternal1 and isexternal2

    x = np.cos(L) * np.sin(l)
    y = np.cos(L) * np.cos(l)

    SIGN = np.sign(np.mean(np.degrees(L)))

    return isexternal, x, y, SIGN

def extends_in_case_of_poles(
    l, L, VISUALIZE=False, thLAT=80,
    l0=None, L0=None, l1=None, L1=None
):

    l = np.asarray(l, dtype=float)
    L = np.asarray(L, dtype=float)

    ris = {
        'l': l.copy(),
        'L': L.copy(),
        'l0': l[0] if l0 is None else l0,
        'L0': L[0] if L0 is None else L0,
        'l1': l[1] if l1 is None else l1,
        'L1': L[1] if L1 is None else L1
    }

    changed = False

    Lr = np.radians(L)
    lr = np.radians(l)

    npoints = len(Lr)

    if npoints == 4:

        isexternal, x, y, SIGN = consider_poles4(
            Lr, lr, np.radians(thLAT)
        )

        tbc = np.array([
            [0, 1],
            [1, 2],
            [2, 3],
            [3, 0]
        ])

    else:

        isexternal, x, y, SIGN = consider_poles5(
            Lr, lr, np.radians(thLAT)
        )

        tbc = np.array([
            [0, 1],
            [1, 2],
            [2, 3],
            [3, 4],
            [4, 0]
        ])

    if isexternal:
        return ris, changed

    changed = True

    # Find intersection with meridian x=0, y<0

    int_p = None
    int_l = None
    int_y = None
    int_k = None

    for k in range(npoints):

        p = tbc[k]

        den = x[p[1]] - x[p[0]]

        if den == 0:
            continue

        lam = -x[p[0]] / den

        yn = (
            y[p[0]]
            - x[p[0]] * (y[p[1]] - y[p[0]]) / den
        )

        if 0 < lam < 1 and yn < 0:

            int_p = p
            int_l = lam
            int_y = yn
            int_k = k

    if int_p is None:
        return ris, False

    # Intersection coordinates

    int_x = (
        x[int_p[0]]
        + int_l * (x[int_p[1]] - x[int_p[0]])
    )

    # Generate points around the pole

    deltar = 0.0001
    N_ang = 10

    ang = (
        2 * np.pi * np.arange(N_ang + 1) / N_ang
        - np.pi
    )

    xc = deltar * np.sin(ang)
    yc = deltar * np.cos(ang)

    # Construct extended polygon

    x1 = np.concatenate((
        [int_x],
        x[tbc[int_k:, 1]],
        x[tbc[:int_k, 1]],
        [int_x],
        xc
    ))

    y1 = np.concatenate((
        [int_y],
        y[tbc[int_k:, 1]],
        y[tbc[:int_k, 1]],
        [int_y],
        yc
    ))

    l2 = np.degrees(np.arctan2(x1, y1))

    l2[0] = abs(l2[0]) * np.sign(l2[1])
    l2[5] = abs(l2[5]) * np.sign(l2[4])
    # Join the pole along the same side of the seam as the preceding edge.
    l2[6:] = np.linspace(l2[5], l2[0], N_ang + 1)

    with np.errstate(invalid='ignore'):
        L2 = SIGN * np.degrees(
            np.arccos(y1 / np.cos(np.radians(l2)))
        )

    L2[6:] = SIGN * 90

    l2, L2 = ensure_clockwise(l2, L2)

    ris['l'] = l2
    ris['L'] = L2

    return ris, changed

def duplicate_in_case_of_meridian(l, L, VISUALIZE=False):

    l = np.asarray(l, dtype=float)
    L = np.asarray(L, dtype=float)

    s = 1  # MATLAB s=2

    ris = [{
        'l': l.copy(),
        'L': L.copy(),
        'l0': l[0],
        'L0': L[0],
        'l1': l[s],
        'L1': L[s]
    }]

    changed = False

    isexternal, x, y, SIGN = consider_poles(
        np.radians(L),
        np.radians(l),
        np.radians(80)
    )

    if isexternal:

        x = np.cos(np.radians(L)) * np.sin(np.radians(l))
        y = np.cos(np.radians(L)) * np.cos(np.radians(l))
        z = np.sin(np.radians(L))

        X = np.array([x, y, z])

        inters = False
        cutted = []
        Xsol = []

        for k in range(4):

            j = (k + 1) % 4

            den = X[0, j] - X[0, k]

            if den == 0:
                continue

            lam = -X[0, k] / den

            y0 = X[1, k] + lam * (X[1, j] - X[1, k])

            if 0 < lam < 1 and y0 < 0:

                inters = True

                cutted.append([k, j])

                Xsol.append(
                    X[:, k] + lam * (X[:, j] - X[:, k])
                )

        if inters:

            Xsol = np.array(Xsol).T

            if len(cutted) != 2:
                raise ValueError(
                    "Expected exactly two meridian intersections"
                )

            cutted = np.asarray(cutted)

            # CASE A: intersections on consecutive edges

            if (
                cutted[0, 1] == cutted[1, 0]
                or cutted[0, 0] == cutted[1, 1]
            ):

                if cutted[0, 1] == cutted[1, 0]:

                    Xnew1 = np.column_stack((
                        Xsol[:, 1],
                        Xsol[:, 0],
                        X[:, cutted[0, 1]],
                        Xsol[:, 1]
                    ))

                    next_ = (cutted[1, 1] + 1) % 4

                    Xnew2 = np.column_stack((
                        Xsol[:, 1],
                        X[:, cutted[1, 1]],
                        X[:, next_],
                        X[:, cutted[0, 0]],
                        Xsol[:, 0]
                    ))

                else:

                    Xnew1 = np.column_stack((
                        Xsol[:, 1],
                        Xsol[:, 0],
                        X[:, cutted[0, 0]],
                        Xsol[:, 1]
                    ))

                    prev = max(cutted[1, 0] - 1, 0)

                    Xnew2 = np.column_stack((
                        Xsol[:, 1],
                        X[:, cutted[1, 0]],
                        X[:, prev],
                        X[:, cutted[0, 1]],
                        Xsol[:, 0]
                    ))

                l1New = np.degrees(
                    np.arctan2(Xnew1[0], Xnew1[1])
                )

                l2New = np.degrees(
                    np.arctan2(Xnew2[0], Xnew2[1])
                )

                if l1New[2] < 0:

                    l1New[[1, 3, 0]] = -180
                    l2New[[0, -1]] = 180

                else:

                    l1New[[1, 3, 0]] = 180
                    l2New[[0, -1]] = -180

                with np.errstate(invalid='ignore'):
                    L1New = np.sign(Xnew1[2]) * np.degrees(
                        np.arccos(
                            Xnew1[1] / np.cos(np.radians(l1New))
                        )
                    )

                    L2New = np.sign(Xnew2[2]) * np.degrees(
                        np.arccos(
                            Xnew2[1] / np.cos(np.radians(l2New))
                        )
                    )

            # CASE B: intersections on non-consecutive edges

            else:

                Xnew1 = np.column_stack((
                    Xsol[:, 0],
                    X[:, cutted[0, 0]],
                    X[:, cutted[1, 1]],
                    Xsol[:, 1],
                    Xsol[:, 0]
                ))

                Xnew2 = np.column_stack((
                    Xsol[:, 1],
                    X[:, cutted[1, 0]],
                    X[:, cutted[0, 1]],
                    Xsol[:, 0],
                    Xsol[:, 1]
                ))

                l1New = np.degrees(
                    np.arctan2(Xnew1[0], Xnew1[1])
                )

                l2New = np.degrees(
                    np.arctan2(Xnew2[0], Xnew2[1])
                )

                if l1New[1] < 0:

                    l1New[[0, 3, 4]] = -180
                    l2New[[0, 3, 4]] = 180

                else:

                    l1New[[0, 3, 4]] = 180
                    l2New[[0, 3, 4]] = -180

                L1New = np.degrees(np.arcsin(Xnew1[2]))
                L2New = np.degrees(np.arcsin(Xnew2[2]))

            l1New, L1New = ensure_clockwise(l1New, L1New)
            l2New, L2New = ensure_clockwise(l2New, L2New)

            ris = [
                {
                    'l': l1New,
                    'L': L1New,
                    'l0': l[0],
                    'L0': L[0],
                    'l1': l[s],
                    'L1': L[s]
                },
                {
                    'l': l2New,
                    'L': L2New,
                    'l0': l[0],
                    'L0': L[0],
                    'l1': l[s],
                    'L1': L[s]
                }
            ]

            changed = True

    return ris, changed

def ispolycw(lon, lat):
    """
    True se il poligono è percorso in senso orario.
    """

    lon = np.asarray(lon)
    lat = np.asarray(lat)

    area = np.sum(
        lon[:-1] * lat[1:] -
        lon[1:] * lat[:-1]
    )

    return area < 0


def ensure_clockwise(lon, lat):

    if not ispolycw(lon, lat):
        lon = lon[::-1]
        lat = lat[::-1]

    return lon, lat



def correct_antimeridiam_table(risTIME,title_col2):

    risTIMEnew=[]
    Lat_coord=[]
    Long_coord=[]
    # CORRECT ANTIMERIDIAN
    # Indici delle colonne Corn0, Corn1, Corn2, Corn3
    for Q, row in enumerate(risTIME):

        Lat = np.array([row[[j for j, c in enumerate(title_col2) if c == f"Corn{i}"][0]]
                  for i in range(4)])

        Long = np.array([row[[j for j, c in enumerate(title_col2) if c == f"Corn{i}"][1]]
                  for i in range(4)])

        
        ris, changed=correct_meridian(Long,Lat)
        if not changed:
            Long_coord.append(ris[0]['l'])
            Lat_coord.append(ris[0]['L'])  #latitudines
            risTIMEnew.append(row)
        else:
            Long_coord.append(ris[0]['l'])
            Lat_coord.append(ris[0]['L'])
            risTIMEnew.append(row)

            Long_coord.append(ris[0]['l'])
            Lat_coord.append(ris[0]['L'])
            risTIMEnew.append(row)



        
    return risTIMEnew,Lat_coord,Long_coord