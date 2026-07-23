"""
anequim.frouin_irradiance
==========================

Spectral (hyperspectral-capable) downwelling irradiance just above the
sea surface, Ed(0+, lambda), following the physical framework of the
Frouin algorithm family:

    Frouin, R. and B. Chertock, 1992: A technique for global monitoring
        of net solar irradiance at the ocean surface. Part I: Model.
        J. Appl. Meteor., 31, 1056-1066.
    Frouin, R., B.A. Franz, and P.J. Werdell, 2003: The SeaWiFS PAR
        product. In: Algorithm Updates for the Fourth SeaWiFS Data
        Reprocessing, NASA Tech. Memo. 2003-206892, Vol. 22.
    Frouin, R.J. et al., 2019: Atmospheric correction of satellite
        ocean-color imagery during the PACE era. Front. Earth Sci. 7:145.

Core modeling ideas implemented here
-------------------------------------
1. The atmosphere-surface system is decoupled into a clear-sky
   (molecular + aerosol) layer sitting above a cloud/surface reflecting
   layer (Frouin & Chertock, 1992). This avoids explicit clear/cloudy
   pixel classification.
2. Clear-sky atmospheric (Rayleigh + aerosol) reflectance is computed
   with the quasi-single-scattering approximation of Tanre et al.
   (1979).
3. Gaseous transmittance (ozone, water vapor, uniformly mixed gases) is
   computed spectrally, in the spirit of the 5-nm-resolution gas
   transmittance calculations used for PACE/OCI (Frouin et al., 2019),
   using Bird & Riordan (1986)-style parametric transmittance forms.
4. A simple two-stream cloud transmittance closes the cloudy branch of
   the decoupled model.
5. Direct + diffuse spectral irradiance are combined into Ed(0+, lambda)
   and can be integrated over 400-700 nm to give PAR.

IMPORTANT — accuracy caveats
-----------------------------
This module reproduces the *equations and structure* of the published
algorithm. It does NOT embed NASA's operational, vicariously-calibrated
look-up tables, nor exact tabulated gas absorption cross-sections or a
reference extraterrestrial solar spectrum. For operational-grade
accuracy you should supply:
  - a reference hyperspectral extraterrestrial solar irradiance
    spectrum F0(lambda) (e.g., Thuillier 2003 or TSIS-1 HSRS), via
    `set_solar_spectrum()`;
  - an ozone absorption cross-section spectrum sigma_o3(lambda)
    (e.g., Bogumil/Serdyuchenko), via `set_ozone_cross_section()`;
  - a water-vapor absorption coefficient spectrum, via
    `set_water_vapor_coefficients()`.
Sensible built-in placeholders are used otherwise (see each setter's
docstring) so the module runs standalone for testing/demo purposes.

Units
-----
Wavelengths:        nanometers (nm)
Irradiance:         W m^-2 nm^-1 (spectral), W m^-2 (broadband/PAR energy)
PAR (photon flux):  mol quanta m^-2 s^-1 (instantaneous) or per day
Ozone column:       Dobson Units (DU)
Water vapor column: cm (precipitable water)
Pressure:            hPa
AOD:                dimensionless, at 550 nm reference
Cloud optical thickness: dimensionless
"""

from __future__ import annotations

import dataclasses
from typing import Optional, Callable

import numpy as np

# numpy >=2.0 renamed trapz -> trapezoid; keep this module working on
# either version.
_trapz = getattr(np, "trapezoid", None) or np.trapz

# ----------------------------------------------------------------------
# Physical constants
# ----------------------------------------------------------------------
STANDARD_PRESSURE_HPA = 1013.25
AVOGADRO = 6.02214076e23
PLANCK = 6.62607015e-34          # J s
LIGHTSPEED = 2.99792458e8        # m s^-1


# ----------------------------------------------------------------------
# Solar geometry
# ----------------------------------------------------------------------
def earth_sun_distance_factor(day_of_year: int) -> float:
    """
    Inverse-square correction (F0 / F0_mean_distance)^2 for Earth-Sun
    distance, Spencer (1971) Fourier approximation.
    """
    gamma = 2.0 * np.pi * (day_of_year - 1) / 365.0
    return (
        1.000110
        + 0.034221 * np.cos(gamma)
        + 0.001280 * np.sin(gamma)
        + 0.000719 * np.cos(2 * gamma)
        + 0.000077 * np.sin(2 * gamma)
    )


def relative_air_mass(sza_deg: np.ndarray) -> np.ndarray:
    """
    Kasten & Young (1989) relative optical air mass, valid to the
    horizon; more robust than 1/cos(sza) at large solar zenith angles.
    """
    sza = np.atleast_1d(np.asarray(sza_deg, dtype=float))
    m = 1.0 / (
        np.cos(np.radians(sza))
        + 0.50572 * (96.07995 - sza) ** (-1.6364)
    )
    return m


def pressure_corrected_air_mass(sza_deg: np.ndarray, pressure_hpa: float) -> np.ndarray:
    return relative_air_mass(sza_deg) * (pressure_hpa / STANDARD_PRESSURE_HPA)


# ----------------------------------------------------------------------
# Optical thickness / transmittance components
# ----------------------------------------------------------------------
def rayleigh_optical_thickness(wavelength_nm: np.ndarray, pressure_hpa: float) -> np.ndarray:
    """
    Spectral Rayleigh optical thickness, Bodhaine et al. (1999)-style
    scaling of the classic Bird (1984) formula, scaled to surface
    pressure.
    """
    lam_um = np.asarray(wavelength_nm, dtype=float) / 1000.0
    tau_r_1013 = 1.0 / (
        117.2594 * lam_um ** 4
        - 1.3215 * lam_um ** 2
        + 0.000320 * lam_um ** -2
        - 0.000076 * lam_um ** -4
    )
    return tau_r_1013 * (pressure_hpa / STANDARD_PRESSURE_HPA)


def aerosol_optical_thickness(
    wavelength_nm: np.ndarray, aod_550: float, angstrom_exponent: float = 1.2
) -> np.ndarray:
    """Angstrom power-law spectral aerosol optical thickness."""
    lam = np.asarray(wavelength_nm, dtype=float)
    return aod_550 * (550.0 / lam) ** angstrom_exponent


def rayleigh_reflectance_qss(
    tau_r: np.ndarray, sza_deg: float, vza_deg: float, raa_deg: float = 0.0
) -> np.ndarray:
    """
    Quasi-single-scattering (QSS) atmospheric reflectance for the
    Rayleigh component, following the Tanre et al. (1979) formulation
    used by Frouin & Chertock (1992):

        R_a = (tau_r * P_r) / (4 * cos(theta_s) * cos(theta_v))

    P_r is the Rayleigh scattering phase function evaluated at the
    scattering angle.
    """
    theta_s = np.radians(sza_deg)
    theta_v = np.radians(vza_deg)
    phi = np.radians(raa_deg)
    cos_scat = -np.cos(theta_s) * np.cos(theta_v) + np.sin(theta_s) * np.sin(theta_v) * np.cos(phi)
    p_rayleigh = 0.75 * (1.0 + cos_scat ** 2)
    return (tau_r * p_rayleigh) / (4.0 * np.cos(theta_s) * np.cos(theta_v))


def aerosol_reflectance_qss(
    tau_a: np.ndarray,
    ssa: float,
    sza_deg: float,
    vza_deg: float,
    raa_deg: float = 0.0,
    asymmetry: float = 0.7,
) -> np.ndarray:
    """
    Quasi-single-scattering aerosol reflectance, Henyey-Greenstein
    phase function as an analytically convenient stand-in for a full
    Mie phase function.
    """
    theta_s = np.radians(sza_deg)
    theta_v = np.radians(vza_deg)
    phi = np.radians(raa_deg)
    cos_scat = -np.cos(theta_s) * np.cos(theta_v) + np.sin(theta_s) * np.sin(theta_v) * np.cos(phi)
    g = asymmetry
    p_aer = (1 - g ** 2) / (1 + g ** 2 - 2 * g * cos_scat) ** 1.5
    return (ssa * tau_a * p_aer) / (4.0 * np.cos(theta_s) * np.cos(theta_v))


def ozone_transmittance(
    wavelength_nm: np.ndarray,
    ozone_du: float,
    sza_deg: float,
    sigma_o3: Optional[Callable[[np.ndarray], np.ndarray]] = None,
) -> np.ndarray:
    """
    Spectral ozone transmittance: T_o3 = exp(-sigma_o3(lambda) * N_o3 * m)

    ozone_du   : total column ozone in Dobson Units (1 DU = 2.1415e-5 kg m^-2
                 = 2.687e16 molecules cm^-2)
    sigma_o3   : optional callable returning absorption cross-section
                 (cm^2/molecule) given wavelength_nm array. If not
                 supplied, a coarse Chappuis + Hartley-Huggins band
                 Gaussian placeholder is used — replace with a real
                 cross-section spectrum (e.g. Bogumil et al. 2003) for
                 quantitative work.
    """
    lam = np.asarray(wavelength_nm, dtype=float)
    n_o3 = ozone_du * 2.687e16  # molecules cm^-2

    if sigma_o3 is None:
        # Coarse placeholder: Hartley-Huggins UV band (~255 nm) +
        # Chappuis visible band (~600 nm), each a Gaussian in log-space.
        hartley = 4.0e-18 * np.exp(-0.5 * ((lam - 255.0) / 15.0) ** 2)
        chappuis = 5.0e-21 * np.exp(-0.5 * ((lam - 600.0) / 80.0) ** 2)
        sigma = hartley + chappuis
    else:
        sigma = sigma_o3(lam)

    m_o3 = relative_air_mass(sza_deg)  # simple slant path; refine with
                                        # an ozone-layer-height air mass
                                        # formula if higher accuracy needed
    return np.exp(-sigma * n_o3 * m_o3)


def water_vapor_transmittance(
    wavelength_nm: np.ndarray,
    water_vapor_cm: float,
    sza_deg: float,
    pressure_hpa: float,
    a_w: Optional[Callable[[np.ndarray], np.ndarray]] = None,
) -> np.ndarray:
    """
    Spectral water-vapor transmittance, Bird & Riordan (1986) form:

        T_w = exp( -0.2385 * a_w(lambda) * W * m /
                    (1 + 20.07 * a_w(lambda) * W * m) ** 0.45 )

    a_w    : water-vapor absorption coefficient spectrum (dimensionless
             empirical coefficient from Bird & Riordan tables). If not
             supplied, only the strong 720/820/940/1130 nm bands are
             represented as narrow Gaussian absorption features and all
             other wavelengths are treated as transparent to water
             vapor — replace with tabulated coefficients for accurate
             red/NIR work.
    """
    lam = np.asarray(wavelength_nm, dtype=float)
    m = pressure_corrected_air_mass(sza_deg, pressure_hpa)

    if a_w is None:
        bands = [(720, 10), (820, 12), (940, 20), (1130, 15)]
        a = np.zeros_like(lam)
        for center, width in bands:
            a += np.exp(-0.5 * ((lam - center) / width) ** 2)
    else:
        a = a_w(lam)

    x = a * water_vapor_cm * m
    return np.exp(-0.2385 * x / (1.0 + 20.07 * x) ** 0.45)


def mixed_gas_transmittance(sza_deg: float, pressure_hpa: float) -> float:
    """
    Broadband transmittance for well-mixed gases (mainly O2, CO2),
    Bird & Riordan (1986) closed-form scalar (weak spectral dependence,
    treated as spectrally flat here).
    """
    m = pressure_corrected_air_mass(sza_deg, pressure_hpa)
    t = np.exp(-1.41 * 0.35 * m / (1.0 + 118.3 * 0.35 * m) ** 0.45)
    return float(np.asarray(t).reshape(-1)[0])


def cloud_transmittance(cloud_optical_thickness: float, ssa_cloud: float = 0.9999) -> float:
    """
    Plane-parallel two-stream (Lacis & Hansen, 1974-style) cloud
    transmittance, used for the "cloud/surface" branch of the
    decoupled Frouin & Chertock model.
    """
    tau_c = max(cloud_optical_thickness, 0.0)
    if tau_c == 0.0:
        return 1.0
    beta = np.sqrt(3.0 * (1.0 - ssa_cloud))
    tau_star = beta * tau_c
    return float(2.0 / (2.0 + tau_star))


# ----------------------------------------------------------------------
# Solar spectrum handling
# ----------------------------------------------------------------------
def default_solar_spectrum(wavelength_nm: np.ndarray) -> np.ndarray:
    """
    Coarse blackbody-based placeholder extraterrestrial solar spectrum
    (NOT a substitute for a real reference spectrum). Normalized so the
    integral over 400-700 nm is roughly consistent with the ~1360 W m^-2
    total solar irradiance partitioned into the visible.
    Replace via `set_solar_spectrum()` with Thuillier (2003) or TSIS-1
    HSRS for quantitative work.
    """
    lam_m = np.asarray(wavelength_nm, dtype=float) * 1e-9
    t_sun = 5778.0
    r_sun_m = 6.957e8       # solar radius, m
    au_m = 1.495978707e11   # 1 AU, m
    h, c, k = 6.62607015e-34, 2.99792458e8, 1.380649e-23

    # Planck spectral radiance, W m^-2 sr^-1 m^-1
    spectral_radiance = (2 * h * c ** 2) / (
        lam_m ** 5 * (np.exp(h * c / (lam_m * k * t_sun)) - 1.0)
    )
    # Surface exitance (W m^-2 m^-1) -> irradiance at 1 AU via inverse-square
    # scaling by the solar disk solid angle: E(lambda) = pi*B(lambda,T)*(R_sun/AU)^2.
    # This reproduces the ~1361 W m^-2 total solar constant when integrated.
    e_per_m = np.pi * spectral_radiance * (r_sun_m / au_m) ** 2  # W m^-2 m^-1
    e_per_nm = e_per_m * 1e-9  # W m^-2 nm^-1
    return e_per_nm


# ----------------------------------------------------------------------
# Main algorithm class
# ----------------------------------------------------------------------
@dataclasses.dataclass
class AtmosphericState:
    sza_deg: float
    vza_deg: float = 0.0
    raa_deg: float = 0.0
    day_of_year: int = 172
    pressure_hpa: float = STANDARD_PRESSURE_HPA
    ozone_du: float = 300.0
    water_vapor_cm: float = 2.0
    aod_550: float = 0.1
    angstrom_exponent: float = 1.2
    aerosol_ssa: float = 0.95
    aerosol_asymmetry: float = 0.7
    cloud_optical_thickness: float = 0.0
    cloud_fraction: float = 0.0


class FrouinIrradiance:
    """
    Spectral downwelling irradiance just above the sea surface,
    Ed(0+, lambda), computed with the decoupled clear-sky/cloud
    approach of Frouin & Chertock (1992) extended to hyperspectral
    resolution in the spirit of Frouin et al. (2019).

    Example
    -------
    >>> wl = np.arange(350, 900, 1.0)          # nm, hyperspectral grid
    >>> state = AtmosphericState(sza_deg=30.0, ozone_du=280.0,
    ...                           water_vapor_cm=1.5, aod_550=0.08)
    >>> model = FrouinIrradiance()
    >>> ed = model.downwelling_irradiance(wl, state)   # W m^-2 nm^-1
    >>> par = model.par_from_spectrum(wl, ed)          # mol quanta m^-2 s^-1
    """

    def __init__(self):
        self._solar_spectrum_fn: Callable[[np.ndarray], np.ndarray] = default_solar_spectrum
        self._sigma_o3_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None
        self._a_w_fn: Optional[Callable[[np.ndarray], np.ndarray]] = None

    # -- setters for accurate ancillary spectra -------------------------
    def set_solar_spectrum(self, fn: Callable[[np.ndarray], np.ndarray]) -> None:
        """fn(wavelength_nm) -> F0 in W m^-2 nm^-1 at 1 AU."""
        self._solar_spectrum_fn = fn

    def set_ozone_cross_section(self, fn: Callable[[np.ndarray], np.ndarray]) -> None:
        """fn(wavelength_nm) -> ozone absorption cross-section, cm^2/molecule."""
        self._sigma_o3_fn = fn

    def set_water_vapor_coefficients(self, fn: Callable[[np.ndarray], np.ndarray]) -> None:
        """fn(wavelength_nm) -> Bird & Riordan a_w(lambda) coefficients."""
        self._a_w_fn = fn

    # -- core computation -------------------------------------------------
    def downwelling_irradiance(
        self, wavelength_nm: np.ndarray, state: AtmosphericState
    ) -> np.ndarray:
        """
        Returns spectral Ed(0+, lambda) in W m^-2 nm^-1, combining direct
        and diffuse components, gas transmittance, and the decoupled
        clear/cloud atmospheric branches.
        """
        lam = np.asarray(wavelength_nm, dtype=float)

        f0 = self._solar_spectrum_fn(lam)
        d_factor = earth_sun_distance_factor(state.day_of_year)
        f0_toa = f0 * d_factor

        mu0 = np.cos(np.radians(state.sza_deg))
        if mu0 <= 0:
            return np.zeros_like(lam)

        # --- optical thicknesses ---
        tau_r = rayleigh_optical_thickness(lam, state.pressure_hpa)
        tau_a = aerosol_optical_thickness(lam, state.aod_550, state.angstrom_exponent)

        # --- gas transmittances ---
        t_o3 = ozone_transmittance(lam, state.ozone_du, state.sza_deg, self._sigma_o3_fn)
        t_w = water_vapor_transmittance(
            lam, state.water_vapor_cm, state.sza_deg, state.pressure_hpa, self._a_w_fn
        )
        t_g = mixed_gas_transmittance(state.sza_deg, state.pressure_hpa)
        t_gas = t_o3 * t_w * t_g

        # --- clear-sky direct-beam transmittance (Beer-Lambert) ---
        m = relative_air_mass(state.sza_deg)
        t_r_dir = np.exp(-tau_r * m)
        t_a_dir = np.exp(-tau_a * m)

        # --- clear-sky diffuse via QSS atmospheric reflectance,
        #     used as a proxy for scattered-into-diffuse fraction ---
        r_r = rayleigh_reflectance_qss(tau_r, state.sza_deg, state.vza_deg, state.raa_deg)
        r_a = aerosol_reflectance_qss(
            tau_a, state.aerosol_ssa, state.sza_deg, state.vza_deg,
            state.raa_deg, state.aerosol_asymmetry,
        )
        diffuse_fraction = np.clip(r_r + r_a, 0.0, 0.9)

        # --- decoupled cloud-layer transmittance ---
        t_cloud = cloud_transmittance(state.cloud_optical_thickness)
        cf = np.clip(state.cloud_fraction, 0.0, 1.0)
        t_cloud_eff = (1 - cf) * 1.0 + cf * t_cloud

        # --- assemble direct + diffuse spectral irradiance at surface ---
        e_direct = f0_toa * mu0 * t_r_dir * t_a_dir * t_gas * t_cloud_eff * (1 - diffuse_fraction)
        e_diffuse = f0_toa * mu0 * t_gas * t_cloud_eff * diffuse_fraction

        ed = e_direct + e_diffuse
        return np.clip(ed, 0.0, None)

    # -- integration utilities -------------------------------------------
    @staticmethod
    def par_from_spectrum(
        wavelength_nm: np.ndarray, ed_spectral: np.ndarray
    ) -> float:
        """
        Integrate spectral irradiance (W m^-2 nm^-1) over 400-700 nm and
        convert to an instantaneous photon flux (mol quanta m^-2 s^-1),
        i.e. PAR / iPAR depending on the Ed(0+) used as input.
        """
        lam = np.asarray(wavelength_nm, dtype=float)
        ed = np.asarray(ed_spectral, dtype=float)
        mask = (lam >= 400.0) & (lam <= 700.0)
        lam_par = lam[mask]
        ed_par = ed[mask]

        # energy per photon at each wavelength: E = h c / lambda
        lam_m = lam_par * 1e-9
        e_photon = PLANCK * LIGHTSPEED / lam_m  # J per photon
        photon_flux_density = ed_par / e_photon  # photons m^-2 s^-1 nm^-1

        photon_flux = _trapz(photon_flux_density, lam_par)  # photons m^-2 s^-1
        mol_quanta_flux = photon_flux / AVOGADRO  # mol m^-2 s^-1
        return float(mol_quanta_flux)

    @staticmethod
    def broadband_irradiance(wavelength_nm: np.ndarray, ed_spectral: np.ndarray) -> float:
        """Integrate spectral irradiance (W m^-2 nm^-1) to W m^-2."""
        return float(_trapz(np.asarray(ed_spectral, dtype=float), np.asarray(wavelength_nm, dtype=float)))


# ----------------------------------------------------------------------
# Integration with anequim.core.spectral_cube.SpectralCube
# ----------------------------------------------------------------------
def aod550_from_aot865(aot_865: float, angstrom_exponent: float) -> float:
    """
    Convert PACE OCI's native aerosol optical thickness at 865 nm
    (``SpectralCube.atmospheric["aot_865"]``) to 550 nm using the
    scene's own Angstrom exponent
    (``SpectralCube.atmospheric["angstrom"]``), via the standard
    Angstrom power law:

        AOD(550) = AOD(865) * (865 / 550) ** angstrom_exponent

    Preferred over a reanalysis (e.g. MERRA-2) aerosol field when the
    granule provides these, since they are scene-matched and typically
    higher spatial resolution than a ~50 km reanalysis grid cell.
    """
    return float(aot_865 * (865.0 / 550.0) ** angstrom_exponent)


def atmospheric_state_from_cube(
    cube,
    pixel_index: int = 0,
    ozone_du: Optional[float] = None,
    water_vapor_cm: Optional[float] = None,
    pressure_hpa: Optional[float] = None,
    cloud_optical_thickness: float = 0.0,
    cloud_fraction: float = 0.0,
) -> AtmosphericState:
    """
    Build an :class:`AtmosphericState` for this model directly from an
    ``anequim.core.spectral_cube.SpectralCube``, using:

    - ``solar_zenith`` / ``sensor_zenith`` / ``relative_azimuth`` from
      ``cube.atmospheric`` (present whenever the granule provides them
      and ``include_atmospheric=True``);
    - ``aot_865`` + ``angstrom`` from ``cube.atmospheric``, converted
      to ``aod_550`` via :func:`aod550_from_aot865`;
    - ``acquisition_time`` from ``cube.provenance`` for day-of-year;
    - ``ozone_du`` / ``water_vapor_cm`` / ``pressure_hpa``, which the
      granule does NOT provide — pass these explicitly (typically from
      ``anequim.download.ancillary.fetch_atmospheric_ancillary``, or
      already merged into ``cube.atmospheric`` when
      ``Anequim.get_rrs(..., include_ancillary_atmosphere=True)`` was
      used, in which case they're read from there automatically if
      not passed here).

    pixel_index selects which pixel of the (possibly multi-pixel) ROI
    to build the state for — atmospheric ancillary fields are
    typically near-uniform across a small match-up box, so the default
    (first pixel) is usually representative; pass an explicit index if
    you need a specific one.

    Raises
    ------
    KeyError
        If ozone/water vapor/pressure aren't available either as an
        explicit argument or in ``cube.atmospheric``, and geometry
        (solar_zenith) is required but missing from the granule.
    """
    import datetime as _dt

    atm = cube.atmospheric

    def _get(name: str, override: Optional[float]) -> float:
        if override is not None:
            return override
        if name not in atm:
            raise KeyError(
                f"'{name}' not found in cube.atmospheric and no override was passed. "
                f"Fetch it (e.g. anequim.download.ancillary.fetch_atmospheric_ancillary) "
                f"and pass it explicitly, or re-run get_rrs with "
                f"include_ancillary_atmosphere=True."
            )
        return float(atm[name][pixel_index])

    sza = _get("solar_zenith", None)
    vza = float(atm["sensor_zenith"][pixel_index]) if "sensor_zenith" in atm else 0.0
    raa = float(atm["relative_azimuth"][pixel_index]) if "relative_azimuth" in atm else 0.0

    if "aot_865" in atm and "angstrom" in atm:
        angstrom = float(atm["angstrom"][pixel_index])
        aod_550 = aod550_from_aot865(float(atm["aot_865"][pixel_index]), angstrom)
    else:
        angstrom = 1.2
        aod_550 = 0.1  # coarse background default if the granule lacks aerosol products

    ozone = _get("ozone_du", ozone_du)
    water_vapor = _get("water_vapor_cm", water_vapor_cm)
    if pressure_hpa is not None:
        pressure = pressure_hpa
    elif "surface_pressure_hpa" in atm:
        pressure = float(atm["surface_pressure_hpa"][pixel_index])
    else:
        pressure = STANDARD_PRESSURE_HPA

    acq_time = cube.provenance.acquisition_time
    day_of_year = _dt.datetime.fromisoformat(acq_time).timetuple().tm_yday if acq_time else 172

    return AtmosphericState(
        sza_deg=sza,
        vza_deg=vza,
        raa_deg=raa,
        day_of_year=day_of_year,
        pressure_hpa=pressure,
        ozone_du=ozone,
        water_vapor_cm=water_vapor,
        aod_550=aod_550,
        angstrom_exponent=angstrom,
        cloud_optical_thickness=cloud_optical_thickness,
        cloud_fraction=cloud_fraction,
    )


# ----------------------------------------------------------------------
# Self-test / usage example
# ----------------------------------------------------------------------
if __name__ == "__main__":
    wl = np.arange(350.0, 900.0, 1.0)
    state = AtmosphericState(
        sza_deg=30.0,
        vza_deg=0.0,
        day_of_year=172,
        pressure_hpa=1013.25,
        ozone_du=280.0,
        water_vapor_cm=1.5,
        aod_550=0.08,
        angstrom_exponent=1.0,
        cloud_optical_thickness=0.0,
        cloud_fraction=0.0,
    )

    model = FrouinIrradiance()
    ed = model.downwelling_irradiance(wl, state)
    par = model.par_from_spectrum(wl, ed)
    broadband = model.broadband_irradiance(wl, ed)

    print(f"Peak Ed(0+): {ed.max():.3f} W m^-2 nm^-1 at {wl[np.argmax(ed)]:.0f} nm")
    print(f"Broadband Ed(0+) [350-900nm]: {broadband:.1f} W m^-2")
    print(f"Instantaneous PAR (400-700nm): {par * 1e6:.2f} micromol quanta m^-2 s^-1")
