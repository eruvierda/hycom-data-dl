# HYCOM Ocean Data Downloader

Downloader untuk data model osean HYCOM (Hybrid Coordinate Ocean Model) yang menyimpan data ke storage lokal.

## Fitur

- ✅ Download data HYCOM dengan retry mechanism
- ✅ Progress bar untuk monitoring download
- ✅ Logging yang komprehensif
- ✅ Validasi file yang didownload
- ✅ Kombinasi file NetCDF per bulan
- ✅ Kompresi data untuk menghemat ruang
- ✅ Error handling yang robust
- ✅ Storage lokal (tidak memerlukan Google Drive)

## Instalasi

1. Clone atau download repository ini
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Konfigurasi

Edit konfigurasi di dalam file `oceanos_hycom_download.py` pada class `Config`:

```python
class Config:
    # Batas geografis
    WEST_LON = 116.5    # Bujur barat
    EAST_LON = 119      # Bujur timur  
    SOUTH_LAT = -2      # Lintang selatan
    NORTH_LAT = 0.5     # Lintang utara
    
    # Rentang tanggal
    DATE_START = '2022-01-01'
    DATE_END = '2022-12-31'
    
    # Variabel yang akan didownload
    VARIABLES = ['water_u', 'water_v']
    
    # Pengaturan download
    MAX_RETRIES = 3     # Maksimal percobaan download
    TIMEOUT = 60        # Timeout dalam detik
```

## Penggunaan

Jalankan script:

```bash
python oceanos_hycom_download.py
```

## Output

Data akan disimpan di folder `./hycom_data/` dengan format:
- `HYCOM_data_YYYYMM.zip` - File zip berisi data NetCDF untuk setiap bulan

## Log

Log akan disimpan di file `hycom_download.log` dan juga ditampilkan di console.

## Struktur File

```
hycom-data-dl/
├── oceanos_hycom_download.py  # Script utama
├── requirements.txt           # Dependencies
├── README.md                 # Dokumentasi
├── hycom_data/               # Output data (dibuat otomatis)
├── temp_download/            # Folder sementara (dibuat otomatis)
└── hycom_download.log        # Log file (dibuat otomatis)
```

## Perbaikan yang Dilakukan

1. **Menghapus dependencies Google Colab** - Script sekarang bisa berjalan di environment lokal
2. **Menggunakan storage lokal** - Data disimpan di folder lokal, bukan Google Drive
3. **Menambahkan retry mechanism** - Download akan dicoba ulang jika gagal
4. **Progress bar** - Monitoring progress download dengan tqdm
5. **Logging yang proper** - Log ke file dan console
6. **Error handling yang robust** - Penanganan error yang lebih baik
7. **Validasi file** - Memastikan file yang didownload valid
8. **Kompresi data** - Menghemat ruang penyimpanan
9. **Type hints** - Kode yang lebih mudah dibaca dan di-maintain
10. **Konfigurasi yang fleksibel** - Mudah mengubah parameter

## Troubleshooting

### Error: "No module named 'xarray'"
```bash
pip install xarray netCDF4
```

### Error: "Permission denied"
Pastikan script memiliki permission untuk menulis di direktori saat ini.

### Download lambat
- Periksa koneksi internet
- Kurangi `TIMEOUT` jika koneksi stabil
- Periksa server HYCOM status

## Lisensi

Lihat file LICENSE untuk detail lisensi.
