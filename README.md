# WA Contact & Message Monitor

Layanan Python untuk kontak opt-in, auto-reply webhook resmi, antrean pesan manual satu-per-satu, countdown CMD, SQLite, dan mode simulasi tanpa token Meta.

## Fitur utama

- Input nama kontak dan nomor dari monitor CMD
- Registry opt-in dan opt-out dengan sumber persetujuan
- Kolom countdown nomor yang sedang menunggu pengiriman
- Satu antrean aktif per kontak
- Delay minimum, jarak global, dan batas harian
- Monitor aktivitas queue serta pesan masuk/keluar
- Mode `offline` untuk pengujian tanpa pengiriman nyata
- Mode `meta` untuk Cloud API resmi
- Pengiriman queue nyata dinonaktifkan secara terpisah secara default
- Penyimpanan SQLite dan deduplikasi webhook
- Tidak ada broadcast massal atau pelacakan status online pengguna

## Quick start Windows

```bat
setup_windows.bat
run_wa_bot.bat
```

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

## Testing

```bash
python -m pytest -q
```

## Keamanan

Jangan commit `.env`, token, secret, atau database kontak. Queue hanya menerima kontak yang tercatat opt-in. Mode offline adalah mode aman untuk demonstrasi dan pengujian lokal.
