# Legacy Django reference

Folder ini adalah proyek Django yang sebelumnya tercampur di dalam
`app/features/forecast/pipeline/src/`. Tidak ada kode di `app/` (FastAPI)
yang memanggil apa pun dari sini — sudah dicek dengan grep sebelum dipindah.

Kalau memang tidak dipakai lagi, folder ini aman untuk dihapus sepenuhnya.
Kalau ada logic yang masih relevan (misal forecast_generation.py), ekstrak
bagian yang dibutuhkan ke ml/forecast/training/ lalu hapus sisanya.
