# Menjalankan WA BOT SISTEM di Windows CMD

## 1. Setup pertama kali

Buka CMD pada folder repository:

```bat
setup.cmd
```

Setup akan:

- membuat `.venv`
- memasang dependency
- membuat `.env` dari `.env.example`
- menginisialisasi SQLite
- mengompilasi source code
- menjalankan unit test

## 2. Isi konfigurasi `.env`

```env
WA_GRAPH_API_VERSION=
WA_PHONE_NUMBER_ID=
WA_ACCESS_TOKEN=
WA_APP_SECRET=
WA_VERIFY_TOKEN=
WA_ADMIN_API_KEY=
WA_ALLOWED_RECIPIENTS=60123456789
WA_DB_PATH=data/wa-system.db
WA_RESPONSE_DATA_PATH=response_data.json
WA_COOLDOWN_MIN_SECONDS=16
WA_COOLDOWN_MAX_SECONDS=20
```

`WA_ALLOWED_RECIPIENTS` berisi nomor opt-in/test yang diizinkan menerima balasan. Gunakan format kode negara tanpa `+`, spasi, atau tanda hubung. Beberapa nomor dipisahkan koma.

## 3. Input kontak ke database

```bat
.venv\Scripts\python.exe admin_contacts.py add --phone 60123456789 --source "website-form" --note "Consent recorded"
```

Untuk versi saat ini, nomor yang akan menerima balasan harus:

1. tersimpan sebagai opt-in melalui `admin_contacts.py`; dan
2. tercantum dalam `WA_ALLOWED_RECIPIENTS` di `.env`.

Input database tidak mengirim pesan secara otomatis.

## 4. Jalankan server lokal

```bat
start.cmd
```

`start.cmd` menggunakan `.venv` dan memuat `.env` secara otomatis. Server berjalan pada:

```text
http://127.0.0.1:8000
```

Health check:

```text
http://127.0.0.1:8000/health
```

## 5. Hubungkan webhook

WhatsApp Cloud API tidak dapat memanggil `localhost` secara langsung. Gunakan tunnel HTTPS publik menuju port `8000`, kemudian atur callback Meta ke:

```text
https://DOMAIN-PUBLIK/webhook
```

Verify token harus sama dengan `WA_VERIFY_TOKEN`.

## 6. Perintah administrasi pada CMD kedua

Lihat kontak dan aktivitas database:

```bat
.venv\Scripts\python.exe admin_contacts.py show --phone 60123456789
```

Daftar kontak:

```bat
.venv\Scripts\python.exe admin_contacts.py list --limit 100
```

Catat opt-out:

```bat
.venv\Scripts\python.exe admin_contacts.py opt-out --phone 60123456789
```

Ringkasan status pesan:

```bat
.venv\Scripts\python.exe admin_messages.py summary
```

Daftar pesan:

```bat
.venv\Scripts\python.exe admin_messages.py list --limit 100
```

Cari Message ID:

```bat
.venv\Scripts\python.exe admin_messages.py show --message-id wamid.EXAMPLE
```

Lihat data respons:

```bat
.venv\Scripts\python.exe admin_responses.py --list
```

Preview respons:

```bat
.venv\Scripts\python.exe admin_responses.py --message "halo"
```

Periksa resource nomor bisnis yang dikonfigurasi:

```bat
.venv\Scripts\python.exe business_check.py
```

## Arti status

- `received`: pesan masuk tersimpan
- `accepted`: API menerima permintaan pengiriman
- `sent`: pesan dikirim oleh WhatsApp
- `delivered`: pesan diterima perangkat tujuan
- `read`: read receipt tersedia
- `failed`: pengiriman gagal; lihat field `error`
- `has_incoming_messages`: kontak pernah mengirim pesan yang diterima webhook lokal
- `api_reachable`: resource nomor bisnis dapat diakses dengan credential saat ini

Sistem tidak dapat menentukan status online/aktif pengguna dan tidak dapat menjamin apakah akun sedang atau akan dibatasi platform.
