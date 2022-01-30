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
from numpy import pi, arctan2, sqrt, sin, cos, arccos, mod, copysign, sign

HALF_PI = 0.5*pi
TWO_PI = 2.0*pi


@njit
def eclipse_phase(p, i, e, w):
    """ Phase for the secondary eclipse center.

    Exact secondary eclipse center phase, good for all eccentricities.
    """
    etr = arctan2(sqrt(1. - e**2) * sin(HALF_PI - w), e + cos(HALF_PI - w))
    eec = arctan2(sqrt(1. - e**2) * sin(HALF_PI + pi - w), e + cos(HALF_PI + pi - w))
    mtr = etr - e * sin(etr)
    mec = eec - e * sin(eec)
    phase = (mec - mtr) * p / TWO_PI
    return phase if phase > 0. else p + phase


@njit
def af_transit(e, w):
    """Calculates the -- factor during the transit"""
    return (1.0-e**2)/(1.0 + e*sin(w))


@njit
def i_from_baew(b, a, e, w):
    """Orbital inclination from the impact parameter, scaled semi-major axis, eccentricity and argument of periastron

    Parameters
    ----------

      b  : impact parameter       [-]
      a  : scaled semi-major axis [R_Star]
      e  : eccentricity           [-]
      w  : argument of periastron [rad]

    Returns
    -------

      i  : inclination            [rad]
    """
    return arccos(b / (a*af_transit(e, w)))


@njit
def ta_from_ea_v(Ea, e):
    sta = sqrt(1.0-e**2) * sin(Ea)/(1.0-e*cos(Ea))
    cta = (cos(Ea)-e)/(1.0-e*cos(Ea))
    Ta  = arctan2(sta, cta)
    return Ta


@njit
def ta_from_ea_s(Ea, e):
    sta = sqrt(1.0-e**2) * sin(Ea)/(1.0-e*cos(Ea))
    cta = (cos(Ea)-e)/(1.0-e*cos(Ea))
    Ta  = arctan2(sta, cta)
    return Ta


@njit
def mean_anomaly_offset(e, w):
    mean_anomaly_offset = arctan2(sqrt(1.0-e**2) * sin(HALF_PI - w), e + cos(HALF_PI - w))
    mean_anomaly_offset -= e*sin(mean_anomaly_offset)
    return mean_anomaly_offset


@njit
def mean_anomaly(t, t0, p, e, w):
    offset = mean_anomaly_offset(e, w)
    Ma = mod(TWO_PI * (t - (t0 - offset * p / TWO_PI)) / p, TWO_PI)
    return Ma


@njit
def ea_newton_v(t, t0, p, e, w):
    Ma = mean_anomaly(t, t0, p, e, w)
    Ea = Ma.copy()
    for j in range(len(t)):
        err = 0.05
        k = 0
        while abs(err) > 1e-8 and k<1000:
            err   = Ea[j] - e*sin(Ea[j]) - Ma[j]
            Ea[j] = Ea[j] - err/(1.0-e*cos(Ea[j]))
            k += 1
    return Ea


@njit
def ea_newton_s(t, t0, p, e, w):
    Ma = mean_anomaly(t, t0, p, e, w)
    Ea = Ma
    err = 0.05
    k = 0
    while abs(err) > 1e-8 and k<1000:
        err   = Ea - e*sin(Ea) - Ma
        Ea = Ea - err/(1.0-e*cos(Ea))
        k += 1
    return Ea


@njit
def ta_newton_s(t, t0, p, e, w):
    return ta_from_ea_s(ea_newton_s(t, t0, p, e, w), e)


@njit
def ta_newton_v(t, t0, p, e, w):
    return ta_from_ea_v(ea_newton_v(t, t0, p, e, w), e)


@njit
def z_from_ta_s(Ta, a, i, e, w):
    z  = a*(1.0-e**2)/(1.0+e*cos(Ta)) * sqrt(1.0 - sin(w+Ta)**2 * sin(i)**2)
    z *= copysign(1.0, sin(w+Ta))
    return z


@njit(parallel=True)
def z_from_ta_v(Ta, a, i, e, w):
    z  = a*(1.0-e**2)/(1.0+e*cos(Ta)) * sqrt(1.0 - sin(w+Ta)**2 * sin(i)**2)
    z *= sign(1.0, sin(w+Ta))
    return z


@njit
def z_newton_s(t, pv):
    """Normalized projected distance for scalar t.

    pv = [t0, p, a, i, e, w]
    """
    t0, p, a, i, e, w = pv
    Ta = ta_newton_s(t, t0, p, e, w)
    return z_from_ta_s(Ta, a, i, e, w)


@njit
def z_newton_v(ts, pv):
    t0, p, a, i, e, w = pv
    Ta = ta_newton_v(ts, t0, p, e, w)
    return z_from_ta_v(Ta, a, i, e, w)