# Installing anequim

## From this zip (local)
```bash
unzip anequim.zip
pip install -e "./anequim[all]"
```

## From GitHub (once merged)
```bash
pip install git+https://github.com/lucasbarbedo83/anequim.git
# or, with all optional extras (download, plot, xarray, test):
pip install "anequim[all] @ git+https://github.com/lucasbarbedo83/anequim.git"
```

## Extras
- `anequim[download]` — earthaccess + requests + eumdac (all download backends)
- `anequim[plot]` — matplotlib (plot_spectrum)
- `anequim[xarray]` — xarray export (SpectralCube.to_xarray())
- `anequim[test]` — pytest
- `anequim[all]` — everything above

## Verify
```bash
python -c "import anequim; print(anequim.__version__, anequim.__author__)"
```

## One-time credential setup (only needed for Anequim.retrieve_online)

**PACE OCI / MODIS / VIIRS (NASA Earthdata):**
1. Free account: https://urs.earthdata.nasa.gov/
2. `python -c "from anequim.download import login; login(strategy='interactive', persist=True)"`
   (saves credentials to ~/.netrc; covers all three NASA sensors)

**Sentinel-3 OLCI — default backend, EUMETSAT Data Store (eumdac):**
1. Free account: https://user.eumetsat.int/register
2. Log in, open your profile -> "My data licenses" -> enable "Meteosat > 1hr
   latency & Metop, Copernicus data & Third party data" (easy to miss --
   Sentinel-3 won't work without this even with valid credentials)
3. Generate a consumer key/secret: https://api.eumetsat.int/api-key
4. `export EUMETSAT_CONSUMER_KEY=...` / `export EUMETSAT_CONSUMER_SECRET=...`

**Sentinel-3 OLCI — alternative backend, Copernicus Data Space Ecosystem (CDSE):**
1. Free account with direct email+password: https://dataspace.copernicus.eu/
   (not Google/institutional SSO)
2. `export CDSE_USERNAME=you@example.com` / `export CDSE_PASSWORD=...`
3. If your account has 2FA enabled:
   `python -c "from anequim.download.copernicus import login; login(totp='123456')"`
   (caches a refresh token to ~/.anequim/cdse_refresh_token; after this,
   retrieve_online(sensor="OLCI", download_kwargs={"backend": "cdse"}) works
   silently, no more password/2FA needed until that refresh token expires)
4. Use with `Anequim.retrieve_online(..., sensor="OLCI", download_kwargs={"backend": "cdse"})`

## Quick test (no credentials, no real data needed)
```bash
python examples/quickstart.py
```

## Sensor cheat sheet

| sensor= | Agency | Download backend | Credentials |
|---|---|---|---|
| "OCI" | NASA | earthaccess | Earthdata Login |
| "MODIS" (platform="Aqua"/"Terra") | NASA | earthaccess | Earthdata Login |
| "VIIRS" (platform="SNPP"/"NOAA-20") | NASA | earthaccess | Earthdata Login |
| "OLCI" | ESA/EUMETSAT | eumdac (default) or CDSE | EUMETSAT or CDSE account |
