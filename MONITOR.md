# WA BOT Local Monitor

Dashboard CMD read-only tersedia melalui:

```bat
monitor.cmd
```

## Cara menjalankan

### CMD pertama — server

```bat
start.cmd
```

Server berjalan di:

```text
http://127.0.0.1:8000
```

### CMD kedua — monitor

```bat
monitor.cmd
```

Monitor akan refresh setiap 2 detik dan menampilkan:

- respons endpoint `/health`
- daftar maksimal 19 kontak dari SQLite
- ringkasan status pesan
- 12 aktivitas pesan terbaru
- status seperti `received`, `accepted`, `sent`, `delivered`, `read`, dan `failed`

Tekan `Ctrl+C` untuk menutup monitor.

## Tampilan

Bagian utama:

```text
WA BOT LOCAL MONITOR

[SESSION]
Status server dan ringkasan health

[CONTACTS]
Kontak opt-in/opt-out dari database

[MESSAGE STATUS]
Jumlah status pesan

[RECENT ACTIVITY]
Pesan masuk, pesan keluar, dan delivery update terbaru
```

Monitor hanya membaca database lokal dan health endpoint. Tidak ada perintah pengiriman, rotasi akun, group farming, atau pemeriksaan status online pengguna.
