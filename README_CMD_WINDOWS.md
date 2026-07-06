# WA Contact & Message Monitor — Windows CMD

Sistem menyediakan kolom kontak, input nomor tujuan, antrean chat individual, countdown pengiriman, dan log aktivitas pesan. Daftar kontak dapat dimasukkan sekaligus melalui CSV, tetapi setiap nomor tetap diproses sebagai chat satu-per-satu dengan jeda.

## Menjalankan

1. Ekstrak ZIP.
2. Buka folder hasil ekstrak.
3. Jalankan sekali:

```bat
setup_windows.bat
```

4. Jalankan service dan monitor:

```bat
run_wa_bot.bat
```

Mode bawaan adalah `WA_MODE=offline`. Pesan hanya disimulasikan dan tidak dikirim ke WhatsApp nyata.

## Input satu kontak

Tombol monitor:

- `A` — tambah kontak dan nomor opt-in
- `E` — ubah nama pada kolom Contact
- `M` — antrekan satu pesan ke satu kontak
- `C` — batalkan pesan yang masih menunggu
- `O` — opt-out kontak dan batalkan antreannya
- `R` — refresh
- `Q` — keluar

## Input daftar kontak sekaligus

Jalankan:

```bat
run_contact_queue.bat
```

Pada pemakaian pertama, script membuat `batch_contacts.csv` dari contoh. Isi datanya menggunakan format:

```csv
contact_name,phone,message,consent,consent_source,consent_note
Customer A,60123456789,,yes,crm-opt-in,Persetujuan tercatat
Customer B,60198765432,,yes,form-opt-in,Persetujuan tercatat
```

Cara kerja:

1. Isi semua nama dan nomor tujuan di `batch_contacts.csv`.
2. Jalankan `run_contact_queue.bat`.
3. Masukkan satu pesan umum melalui CMD. Kolom `message` pada CSV dapat dipakai untuk pesan khusus per kontak.
4. Sistem menampilkan preview, jumlah kontak valid, baris yang ditolak, waktu tunggu, dan estimasi durasi.
5. Ketik `QUEUE` untuk memasukkan semua chat individual ke antrean.
6. Jalankan atau buka `run_wa_bot.bat` untuk melihat countdown setiap nomor.

Setiap nomor memiliki item queue sendiri. Sistem tidak membuat grup dan tidak mengirim semua nomor pada detik yang sama.

## Kolom monitor

- **Contact** — nama tujuan
- **Phone** — nomor internasional, contoh `60123456789`
- **State** — `READY`, `LIMIT`, `OPT-OUT`, atau `ALLOWLIST`
- **Today** — total pesan hari ini dibanding batas harian
- **Next** — `WAIT 00:30`, `DUE`, `SENDING`, `PAUSED`, atau `READY`
- **Last** — waktu aktivitas pesan terakhir

Panel kanan menampilkan perubahan queue dan aktivitas pesan masuk/keluar.

## Pembatasan anti-spam

- Kontak wajib sudah opt-in atau memiliki `consent=yes` dan `consent_source` pada CSV.
- Hanya satu pesan yang boleh menunggu untuk setiap kontak.
- Nomor duplikat dalam satu file ditolak.
- Daftar dibatasi maksimal 50 kontak secara bawaan.
- Delay awal bawaan 30 detik.
- Jarak antar-kontak bawaan 20 detik.
- Delay minimum sistem 15 detik.
- Batas bawaan 6 pesan per kontak per hari.
- Opt-out otomatis membatalkan pesan yang masih menunggu.
- Pengiriman nyata pada mode Meta tetap mati sampai `WA_QUEUE_REAL_SEND_ENABLED=true` diaktifkan secara eksplisit.

Pengaturan dapat diubah di `.env`:

```env
WA_QUEUE_DEFAULT_DELAY_SECONDS=30
WA_QUEUE_MIN_DELAY_SECONDS=15
WA_QUEUE_GLOBAL_GAP_SECONDS=15
WA_BATCH_MAX_CONTACTS=50
WA_BATCH_INITIAL_DELAY_SECONDS=30
WA_BATCH_GAP_SECONDS=20
WA_MAX_REPLIES_PER_CONTACT_PER_DAY=6
```

Validasi tanpa memasukkan antrean:

```bat
.venv\Scripts\python.exe batch_queue.py --file batch_contacts.csv --dry-run
```

## Mode Meta resmi

Untuk pengiriman nyata, ubah:

```env
WA_MODE=meta
```

Kemudian lengkapi kredensial Meta resmi. Antrean pengiriman nyata tetap berhenti sampai:

```env
WA_QUEUE_REAL_SEND_ENABLED=true
```

Gunakan hanya untuk kontak yang sudah memberikan persetujuan dan percakapan yang sesuai dengan ketentuan WhatsApp Business Platform.

## Endpoint lokal

```text
http://127.0.0.1:8000/health
```

Endpoint `/messages` dan `/queue` membutuhkan header `X-Admin-Key` dan nilai `WA_ADMIN_API_KEY`.

Monitor tidak membaca atau menebak status online pengguna WhatsApp. Semua status berasal dari database lokal dan status delivery resmi yang diterima sistem.
