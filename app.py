# -*- coding: utf-8 -*-
"""
HYCOM Data Downloader Flask Web Application
A web interface for downloading HYCOM ocean model data
Enhanced with robust h5netcdf-first processing from pure.py
"""

import os
import json
import threading
import time
import zipfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
import logging

# Import our enhanced downloader functionality
from oceanos_hycom_download import (
    Config, download_file_with_retry, combine_files, 
    get_hycom_url, redownload_failed, safe_open_dataset,
    write_netcdf_with_fallback
)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'hycom_downloader_secret_key_2024'

# Global variables for download status
download_status = {
    'is_running': False,
    'progress': 0,
    'total_files': 0,
    'current_file': '',
    'status_message': '',
    'error': None,
    'start_time': None,
    'end_time': None,
    'downloaded_files': [],
    'failed_files': []
}

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

# Ensure directories exist
Config.setup_directories()

@app.route('/')
def index():
    """Main page with download form"""
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify({
        'west_lon': Config.WEST_LON,
        'east_lon': Config.EAST_LON,
        'south_lat': Config.SOUTH_LAT,
        'north_lat': Config.NORTH_LAT,
        'date_start': Config.DATE_START,
        'date_end': Config.DATE_END,
        'variables': Config.VARIABLES,
        'max_retries': Config.MAX_RETRIES,
        'timeout': Config.TIMEOUT
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        data = request.get_json()
        
        # Update configuration
        Config.WEST_LON = float(data.get('west_lon', Config.WEST_LON))
        Config.EAST_LON = float(data.get('east_lon', Config.EAST_LON))
        Config.SOUTH_LAT = float(data.get('south_lat', Config.SOUTH_LAT))
        Config.NORTH_LAT = float(data.get('north_lat', Config.NORTH_LAT))
        Config.DATE_START = data.get('date_start', Config.DATE_START)
        Config.DATE_END = data.get('date_end', Config.DATE_END)
        Config.VARIABLES = data.get('variables', Config.VARIABLES)
        Config.MAX_RETRIES = int(data.get('max_retries', Config.MAX_RETRIES))
        Config.TIMEOUT = int(data.get('timeout', Config.TIMEOUT))
        
        return jsonify({'status': 'success', 'message': 'Configuration updated successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/status')
def get_status():
    """Get download status"""
    return jsonify(download_status)

@app.route('/api/start_download', methods=['POST'])
def start_download():
    """Start download process"""
    global download_status
    
    if download_status['is_running']:
        return jsonify({'status': 'error', 'message': 'Download is already running'}), 400
    
    try:
        # Start download in background thread
        thread = threading.Thread(target=download_worker)
        thread.daemon = True
        thread.start()
        
        return jsonify({'status': 'success', 'message': 'Download started'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stop_download', methods=['POST'])
def stop_download():
    """Stop download process"""
    global download_status
    
    if not download_status['is_running']:
        return jsonify({'status': 'error', 'message': 'No download is running'}), 400
    
    download_status['is_running'] = False
    download_status['status_message'] = 'Download stopped by user'
    
    return jsonify({'status': 'success', 'message': 'Download stopped'})

@app.route('/api/files')
def list_files():
    """List downloaded files"""
    try:
        files = []
        data_dir = Path(Config.BASE_DIR)
        
        if data_dir.exists():
            for file_path in data_dir.glob('*.zip'):
                stat = file_path.stat()
                files.append({
                    'name': file_path.name,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    'path': str(file_path)
                })
        
        # Sort by creation time (newest first)
        files.sort(key=lambda x: x['created'], reverse=True)
        
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    """Download a file"""
    try:
        file_path = Path(Config.BASE_DIR) / secure_filename(filename)
        
        if not file_path.exists():
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete a file"""
    try:
        file_path = Path(Config.BASE_DIR) / secure_filename(filename)
        
        if not file_path.exists():
            return jsonify({'status': 'error', 'message': 'File not found'}), 404
        
        file_path.unlink()
        return jsonify({'status': 'success', 'message': 'File deleted successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def download_worker():
    """Background worker for downloading data using enhanced processing"""
    global download_status
    
    try:
        # Initialize status
        download_status.update({
            'is_running': True,
            'progress': 0,
            'total_files': 0,
            'current_file': '',
            'status_message': 'Starting download...',
            'error': None,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'downloaded_files': [],
            'failed_files': []
        })
        
        # Parse date range
        start_date_obj = datetime.strptime(Config.DATE_START, '%Y-%m-%d')
        end_date_obj = datetime.strptime(Config.DATE_END, '%Y-%m-%d')
        
        logger.info(f"Starting HYCOM Data Download - Monthly Processing")
        logger.info(f"Date range: {Config.DATE_START} to {Config.DATE_END}")
        logger.info(f"Variables: {Config.VARIABLES}")
        logger.info(f"Geographic bounds: {Config.SOUTH_LAT}°N to {Config.NORTH_LAT}°N, {Config.WEST_LON}°E to {Config.EAST_LON}°E")
        
        # Calculate total files
        total_days = (end_date_obj - start_date_obj).days + 1
        total_files = total_days * len(Config.VARIABLES)
        download_status['total_files'] = total_files
        
        logger.info(f"Starting download: {total_files} files from {Config.DATE_START} to {Config.DATE_END}")
        
        # Process by month (following pure.py approach)
        current_date = start_date_obj
        downloaded_files = []
        failed_items = []
        
        while current_date <= end_date_obj and download_status['is_running']:
            # Calculate month boundaries (following pure.py logic)
            month_start = current_date
            # End of this calendar month
            if current_date.month == 12:
                month_end = datetime(current_date.year, 12, 31)
            else:
                month_end = datetime(current_date.year, current_date.month + 1, 1) - timedelta(days=1)
            # Cap by DATE_END
            month_end = min(month_end, end_date_obj)
            if month_end < month_start:
                break
            
            # Generate dates in month
            dates_in_month = []
            temp_date = month_start
            while temp_date <= month_end:
                dates_in_month.append(temp_date)
                temp_date += timedelta(days=1)
            
            total_files_month = len(dates_in_month) * len(Config.VARIABLES)
            
            logger.info(f"\nProcessing month: {month_start.strftime('%Y-%m')} (capped end: {month_end.strftime('%Y-%m-%d')})")
            download_status['status_message'] = f"Processing {month_start.strftime('%Y-%m')}..."
            
            downloaded_files_month = []
            failed_items_month = []
            
            # Download files for this month
            for date in dates_in_month:
                if not download_status['is_running']:
                    break
                    
                for var in Config.VARIABLES:
                    if not download_status['is_running']:
                        break
                    
                    filename = f"hycom_{var}_{date.strftime('%Y%m%d')}.nc"
                    download_status['current_file'] = filename
                    
                    file_path = download_file_with_retry(date, var)
                    if file_path:
                        downloaded_files_month.append(file_path)
                        downloaded_files.append(file_path)
                        download_status['downloaded_files'].append(filename)
                    else:
                        failed_items_month.append((date, var))
                        failed_items.append((date, var))
                        download_status['failed_files'].append(filename)
                    
                    # Update progress
                    download_status['progress'] += 1
                    progress_percent = (download_status['progress'] / total_files) * 100
                    download_status['status_message'] = f"Downloaded {download_status['progress']}/{total_files} files ({progress_percent:.1f}%)"
            
            # Try to redownload failed files
            if failed_items_month and download_status['is_running']:
                logger.warning(f"Initial failures: {len(failed_items_month)}. Attempting redownload pass...")
                download_status['status_message'] = f"Retrying failed downloads for {month_start.strftime('%Y-%m')}..."
                recovered, remaining = redownload_failed(failed_items_month, attempts=1)
                downloaded_files_month.extend(recovered)
                downloaded_files.extend(recovered)
                
                # Update status
                for path in recovered:
                    filename = path.name
                    if filename in download_status['failed_files']:
                        download_status['failed_files'].remove(filename)
                    download_status['downloaded_files'].append(filename)
                
                if remaining:
                    logger.warning(f"Still failed after redownload: {len(remaining)} items")
            
            logger.info(f"Downloaded {len(downloaded_files_month)}/{total_files_month} files for {month_start.strftime('%Y-%m')}")
            
            # Combine files for this month if we have any
            if downloaded_files_month and download_status['is_running']:
                try:
                    logger.info(f"Combining files for {month_start.strftime('%Y-%m')}...")
                    download_status['status_message'] = f"Combining files for {month_start.strftime('%Y-%m')}..."
                    
                    combined = combine_files(downloaded_files_month)
                    
                    # Create filename based on month (following pure.py approach)
                    timestamp = month_start.strftime('%Y%m')
                    nc_filename = f"HYCOM_combined_{timestamp}.nc"
                    zip_filename = f"HYCOM_data_{timestamp}.zip"
                    nc_path = Config.BASE_DIR / nc_filename
                    zip_path = Config.BASE_DIR / zip_filename
                    
                    # Encoding only for numeric variables (compression-ready)
                    encoding = {}
                    for name, da in combined.data_vars.items():
                        if da.dtype.kind in "ifub":
                            encoding[name] = {'zlib': True, 'complevel': 6}
                    
                    logger.info(f"Saving NetCDF file: {nc_filename}")
                    download_status['status_message'] = f"Creating {zip_filename}..."
                    
                    # Use enhanced write function with fallback
                    write_engine_used = write_netcdf_with_fallback(combined, nc_path, encoding)
                    
                    logger.info(f"Creating zip file: {zip_filename}")
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        zipf.write(nc_path, nc_filename)
                    
                    # Cleanup
                    try:
                        nc_path.unlink(missing_ok=True)  # keep only the zip
                    except Exception:
                        pass
                    combined.close()
                    
                    vars_list = list(combined.data_vars) if hasattr(combined, 'data_vars') else []
                    dims_dict = dict(combined.dims) if hasattr(combined, 'dims') else {}
                    
                    logger.info(f"Successfully created: {zip_filename}")
                    logger.info(f"Write engine: {write_engine_used}")
                    logger.info(f"Variables: {vars_list}")
                    if 'time' in dims_dict:
                        logger.info(f"Time steps: {dims_dict['time']}")
                    logger.info(f"Location: {zip_path}")
                    
                    download_status['status_message'] = f"Created {zip_filename} for {month_start.strftime('%Y-%m')}"
                    
                except Exception as e:
                    logger.error(f"Failed to process files for {month_start.strftime('%Y-%m')}: {e}")
                    download_status['error'] = f"Failed to combine files for {month_start.strftime('%Y-%m')}: {str(e)}"
            else:
                logger.warning(f"No files downloaded for {month_start.strftime('%Y-%m')}!")
            
            # Move to next month
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1)
        
        # Final status
        if download_status['is_running']:
            download_status.update({
                'is_running': False,
                'status_message': f'Download completed! Downloaded {len(downloaded_files)} files',
                'end_time': datetime.now().isoformat()
            })
        else:
            download_status.update({
                'status_message': 'Download stopped by user',
                'end_time': datetime.now().isoformat()
            })
        
        logger.info("Download process completed")
        
    except Exception as e:
        download_status.update({
            'is_running': False,
            'error': str(e),
            'status_message': f'Download failed: {str(e)}',
            'end_time': datetime.now().isoformat()
        })
        logger.error(f"Download worker error: {e}")
    finally:
        # Cleanup temporary directory
        temp_dir = Path(Config.TEMP_DIR)
        if temp_dir.exists():
            logger.info("Cleaning up temporary directory...")
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)