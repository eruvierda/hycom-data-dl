# -*- coding: utf-8 -*-
"""
HYCOM Ocean Data Downloader
Downloads HYCOM ocean model outputs and saves to local storage

Requirements:
- requests
- pandas
- xarray
- tqdm
- netCDF4
"""

import os
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

# Configuration
class Config:
    """Configuration class for HYCOM downloader"""
    
    # Geographic bounds
    WEST_LON = 116.5
    EAST_LON = 119
    SOUTH_LAT = -2
    NORTH_LAT = 0.5
    
    # Date range
    DATE_START = '2022-12-01'
    DATE_END = '2022-12-31'
    
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
        """Create necessary directories"""
        cls.BASE_DIR.mkdir(exist_ok=True)
        cls.TEMP_DIR.mkdir(exist_ok=True)
        return cls.BASE_DIR, cls.TEMP_DIR

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hycom_download.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize configuration
config = Config()
base_dir, temp_dir = config.setup_directories()

def get_hycom_url(date: datetime, var: str) -> str:
    """Generate HYCOM download URL"""
    date_str = date.strftime('%Y-%m-%d')
    base_url = "https://ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0"

    return (f"{base_url}?var={var}&north={config.NORTH_LAT}&west={config.WEST_LON}"
            f"&east={config.EAST_LON}&south={config.SOUTH_LAT}&disableProjSubset=on"
            f"&horizStride=1&time_start={date_str}T12:00:00Z&time_end={date_str}T12:00:00Z"
            f"&timeStride=1&addLatLon=true&accept=netcdf4")

def download_file_with_retry(date: datetime, var: str) -> Optional[Path]:
    """Download a single HYCOM file with retry mechanism"""
    url = get_hycom_url(date, var)
    filename = f"hycom_{var}_{date.strftime('%Y%m%d')}.nc"
    filepath = temp_dir / filename

    for attempt in range(config.MAX_RETRIES):
        try:
            logger.info(f"Downloading {filename} (attempt {attempt + 1}/{config.MAX_RETRIES})")
            
            response = requests.get(url, timeout=config.TIMEOUT, stream=True)
            response.raise_for_status()
            
            # Download with progress bar
            total_size = int(response.headers.get('content-length', 0))
            with open(filepath, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, 
                         desc=filename, leave=False) as pbar:
                    for chunk in response.iter_content(chunk_size=config.CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            # Validate file
            try:
                ds = xr.open_dataset(filepath)
                if var in ds and ds[var].count() > 0:
                    ds.close()
                    logger.info(f"Successfully downloaded: {filename}")
                    return filepath
                else:
                    logger.warning(f"File {filename} contains no data for variable {var}")
                    ds.close()
            except Exception as e:
                logger.error(f"Failed to validate file {filename}: {e}")
            
            # Remove invalid file
            if filepath.exists():
                filepath.unlink()
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Download attempt {attempt + 1} failed for {filename}: {e}")
            if filepath.exists():
                filepath.unlink()
            
            if attempt < config.MAX_RETRIES - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        except Exception as e:
            logger.error(f"Unexpected error downloading {filename}: {e}")
            if filepath.exists():
                filepath.unlink()
            break

    logger.error(f"Failed to download {filename} after {config.MAX_RETRIES} attempts")
    return None

def redownload_failed(failed_items: List[Tuple[datetime, str]], attempts: int = 1) -> Tuple[List[Path], List[Tuple[datetime, str]]]:
    """Attempt to re-download failed items before merging.

    Returns a tuple of (successful_paths, remaining_failures).
    """
    if not failed_items:
        return [], []

    logger.info(f"Starting redownload pass for {len(failed_items)} failed items (passes={attempts})")
    successful_paths: List[Path] = []
    remaining_failures: List[Tuple[datetime, str]] = failed_items[:]

    for _ in range(attempts):
        if not remaining_failures:
            break

        current_round = remaining_failures
        remaining_failures = []

        for date_obj, var in current_round:
            path = download_file_with_retry(date_obj, var)
            if path:
                successful_paths.append(path)
            else:
                remaining_failures.append((date_obj, var))

        logger.info(f"Redownload round complete. Recovered {len(successful_paths)} so far. Remaining: {len(remaining_failures)}")

    return successful_paths, remaining_failures

def combine_files(files: List[Path]) -> xr.Dataset:
    """Combine NetCDF files into one dataset"""
    if not files:
        raise ValueError("No files provided for combining")
    
    logger.info(f"Combining {len(files)} files...")
    
    # Group files by variable using regex pattern
    import re
    var_files = {}
    
    for file_path in files:
        filename = file_path.name
        # Use regex to extract variable name from filename: hycom_{var}_{date}.nc
        match = re.match(r'hycom_(.+)_(\d{8})\.nc', filename)
        if match:
            var_name = match.group(1)
            if var_name not in var_files:
                var_files[var_name] = []
            var_files[var_name].append(file_path)
        else:
            logger.warning(f"Could not parse filename: {filename}")

    if not var_files:
        raise ValueError("No valid files found for combining")

    # Combine each variable across time
    datasets = []
    for var_name, file_list in var_files.items():
        logger.info(f"Combining {len(file_list)} files for variable: {var_name}")
        file_list.sort()  # Sort by date
        
        try:
            # Open datasets with proper error handling
            var_datasets = []
            for f in file_list:
                try:
                    ds = xr.open_dataset(f)
                    var_datasets.append(ds)
                except Exception as e:
                    logger.error(f"Failed to open {f}: {e}")
                    continue
            
            if var_datasets:
                # Check if all datasets have the same dimensions
                first_dims = set(var_datasets[0].dims.keys())
                for ds in var_datasets[1:]:
                    if set(ds.dims.keys()) != first_dims:
                        logger.warning(f"Dimension mismatch in {var_name} files")
                
                combined_var = xr.concat(var_datasets, dim='time')
                datasets.append(combined_var)
                logger.info(f"Successfully combined {len(var_datasets)} files for {var_name}")
            else:
                logger.error(f"No valid datasets found for variable {var_name}")

            # Close individual datasets
            for ds in var_datasets:
                ds.close()
                
        except Exception as e:
            logger.error(f"Failed to combine files for variable {var_name}: {e}")
            continue

    if not datasets:
        raise ValueError("No datasets could be combined")

    # Merge all variables
    try:
        final_dataset = xr.merge(datasets)
        final_dataset.attrs['created'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        final_dataset.attrs['source'] = 'HYCOM'
        final_dataset.attrs['variables'] = list(var_files.keys())
        
        logger.info(f"Successfully created combined dataset with variables: {list(var_files.keys())}")
        return final_dataset
        
    except Exception as e:
        logger.error(f"Failed to merge datasets: {e}")
        # Close all datasets before raising
        for ds in datasets:
            ds.close()
        raise

def main():
    """Main execution function"""
    logger.info("Starting HYCOM Data Download - Monthly Processing")
    logger.info("=" * 50)
    
    try:
        start_date_obj = datetime.strptime(config.DATE_START, '%Y-%m-%d')
        end_date_obj = datetime.strptime(config.DATE_END, '%Y-%m-%d')
        
        logger.info(f"Date range: {config.DATE_START} to {config.DATE_END}")
        logger.info(f"Variables: {config.VARIABLES}")
        logger.info(f"Geographic bounds: {config.SOUTH_LAT}°N to {config.NORTH_LAT}°N, "
                   f"{config.WEST_LON}°E to {config.EAST_LON}°E")
        logger.info(f"Output directory: {base_dir}")

        current_date = start_date_obj
        while current_date <= end_date_obj:
            month_start = current_date
            # Calculate the last day of the current month
            if current_date.month == 12:
                month_end = datetime(current_date.year, 12, 31)
            else:
                month_end = datetime(current_date.year, current_date.month + 1, 1) - pd.Timedelta(days=1)

            logger.info(f"\nProcessing month: {month_start.strftime('%Y-%m')}")
            dates_in_month = pd.date_range(start=month_start, end=month_end, freq='D')
            downloaded_files_month = []

            total_files_month = len(dates_in_month) * len(config.VARIABLES)
            
            # Create progress bar for the month
            failed_items: List[Tuple[datetime, str]] = []
            with tqdm(total=total_files_month, desc=f"Downloading {month_start.strftime('%Y-%m')}") as pbar:
                for date in dates_in_month:
                    for var in config.VARIABLES:
                        file_path = download_file_with_retry(date, var)
                        if file_path:
                            downloaded_files_month.append(file_path)
                        else:
                            failed_items.append((date, var))
                        pbar.update(1)

            # Try redownload before combining
            if failed_items:
                logger.warning(f"Initial failures: {len(failed_items)}. Attempting redownload pass...")
                recovered_paths, remaining_failures = redownload_failed(failed_items, attempts=1)
                downloaded_files_month.extend(recovered_paths)
                if remaining_failures:
                    logger.warning(f"Still failed after redownload: {len(remaining_failures)} items")

            logger.info(f"Downloaded {len(downloaded_files_month)}/{total_files_month} files for {month_start.strftime('%Y-%m')}")

            if downloaded_files_month:
                try:
                    # Combine files for the month
                    logger.info(f"Combining files for {month_start.strftime('%Y-%m')}...")
                    combined_dataset_month = combine_files(downloaded_files_month)

                    # Save to zip
                    timestamp = month_start.strftime('%Y%m')
                    nc_filename = f"HYCOM_combined_{timestamp}.nc"
                    zip_filename = f"HYCOM_data_{timestamp}.zip"

                    nc_path = base_dir / nc_filename
                    zip_path = base_dir / zip_filename

                    # Save NetCDF with compression
                    logger.info(f"Saving NetCDF file: {nc_filename}")
                    combined_dataset_month.to_netcdf(nc_path, encoding={
                        var: {'zlib': True, 'complevel': 6} for var in combined_dataset_month.data_vars
                    })

                    # Create zip
                    logger.info(f"Creating zip file: {zip_filename}")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        zipf.write(nc_path, nc_filename)

                    # Cleanup
                    nc_path.unlink()  # Remove NetCDF file, keep only zip
                    combined_dataset_month.close()

                    logger.info(f"Successfully created: {zip_filename}")
                    logger.info(f"Variables: {list(combined_dataset_month.data_vars)}")
                    if 'time' in combined_dataset_month.dims:
                        logger.info(f"Time steps: {combined_dataset_month.dims['time']}")
                    logger.info(f"Location: {zip_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to process files for {month_start.strftime('%Y-%m')}: {e}")
            else:
                logger.warning(f"No files downloaded for {month_start.strftime('%Y-%m')}!")

            # Move to the next month
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1)

    except Exception as e:
        logger.error(f"Fatal error in main execution: {e}")
        raise
    finally:
        # Cleanup temp directory
        if temp_dir.exists():
            logger.info("Cleaning up temporary directory...")
            shutil.rmtree(temp_dir)
        logger.info("Download process completed!")

if __name__ == "__main__":
    main()