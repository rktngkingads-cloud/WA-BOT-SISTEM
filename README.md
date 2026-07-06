# WA Contact & Message Monitor

Layanan Python untuk kontak opt-in, auto-reply webhook resmi, antrean pesan satu-per-satu, input daftar kontak melalui CSV, countdown CMD, SQLite, dan mode simulasi tanpa token Meta.

## Fitur utama

- Input nama kontak dan nomor dari monitor CMD
- Input beberapa kontak melalui `batch_contacts.csv`
- Setiap kontak dibuat sebagai chat individual dengan jadwal berbeda
- Pesan umum dapat digunakan untuk seluruh daftar, atau diubah per baris CSV
- Registry opt-in dan opt-out dengan sumber persetujuan
- Kolom countdown nomor yang sedang menunggu pengiriman
- Satu antrean aktif per kontak
- Delay awal, jarak antar-kontak, batas daftar, dan batas harian
- Monitor aktivitas queue serta pesan masuk/keluar
- Mode `offline` untuk pengujian tanpa pengiriman nyata
- Mode `meta` untuk Cloud API resmi
- Pengiriman queue nyata dinonaktifkan secara terpisah secara default
- Penyimpanan SQLite dan deduplikasi webhook
- Tidak ada pesan grup dan tidak ada pelacakan status online pengguna

## Quick start Windows

```bat
setup_windows.bat
run_wa_bot.bat
```

Untuk memasukkan daftar kontak sekaligus:

```bat
run_contact_queue.bat
```

Salin `batch_contacts.example.csv` menjadi `batch_contacts.csv`, lalu isi kolom:

```text
contact_name,phone,message,consent,consent_source,consent_note
```

Kolom `message` boleh kosong ketika pesan umum dimasukkan melalui CMD. Kontak baru hanya diterima apabila `consent=yes` dan `consent_source` diisi.

Lihat `README_CMD_WINDOWS.md` untuk tombol dan konfigurasi lengkap.

## Menjalankan manual

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
copy .env.example .env
.venv/Scripts/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Terminal kedua:

```bash
.venv/Scripts/python wa_monitor.py
```

Validasi daftar tanpa menambahkan antrean:

```bash
.venv/Scripts/python batch_queue.py --file batch_contacts.csv --dry-run
```

## Testing

```bash
python -m pytest -q
python windows_system_check.py
```

## Keamanan

Jangan commit `.env`, token, secret, database kontak, atau daftar customer asli. Queue hanya menerima kontak yang sudah opt-in atau baris CSV yang menyertakan catatan persetujuan. Mode offline adalah mode aman untuk demonstrasi dan pengujian lokal.
