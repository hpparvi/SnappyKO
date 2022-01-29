#  ExOrbit: fast orbit calculations for exoplanet modelling
#  Copyright (C) 2022 Hannu Parviainen
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

from numba import njit
from numpy import cos, sin, floor, sqrt, zeros, linspace

from .orbit import ta_newton_s


@njit(fastmath=True)
def solve_xyp_5s(phase, p, a, i, e, w):
    """Planet velocity, acceleration, jerk, and snap at mid-transit in [R_star / day]"""

    # Time step for central finite difference
    # ---------------------------------------
    # I've tried to choose a value that is small enough to
    # work with ultra-short-period orbits and large enough
    # not to cause floating point problems with the fourth
    # derivative (anything much smaller starts hitting the
    # double precision limit.)
    dt = 2e-2

    ae = a*(1. - e**2)
    ci = cos(i)

    # Calculation of X and Y positions
    # --------------------------------
    # These could just as well be calculated with a single
    # loop with X and Y as arrays, but I've decided to
    # manually unroll it because it seems to give a small
    # speed advantage with numba.

    f0 = ta_newton_s(phase-3 * dt, 0.0, p, e, w)
    f1 = ta_newton_s(phase-2 * dt, 0.0, p, e, w)
    f2 = ta_newton_s(phase-dt, 0.0, p, e, w)
    f3 = ta_newton_s(phase, 0.0, p, e, w)
    f4 = ta_newton_s(phase+dt, 0.0, p, e, w)
    f5 = ta_newton_s(phase+2 * dt, 0.0, p, e, w)
    f6 = ta_newton_s(phase+3 * dt, 0.0, p, e, w)

    r0 = ae/(1. + e*cos(f0))
    r1 = ae/(1. + e*cos(f1))
    r2 = ae/(1. + e*cos(f2))
    r3 = ae/(1. + e*cos(f3))
    r4 = ae/(1. + e*cos(f4))
    r5 = ae/(1. + e*cos(f5))
    r6 = ae/(1. + e*cos(f6))

    x0 = -r0*cos(w + f0)
    x1 = -r1*cos(w + f1)
    x2 = -r2*cos(w + f2)
    x3 = -r3*cos(w + f3)
    x4 = -r4*cos(w + f4)
    x5 = -r5*cos(w + f5)
    x6 = -r6*cos(w + f6)

    y0 = -r0*sin(w + f0)*ci
    y1 = -r1*sin(w + f1)*ci
    y2 = -r2*sin(w + f2)*ci
    y3 = -r3*sin(w + f3)*ci
    y4 = -r4*sin(w + f4)*ci
    y5 = -r5*sin(w + f5)*ci
    y6 = -r6*sin(w + f6)*ci

    # First time derivative of position: velocity
    # -------------------------------------------
    a, b, c = 1/60, 9/60, 45/60
    vx = (a*(x6 - x0) + b*(x1 - x5) + c*(x4 - x2))/dt
    vy = (a*(y6 - y0) + b*(y1 - y5) + c*(y4 - y2))/dt

    # Second time derivative of position: acceleration
    # ------------------------------------------------
    a, b, c, d = 1/90, 3/20, 3/2, 49/18
    ax = (a*(x0 + x6) - b*(x1 + x5) + c*(x2 + x4) - d*x3)/dt**2
    ay = (a*(y0 + y6) - b*(y1 + y5) + c*(y2 + y4) - d*y3)/dt**2

    # Third time derivative of position: jerk
    # ---------------------------------------
    a, b, c = 1/8, 1, 13/8
    jx = (a*(x0 - x6) + b*(x5 - x1) + c*(x2 - x4))/dt**3
    jy = (a*(y0 - y6) + b*(y5 - y1) + c*(y2 - y4))/dt**3

    # Fourth time derivative of position: snap
    # ----------------------------------------
    a, b, c, d = 1/6, 2, 13/2, 28/3
    sx = (-a*(x0 + x6) + b*(x1 + x5) - c*(x2 + x4) + d*x3)/dt**4
    sy = (-a*(y0 + y6) + b*(y1 + y5) - c*(y2 + y4) + d*y3)/dt**4

    return x3, y3, vx, vy, ax, ay, jx, jy, sx, sy


@njit
def solve_xyo_5s(p, a, i, e, w, npt):
    points = linspace(0.0, p, npt)
    dt = points[1] - points[0]
    coeffs = zeros((npt, 10))
    for ix in range(npt-1):
        coeffs[ix] = solve_xyp_5s(points[ix], p, a, i, e, w)
    coeffs[-1] = coeffs[0]
    return dt, points, coeffs


@njit
def xyo_5s(t, t0, p, dt, points, coeffs):
    """Calculate planet's (x,y) position for a scalar time for any orbital phase"""
    epoch = floor((t - t0) / p)
    tc = t - t0 - epoch * p
    ix = int(floor(tc / dt + 0.5))
    x0, y0, vx, vy, ax, ay, jx, jy, sx, sy = coeffs[ix]
    tc -= points[ix]
    tc2 = tc * tc
    tc3 = tc2 * tc
    tc4 = tc3 * tc
    px = x0 + vx * tc + 0.5 * ax * tc2 + jx * tc3 / 6.0 + sx * tc4 / 24.
    py = y0 + vy * tc + 0.5 * ay * tc2 + jy * tc3 / 6.0 + sy * tc4 / 24.
    return px, py


@njit
def xyo_5v(times, t0, p, dt, points, coeffs):
    """Calculate planet's (x,y) position for a vector time for any orbital phase"""
    npt = times.size
    xs, ys = zeros(npt), zeros(npt)

    for i in range(npt):
        x, y = xyo_5s(times[i], t0, p, dt, points, coeffs)
        xs[i] = x
        ys[i] = y
    return xs, ys


@njit(fastmath=True)
def xyt_15s(tc, t0, p, x0, y0, vx, vy, ax, ay, jx, jy, sx, sy):
    """Calculate planet's (x,y) position near transit."""
    epoch = floor((tc - t0 + 0.5 * p) / p)
    t = tc - (t0 + epoch * p)
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    px = x0 + vx * t + 0.5 * ax * t2 + jx * t3 / 6.0 + sx * t4 / 24.
    py = y0 + vy * t + 0.5 * ay * t2 + jy * t3 / 6.0 + sy * t4 / 24.
    return px, py


@njit(fastmath=True)
def pdt_15s(tc, t0, p, x0, y0, vx, vy, ax, ay, jx, jy, sx, sy):
    """Calculate the (p)rojected planet-star center (d)istance near (t)ransit."""
    epoch = floor((tc - t0 + 0.5 * p) / p)
    t = tc - (t0 + epoch * p)
    t2 = t * t
    t3 = t2 * t
    t4 = t3 * t
    px = x0 + vx * t + 0.5 * ax * t2 + jx * t3 / 6.0 + sx * t4 / 24.
    py = y0 + vy * t + 0.5 * ay * t2 + jy * t3 / 6.0 + sy * t4 / 24.
    return sqrt(px ** 2 + py ** 2)


@njit(fastmath=True)
def prdist_15v(times, t0, p, x0, y0, vx, vy, ax, ay, jx, jy, sx, sy):
    z = zeros(times.size)
    for i in range(times.size):
        z[i] = pdt_15s(times[i], t0, p, x0, y0, vx, vy, ax, ay, jx, jy, sx, sy)
    return z


@njit(fastmath=True)
def pdt_25s(t, t0, p, dt, v1, v2):
    """Calculate the (p)rojected planet-star center (d)istance near (t)ransit."""
    epoch = floor((t - t0 + 0.5 * p) / p)
    tc = t - (t0 + epoch * p)
    if t < 0.0:
        x0, y0, vx, vy, ax, ay, jx, jy, sx, sy = v1
        tc += dt
    else:
        x0, y0, vx, vy, ax, ay, jx, jy, sx, sy = v2
        tc -= dt
    tc2 = tc * tc
    tc3 = tc2 * tc
    tc4 = tc3 * tc
    px = x0 + vx * tc + 0.5 * ax * tc2 + jx * tc3 / 6.0 + sx * tc4 / 24.
    py = y0 + vy * tc + 0.5 * ay * tc2 + jy * tc3 / 6.0 + sy * tc4 / 24.
    return sqrt(px ** 2 + py ** 2)


@njit(fastmath=True)
def pdt_25v(times, t0, p, dt, v1, v2):
    z = zeros(times.size)
    for i in range(times.size):
        z[i] = pdt_25s(times[i], t0, p, dt, v1, v2)
    return z