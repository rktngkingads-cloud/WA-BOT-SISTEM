# WA BOT SISTEM

Repositori khusus untuk layanan Python berbasis webhook resmi WhatsApp Cloud API.

## Batas sistem

Sistem hanya menggunakan data webhook, delivery receipt, database lokal, dan metadata nomor bisnis yang dikonfigurasi. Sistem tidak dapat menentukan apakah nomor pengguna sedang online, memindai nomor acak, menjamin nomor tidak diblokir, atau menghindari pembatasan platform.

Status kontak pada CMD berarti:

- `opted_in`: persetujuan tersimpan di database
- `has_incoming_messages`: pernah ada pesan masuk yang diterima webhook
- `sent`, `delivered`, `read`, `failed`: status pesan dari webhook
- `api_reachable`: credential dan resource nomor bisnis yang dikonfigurasi dapat diakses

## Fitur

- webhook pesan masuk dan validasi signature
- cooldown/debounce per penerima 16–20 detik
- pesan baru menggantikan balasan yang masih menunggu
- allowlist nomor opt-in/test
- respons otomatis dari `response_data.json`
- deduplikasi ID pesan
- SQLite untuk kontak, pesan, dan status delivery
- input kontak opt-in dari CMD
- laporan aktivitas database per kontak
- ringkasan dan pencarian status pesan
- pemeriksaan metadata nomor bisnis yang dikonfigurasi
- Docker, unit test, dan GitHub Actions

## Instalasi Windows CMD

Clone atau download repo, buka CMD pada folder repo, lalu jalankan:

```bat
setup.cmd
```

Perintah tersebut membuat `.venv`, memasang dependency, membuat `.env`, menginisialisasi database, mengompilasi Python, dan menjalankan test.

Edit `.env` dan isi credential resmi:

```env
WA_GRAPH_API_VERSION=
WA_PHONE_NUMBER_ID=
WA_ACCESS_TOKEN=
WA_APP_SECRET=
WA_VERIFY_TOKEN=
WA_ADMIN_API_KEY=
WA_ALLOWED_RECIPIENTS=60123456789
```

Jalankan server:

```bat
start.cmd
```

Server tersedia pada port `8000`.

## Input nomor manual

Nomor wajib memakai kode negara tanpa tanda `+`, spasi, atau tanda hubung.

Tambahkan kontak yang sudah memberikan opt-in:

```bat
.venv\Scripts\python admin_contacts.py add --phone 60123456789 --source "website-form" --note "Consent recorded"
```

Lihat kontak dan aktivitas pesan yang tersimpan:

```bat
.venv\Scripts\python admin_contacts.py show --phone 60123456789
```

Hasil menampilkan jumlah pesan masuk/keluar, pesan terakhir, dan `has_incoming_messages`. Nilai ini berasal dari database lokal, bukan status online WhatsApp.

Daftar kontak:

```bat
.venv\Scripts\python admin_contacts.py list --limit 100
```

Catat opt-out:

```bat
.venv\Scripts\python admin_contacts.py opt-out --phone 60123456789
```

## Status pesan

Ringkasan seluruh status:

```bat
.venv\Scripts\python admin_messages.py summary
```

Daftar pesan terbaru:

```bat
.venv\Scripts\python admin_messages.py list --limit 100
```

Cari satu pesan berdasarkan ID:

```bat
.venv\Scripts\python admin_messages.py show --message-id wamid.EXAMPLE
```

Status yang disimpan meliputi `received`, `accepted`, `sent`, `delivered`, `read`, dan `failed`. Untuk status `failed`, periksa field `error`.

## Pemeriksaan nomor bisnis

Jalankan:

```bat
.venv\Scripts\python business_check.py
```

Perintah ini memeriksa resource `WA_PHONE_NUMBER_ID` milik bisnis Anda dan menampilkan:

- konfigurasi credential tersedia atau tidak
- API dapat dijangkau atau tidak
- HTTP error bila akses ditolak
- metadata seperti display number, verified name, dan quality rating bila tersedia

Perintah ini tidak memeriksa status aktif/online nomor penerima dan tidak dapat memastikan alasan pembatasan akun di luar respons API.

## Data respons otomatis

Respons berada di:

```text
response_data.json
```

Lihat semua rule:

```bat
.venv\Scripts\python admin_responses.py --list
```

Preview respons untuk contoh pesan masuk:

```bat
.venv\Scripts\python admin_responses.py --message "halo"
```

Format data:

```json
{
  "default": "Balasan otomatis: Terima kasih, pesan Anda sudah diterima.",
  "rules": [
    {
      "keywords": ["halo", "hai"],
      "response": "Balasan otomatis: Halo, terima kasih sudah menghubungi kami."
    }
  ]
}
```

Pesan yang tidak cocok dengan rule menggunakan `default`.

## Endpoint

- `GET /health` — kesehatan layanan dan ringkasan status
- `GET /webhook` — verifikasi webhook
- `POST /webhook` — menerima pesan dan delivery update
- `GET /messages?limit=100` — log pesan dengan header `X-Admin-Key`

## Cooldown

```env
WA_COOLDOWN_MIN_SECONDS=16
WA_COOLDOWN_MAX_SECONDS=20
```

Cooldown mencegah beberapa balasan terkirim bersamaan. Ini bukan alat untuk menyamarkan otomatisasi sebagai manusia.

## Docker

```bash
docker build -t wa-bot-system .
docker run --env-file .env -p 8000:8000 wa-bot-system
```

## Pengujian

```bat
.venv\Scripts\python -m compileall -q .
.venv\Scripts\python -m pytest -q
```

## Keamanan

Jangan commit `.env`, token, app secret, verify token, atau admin key. Gunakan nomor yang telah memberikan izin dan patuhi kebijakan WhatsApp Business Platform.
