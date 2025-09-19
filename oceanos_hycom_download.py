# -*- coding: utf-8 -*-
"""
HYCOM Ocean Data Downloader (Flask-friendly, h5netcdf-first, robust fallbacks)

Features:
- Requests NetCDF4/HDF5 from HYCOM NCSS (accept=netcdf4)
- Safe open that prefers h5netcdf (installed), then autodetect, then scipy
- Month-end capping to respect DATE_END
- Cheap validation (no full array read)
- Handles missing Content-Length in tqdm
- Compressed NetCDF writing via h5netcdf; falls back to scipy if needed

Public API (used by Flask app):
- Config
- get_hycom_url(date: datetime, var: str) -> str
- download_file_with_retry(date: datetime, var: str) -> Optional[Path]
- redownload_failed(failed_items, attempts=1) -> (List[Path], List[Tuple[datetime,str]])
- combine_files(files: List[Path]) -> xr.Dataset
- safe_open_dataset(path: Path) -> xr.Dataset
- write_netcdf_with_fallback(ds: xr.Dataset, nc_path: Path, encoding: dict) -> str
- main() -> None (for standalone execution)
"""

import requests
import pandas as pd
import xarray as xr
import zipfile
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from tqdm import tqdm
import time

# ---------------------------
# Configuration
# ---------------------------
class Config:
    """Configuration class for HYCOM downloader"""
    # Geographic bounds
    WEST_LON = 116.5
    EAST_LON = 119
    SOUTH_LAT = -2
    NORTH_LAT = 0.5

    # Date range
    DATE_START = '2022-12-01'
    DATE_END   = '2022-12-02'

    # Variables to download
    VARIABLES = ['water_u', 'water_v']

    # Local storage paths
    BASE_DIR = Path('./hycom_data')
    TEMP_DIR = Path('./temp_download')

    # Download settings
    MAX_RETRIES = 3
    TIMEOUT = 60
    CHUNK_SIZE = 8192

    @classmethod
    def setup_directories(cls):
        cls.BASE_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        return cls.BASE_DIR, cls.TEMP_DIR

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('hycom_download.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize configuration
config = Config()
base_dir, temp_dir = config.setup_directories()

# ---------------------------
# Helpers
# ---------------------------
def get_hycom_url(date: datetime, var: str) -> str:
    """Generate HYCOM NCSS URL (request NetCDF4/HDF5)."""
    date_str = date.strftime('%Y-%m-%d')
    base_url = "https://ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0"
    # Request NetCDF4 to match h5netcdf/NetCDF4 backends
    return (f"{base_url}?var={var}&north={config.NORTH_LAT}&west={config.WEST_LON}"
            f"&east={config.EAST_LON}&south={config.SOUTH_LAT}&disableProjSubset=on"
            f"&horizStride=1&time_start={date_str}T12:00:00Z&time_end={date_str}T12:00:00Z"
            f"&timeStride=1&addLatLon=true&accept=netcdf4")

def safe_open_dataset(path: Path):
    """
    Open a dataset by trying multiple engines for robustness.
    Prefer h5netcdf (installed), then autodetect, then scipy.
    """
    engines = ["h5netcdf", None, "scipy"]
    last_err = None
    for eng in engines:
        try:
            return xr.open_dataset(path, engine=eng) if eng else xr.open_dataset(path)
        except Exception as e:
            last_err = e
    raise last_err if last_err else RuntimeError("Failed to open dataset with any engine")

def download_file_with_retry(date: datetime, var: str) -> Optional[Path]:
    """Download a single HYCOM file with retry mechanism and cheap validation."""
    url = get_hycom_url(date, var)
    filename = f"hycom_{var}_{date.strftime('%Y%m%d')}.nc"
    filepath = temp_dir / filename

    for attempt in range(config.MAX_RETRIES):
        try:
            logger.info(f"Downloading {filename} (attempt {attempt + 1}/{config.MAX_RETRIES})")
            resp = requests.get(url, timeout=config.TIMEOUT, stream=True)
            resp.raise_for_status()

            total_size = int(resp.headers.get('content-length', 0))
            with open(filepath, 'wb') as f:
                with tqdm(total=total_size if total_size > 0 else None,
                          unit='B', unit_scale=True, desc=filename, leave=False) as pbar:
                    for chunk in resp.iter_content(chunk_size=config.CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            # Cheap validation (no full array read) with safe engine selection
            try:
                with safe_open_dataset(filepath) as ds:
                    if (var in ds.data_vars) and (ds[var].size > 0):
                        logger.info(f"Successfully downloaded: {filename}")
                        return filepath
                    else:
                        logger.warning(f"File {filename} has no data for variable '{var}'")
            except Exception as e:
                logger.error(f"Failed to validate file {filename}: {e}")

            if filepath.exists():
                filepath.unlink()

        except requests.exceptions.RequestException as e:
            logger.warning(f"Download attempt {attempt + 1} failed for {filename}: {e}")
            if filepath.exists():
                filepath.unlink()
            if attempt < config.MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.info(f"Retrying in {wait} seconds...")
                time.sleep(wait)
        except Exception as e:
            logger.error(f"Unexpected error downloading {filename}: {e}")
            if filepath.exists():
                filepath.unlink()
            break

    logger.error(f"Failed to download {filename} after {config.MAX_RETRIES} attempts")
    return None

def redownload_failed(failed_items: List[Tuple[datetime, str]], attempts: int = 1) -> Tuple[List[Path], List[Tuple[datetime, str]]]:
    if not failed_items:
        return [], []
    logger.info(f"Starting redownload pass for {len(failed_items)} failed items (passes={attempts})")
    successful, remaining = [], failed_items[:]
    for _ in range(attempts):
        if not remaining:
            break
        current, remaining = remaining, []
        for date_obj, var in current:
            path = download_file_with_retry(date_obj, var)
            if path:
                successful.append(path)
            else:
                remaining.append((date_obj, var))
        logger.info(f"Redownload round complete. Recovered {len(successful)} so far. Remaining: {len(remaining)}")
    return successful, remaining

def combine_files(files: List[Path]) -> xr.Dataset:
    """Combine NetCDF files into one dataset (safe engine opener)."""
    if not files:
        raise ValueError("No files provided for combining")
    logger.info(f"Combining {len(files)} files...")

    import re
    var_files = {}
    for p in files:
        m = re.match(r'hycom_(.+)_(\d{8})\.nc', p.name)
        if m:
            var_files.setdefault(m.group(1), []).append(p)
        else:
            logger.warning(f"Could not parse filename: {p.name}")

    if not var_files:
        raise ValueError("No valid files found for combining")

    datasets = []
    for var_name, file_list in var_files.items():
        logger.info(f"Combining {len(file_list)} files for variable: {var_name}")
        file_list.sort()
        var_datasets = []
        for f in file_list:
            try:
                ds = safe_open_dataset(f)
                var_datasets.append(ds)
            except Exception as e:
                logger.error(f"Failed to open {f}: {e}")
        if not var_datasets:
            logger.error(f"No valid datasets for variable {var_name}")
            continue

        # Optional: check dims consistency
        first_dims = set(var_datasets[0].dims.keys())
        for ds in var_datasets[1:]:
            if set(ds.dims.keys()) != first_dims:
                logger.warning(f"Dimension mismatch in {var_name} files")

        combined_var = xr.concat(var_datasets, dim='time')
        datasets.append(combined_var)
        logger.info(f"Successfully combined {len(var_datasets)} files for {var_name}")

        # Close children (concat holds references)
        for ds in var_datasets:
            try:
                ds.close()
            except Exception:
                pass

    if not datasets:
        raise ValueError("No datasets could be combined")

    try:
        final = xr.merge(datasets)
        final.attrs.update({
            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': 'HYCOM',
            'variables': list(var_files.keys())
        })
        logger.info(f"Successfully created combined dataset with variables: {list(var_files.keys())}")
        return final
    except Exception as e:
        logger.error(f"Failed to merge datasets: {e}")
        for ds in datasets:
            try:
                ds.close()
            except Exception:
                pass
        raise

def write_netcdf_with_fallback(ds: xr.Dataset, nc_path: Path, encoding: dict):
    """
    Try to write with h5netcdf (compression). If that fails, fall back to scipy (no compression).
    """
    try:
        import h5netcdf  # probe availability
        ds.to_netcdf(nc_path, engine="h5netcdf", encoding=encoding)
        return "h5netcdf (compressed)"
    except Exception as e:
        logger.warning(f"h5netcdf write failed ({e}). Falling back to scipy without compression.")
        ds.to_netcdf(nc_path, engine="scipy")
        return "scipy (uncompressed)"

# ---------------------------
# Main (for standalone execution)
# ---------------------------
def main():
    logger.info("Starting HYCOM Data Download - Monthly Processing")
    logger.info("=" * 50)
    try:
        start_date_obj = datetime.strptime(config.DATE_START, '%Y-%m-%d')
        end_date_obj   = datetime.strptime(config.DATE_END,   '%Y-%m-%d')

        logger.info(f"Date range: {config.DATE_START} to {config.DATE_END}")
        logger.info(f"Variables: {config.VARIABLES}")
        logger.info(f"Geographic bounds: {config.SOUTH_LAT}°N to {config.NORTH_LAT}°N, {config.WEST_LON}°E to {config.EAST_LON}°E")
        logger.info(f"Output directory: {base_dir}")

        current_date = start_date_obj
        while current_date <= end_date_obj:
            month_start = current_date
            # End of this calendar month
            if current_date.month == 12:
                month_end = datetime(current_date.year, 12, 31)
            else:
                month_end = datetime(current_date.year, current_date.month + 1, 1) - pd.Timedelta(days=1)
            # Cap by DATE_END
            month_end = min(month_end, end_date_obj)
            if month_end < month_start:
                break

            dates_in_month = pd.date_range(start=month_start, end=month_end, freq='D')
            total_files_month = len(dates_in_month) * len(config.VARIABLES)

            logger.info(f"\nProcessing month: {month_start.strftime('%Y-%m')} (capped end: {month_end.strftime('%Y-%m-%d')})")
            downloaded_files_month: List[Path] = []
            failed_items: List[Tuple[datetime, str]] = []

            with tqdm(total=total_files_month, desc=f"Downloading {month_start.strftime('%Y-%m')}") as pbar:
                for date in dates_in_month:
                    for var in config.VARIABLES:
                        path = download_file_with_retry(date, var)
                        if path:
                            downloaded_files_month.append(path)
                        else:
                            failed_items.append((date, var))
                        pbar.update(1)

            if failed_items:
                logger.warning(f"Initial failures: {len(failed_items)}. Attempting redownload pass...")
                recovered, remaining = redownload_failed(failed_items, attempts=1)
                downloaded_files_month.extend(recovered)
                if remaining:
                    logger.warning(f"Still failed after redownload: {len(remaining)} items")

            logger.info(f"Downloaded {len(downloaded_files_month)}/{total_files_month} files for {month_start.strftime('%Y-%m')}")

            if downloaded_files_month:
                try:
                    logger.info(f"Combining files for {month_start.strftime('%Y-%m')}...")
                    combined = combine_files(downloaded_files_month)

                    timestamp   = month_start.strftime('%Y%m')
                    nc_filename = f"HYCOM_combined_{timestamp}.nc"
                    zip_filename = f"HYCOM_data_{timestamp}.zip"
                    nc_path  = base_dir / nc_filename
                    zip_path = base_dir / zip_filename

                    # Encoding only for numeric variables (compression-ready)
                    encoding = {}
                    for name, da in combined.data_vars.items():
                        if da.dtype.kind in "ifub":
                            encoding[name] = {'zlib': True, 'complevel': 6}

                    logger.info(f"Saving NetCDF file: {nc_filename}")
                    write_engine_used = write_netcdf_with_fallback(combined, nc_path, encoding)

                    logger.info(f"Creating zip file: {zip_filename}")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        zipf.write(nc_path, nc_filename)

                    vars_list = list(combined.data_vars)
                    dims_dict = dict(combined.dims)
                    try:
                        nc_path.unlink(missing_ok=True)  # keep only the zip
                    except Exception:
                        pass
                    combined.close()

                    logger.info(f"Successfully created: {zip_filename}")
                    logger.info(f"Write engine: {write_engine_used}")
                    logger.info(f"Variables: {vars_list}")
                    if 'time' in dims_dict:
                        logger.info(f"Time steps: {dims_dict['time']}")
                    logger.info(f"Location: {zip_path}")

                except Exception as e:
                    logger.error(f"Failed to process files for {month_start.strftime('%Y-%m')}: {e}")
            else:
                logger.warning(f"No files downloaded for {month_start.strftime('%Y-%m')}!")

            # Next month
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1)

    except Exception as e:
        logger.error(f"Fatal error in main execution: {e}")
        raise
    finally:
        if temp_dir.exists():
            logger.info("Cleaning up temporary directory...")
            shutil.rmtree(temp_dir)
        logger.info("Download process completed!")

if __name__ == "__main__":
    main()