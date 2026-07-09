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
- `anequim[download]` — earthaccess + requests (PACE OCI / Sentinel-3 OLCI download)
- `anequim[plot]` — matplotlib (plot_spectrum)
- `anequim[xarray]` — xarray export (SpectralCube.to_xarray())
- `anequim[test]` — pytest
- `anequim[all]` — everything above

## Verify
```bash
python -c "import anequim; print(anequim.__version__)"
```

## One-time credential setup (only needed for Anequim.retrieve_online)

**PACE OCI (NASA Earthdata):**
1. Free account: https://urs.earthdata.nasa.gov/
2. `python -c "from anequim.download import login; login(strategy='interactive', persist=True)"`
   (saves credentials to ~/.netrc for future non-interactive use)

**Sentinel-3 OLCI (Copernicus Data Space Ecosystem):**
1. Free account with direct email+password: https://dataspace.copernicus.eu/
   (not Google/institutional SSO — not supported by this API path)
2. `export CDSE_USERNAME=you@example.com` / `export CDSE_PASSWORD=...`
3. If your account has 2FA enabled:
   `python -c "from anequim.download.copernicus import login; login(totp='123456')"`
   (caches a refresh token to ~/.anequim/cdse_refresh_token; after this,
   retrieve_online(sensor="OLCI", ...) works silently, no more password/2FA needed
   until that refresh token eventually expires)

## Quick test (no credentials, no real data needed)
```bash
python examples/quickstart.py
```
