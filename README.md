# WA BOT SISTEM

Repositori khusus untuk layanan Python berbasis webhook resmi WhatsApp Cloud API. Sistem sebelumnya telah dipindahkan dari proyek `landing-page` ke repositori ini.

## Ruang lingkup

Sistem ini ditujukan untuk percakapan bisnis yang sah dengan kontak yang sudah memberikan persetujuan. Sistem tidak menyediakan broadcast massal, percakapan palsu, pemeriksaan status online pengguna, atau pengiriman proaktif ke daftar nomor.

## Fitur

- menerima webhook pesan masuk
- validasi signature `X-Hub-Signature-256`
- hanya membalas nomor opt-in/test yang diizinkan
- registry kontak manual dengan sumber dan waktu persetujuan
- pencatatan opt-out
- data respons disimpan terpisah dalam `response_data.json`
- deduplikasi berdasarkan ID pesan masuk
- debounce/cooldown per nomor antara 16–20 detik
- pesan baru dari nomor yang sama menggantikan balasan yang masih menunggu
- penyimpanan pesan dan status ke SQLite
- status resmi `accepted`, `sent`, `delivered`, `read`, dan `failed`
- endpoint log dilindungi `WA_ADMIN_API_KEY`
- struktur counter untuk batas balasan harian per kontak

Cooldown digunakan untuk mencegah burst dan balasan bertumpuk. Balasan default diberi label sebagai balasan otomatis.

## Kontak manual

Nomor manual hanya boleh dimasukkan setelah ada bukti persetujuan. Registry menyimpan nomor internasional, status opt-in, sumber persetujuan, catatan, waktu persetujuan, dan waktu opt-out.

Menambahkan kontak ke database tidak mengirim pesan secara otomatis. Pengiriman tetap hanya boleh terjadi sebagai respons terhadap pesan masuk yang sah.

## Menjalankan lokal

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --host 0.0.0.0 --port 8000
```

Pada Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## Endpoint

- `GET /health` — kesehatan layanan dan ringkasan status
- `GET /webhook` — verifikasi webhook Meta
- `POST /webhook` — menerima pesan dan status delivery
- `GET /messages?limit=100` — log pesan; wajib header `X-Admin-Key`

## Cooldown

```env
WA_COOLDOWN_MIN_SECONDS=16
WA_COOLDOWN_MAX_SECONDS=20
WA_MAX_REPLIES_PER_CONTACT_PER_DAY=6
```

Untuk satu nomor, hanya satu balasan tertunda yang disimpan. Ketika pesan baru masuk sebelum timer selesai, balasan lama dibatalkan dan diganti dengan balasan terbaru.

## Docker

```bash
docker build -t wa-bot-system .
docker run --env-file .env -p 8000:8000 wa-bot-system
```

## Pengujian

```bash
python -m pytest -q
```

## Keamanan

Jangan commit `WA_ACCESS_TOKEN`, `WA_APP_SECRET`, `WA_VERIFY_TOKEN`, atau `WA_ADMIN_API_KEY`. Gunakan nomor yang memiliki izin/opt-in dan patuhi kebijakan WhatsApp Business Platform.
