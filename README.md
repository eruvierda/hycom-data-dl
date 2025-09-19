# HYCOM Ocean Data Downloader

A robust, high-performance downloader for HYCOM (Hybrid Coordinate Ocean Model) ocean data with both web interface and command-line capabilities. Built with Flask and enhanced with h5netcdf-first processing for optimal performance and reliability.

## ✨ Features

### 🚀 **Enhanced Performance & Reliability**
- ✅ **h5netcdf-first processing** - Optimized NetCDF handling with automatic fallbacks
- ✅ **Robust engine selection** - Tries h5netcdf → autodetect → scipy for maximum compatibility
- ✅ **Compressed NetCDF writing** - Automatic compression with h5netcdf, fallback to scipy
- ✅ **Cheap validation** - Fast file validation without full array reads
- ✅ **Month-end capping** - Respects date boundaries properly
- ✅ **Enhanced error handling** - Comprehensive retry mechanisms and cleanup

### 🌐 **Web Interface**
- ✅ **User-friendly Flask interface** - Modern, responsive web UI
- ✅ **Real-time monitoring** - Live progress tracking with detailed status
- ✅ **Configuration management** - Easy parameter adjustment through web forms
- ✅ **File management** - Download, view, and delete files through the interface
- ✅ **Keyboard shortcuts** - Power user features for efficiency

### 📊 **Data Processing**
- ✅ **Automatic file combination** - Merges NetCDF files by month with proper time handling
- ✅ **Smart retry mechanism** - Intelligent retry logic for failed downloads
- ✅ **Progress tracking** - Detailed progress bars and status updates
- ✅ **Comprehensive logging** - Full audit trail of all operations
- ✅ **Local storage** - No external dependencies, stores data locally

## 🛠️ Installation

### Prerequisites
- Python 3.7 or higher
- Internet connection for downloading HYCOM data

### Quick Setup
1. **Clone or download** this repository
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Dependencies
The application requires these Python packages:
- `flask` - Web framework
- `requests` - HTTP client for downloads
- `xarray` - NetCDF data handling
- `pandas` - Date/time processing
- `tqdm` - Progress bars
- `h5netcdf` - Optimized NetCDF engine (optional, with fallback)
- `netCDF4` - NetCDF support (fallback)

## ⚙️ Configuration

### Web Interface Configuration (Recommended)
Access the web interface at `http://localhost:5000` and configure:
- **Geographic bounds** (longitude/latitude)
- **Date range** for data download
- **Variables** to download (water_u, water_v, etc.)
- **Download settings** (retry count, timeout)

### Programmatic Configuration
Edit the `Config` class in `oceanos_hycom_download.py`:

```python
class Config:
    # Geographic bounds (Indonesian waters example)
    WEST_LON = 116.5    # Western longitude
    EAST_LON = 119.0    # Eastern longitude  
    SOUTH_LAT = -2.0    # Southern latitude
    NORTH_LAT = 0.5     # Northern latitude
    
    # Date range
    DATE_START = '2022-12-01'
    DATE_END = '2022-12-31'
    
    # Variables to download
    VARIABLES = ['water_u', 'water_v']
    
    # Download settings
    MAX_RETRIES = 3     # Maximum retry attempts
    TIMEOUT = 60        # Request timeout in seconds
    CHUNK_SIZE = 8192   # Download chunk size
```

## 🚀 Usage

### Web Interface (Recommended)

1. **Start the application**:
   ```bash
   python run_app.py
   ```
   Or use the Windows batch file:
   ```bash
   start_web_interface.bat
   ```

2. **Open your browser** and navigate to: `http://localhost:5000`

3. **Configure your download**:
   - Set geographic bounds for your area of interest
   - Choose date range for data download
   - Select ocean variables (water_u, water_v, etc.)
   - Adjust download settings as needed

4. **Start downloading**:
   - Click "Start Download" to begin
   - Monitor real-time progress
   - Use "Stop Download" if needed

5. **Manage files**:
   - View downloaded files in the Files panel
   - Download files to your local machine
   - Delete files you no longer need

### Command Line Interface

Run the downloader directly:
```bash
python oceanos_hycom_download.py
```

This will use the configuration in the `Config` class and process data month by month.

### Web Interface Features

#### 🎛️ **Configuration Panel**
- Interactive form for all download parameters
- Real-time validation of input values
- Save/load configuration presets

#### 📊 **Real-time Monitoring**
- Live progress bar with percentage completion
- Current file being downloaded
- Download speed and ETA
- Success/failure counts

#### 🎮 **Download Control**
- Start/stop downloads with confirmation
- Pause and resume functionality
- Emergency stop with cleanup

#### 📁 **File Management**
- Browse all downloaded files
- View file details (size, date, variables)
- Download files to local machine
- Delete unwanted files
- Sort by date, size, or name

#### ⌨️ **Keyboard Shortcuts**
- `Ctrl+S` - Save configuration
- `Ctrl+D` - Start download
- `Ctrl+Shift+D` - Stop download
- `Ctrl+F` - Show files panel
- `Ctrl+R` - Refresh status

## 📁 Output Files

### File Naming Convention
Files are saved in `./hycom_data/` with the format:
```
HYCOM_data_[YYYYMM].zip
```

Where:
- `YYYYMM` - Year and month of the data (e.g., 202212 for December 2022)

### File Contents
Each ZIP file contains:
- `HYCOM_combined_[YYYYMM].nc` - Combined NetCDF file with all variables and time steps
- Compressed using ZIP_DEFLATED for efficient storage

### Data Structure
The NetCDF files contain:
- **Variables**: Ocean current components (water_u, water_v)
- **Coordinates**: Longitude, latitude, time, depth
- **Attributes**: Creation timestamp, source information, variable list
- **Compression**: Automatic compression for efficient storage

## 🏗️ Project Structure

```
hycom-data-dl/
├── app.py                    # Flask web application
├── run_app.py               # Application launcher
├── oceanos_hycom_download.py # Core downloader (CLI + API)
├── start_web_interface.bat  # Windows launcher
├── requirements.txt          # Python dependencies
├── README.md                # This documentation
├── LICENSE                  # License information
├── templates/               # HTML templates
│   ├── base.html           # Base template with navigation
│   └── index.html          # Main application page
├── static/                 # Static web assets
│   ├── css/
│   │   └── style.css       # Custom styling
│   └── js/
│       └── app.js          # Frontend JavaScript
├── hycom_data/             # Output directory (auto-created)
├── temp_download/          # Temporary files (auto-created)
└── hycom_download.log      # Application logs (auto-created)
```

## 🔧 Technical Details

### Enhanced Processing Pipeline
1. **URL Generation** - Creates optimized HYCOM NCSS URLs with NetCDF4 format
2. **Download with Retry** - Robust download with exponential backoff
3. **Validation** - Fast validation using safe engine selection
4. **File Combination** - Intelligent merging by variable and time
5. **Compression** - Automatic compression with fallback options
6. **Cleanup** - Proper resource cleanup and temporary file removal

### Engine Selection Strategy
The application uses a smart engine selection strategy:
1. **h5netcdf** - Preferred for performance and compression
2. **autodetect** - Fallback for compatibility
3. **scipy** - Final fallback for maximum compatibility

### Error Handling
- **Network errors** - Automatic retry with exponential backoff
- **File corruption** - Validation and re-download
- **Memory issues** - Proper resource cleanup
- **Disk space** - Temporary file management

## 🐛 Troubleshooting

### Common Issues

#### "No module named 'xarray'"
```bash
pip install xarray netCDF4 pandas requests flask tqdm
```

#### "Permission denied" errors
- Ensure the application has write permissions in the current directory
- Run as administrator if necessary (Windows)

#### Slow downloads
- Check your internet connection
- Reduce `TIMEOUT` if connection is stable
- Verify HYCOM server status
- Consider downloading smaller date ranges

#### Memory issues
- The application automatically manages memory
- Temporary files are cleaned up after processing
- Use smaller date ranges for very large datasets

#### Port 5000 already in use
```bash
# Kill existing processes
netstat -ano | findstr :5000
taskkill /F /PID <PID_NUMBER>
```

### Performance Optimization

#### For Large Datasets
- Download data in smaller monthly chunks
- Use SSD storage for better I/O performance
- Ensure sufficient RAM (8GB+ recommended)

#### For Slow Connections
- Increase `TIMEOUT` value
- Reduce `CHUNK_SIZE` for more stable downloads
- Use retry mechanism (already enabled)

## 📈 Recent Improvements

### Version 2.0 Enhancements
1. **h5netcdf Integration** - Optimized NetCDF processing with automatic fallbacks
2. **Enhanced Error Handling** - Comprehensive retry mechanisms and cleanup
3. **Improved Validation** - Fast file validation without full array reads
4. **Better Compression** - Automatic compression with multiple engine support
5. **Cleaner Codebase** - Removed obsolete test files and improved structure
6. **Enhanced Documentation** - Comprehensive README with troubleshooting guide

### Performance Improvements
- **Faster file processing** with h5netcdf engine
- **Better memory management** with proper resource cleanup
- **Improved reliability** with robust error handling
- **Enhanced user experience** with better progress tracking

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## 📞 Support

For support and questions:
1. Check the troubleshooting section above
2. Review the application logs in `hycom_download.log`
3. Open an issue on the project repository

---

**Happy downloading! 🌊**