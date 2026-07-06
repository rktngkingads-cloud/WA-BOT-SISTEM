# WA Contact & Message Monitor — Windows CMD

Sistem ini menyediakan kolom kontak, input nomor tujuan, antrean satu pesan per kontak, countdown pengiriman, dan log aktivitas pesan. Tidak ada perintah broadcast atau import massal.

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

## Tombol monitor

- `A` — tambah kontak dan nomor opt-in
- `E` — ubah nama pada kolom Contact
- `M` — antrekan satu pesan ke satu kontak
- `C` — batalkan pesan yang masih menunggu
- `O` — opt-out kontak dan batalkan antreannya
- `R` — refresh
- `Q` — keluar

## Kolom monitor

- **Contact** — nama tujuan yang diisi saat menambah kontak
- **Phone** — nomor internasional, contoh `60123456789`
- **State** — `READY`, `LIMIT`, `OPT-OUT`, atau `ALLOWLIST`
- **Today** — total pesan hari ini dibanding batas harian
- **Next** — `WAIT 00:30`, `DUE`, `SENDING`, `PAUSED`, atau `READY`
- **Last** — waktu aktivitas pesan terakhir

Panel kanan menampilkan perubahan queue dan aktivitas pesan masuk/keluar.

## Proteksi anti-spam

- Kontak antrean wajib tercatat `opted_in=1` di database.
- Hanya satu pesan yang boleh menunggu untuk setiap kontak.
- Tidak tersedia perintah broadcast atau queue semua kontak.
- Delay minimum bawaan 15 detik.
- Jarak global antar-pengiriman bawaan 15 detik.
- Batas bawaan 6 pesan per kontak per hari.
- Opt-out otomatis membatalkan pesan yang masih menunggu.
- Pengiriman queue nyata pada mode Meta tetap mati sampai `WA_QUEUE_REAL_SEND_ENABLED=true` diaktifkan secara eksplisit.

Pengaturan dapat diubah di `.env`:

```env
WA_QUEUE_DEFAULT_DELAY_SECONDS=30
WA_QUEUE_MIN_DELAY_SECONDS=15
WA_QUEUE_GLOBAL_GAP_SECONDS=15
WA_MAX_REPLIES_PER_CONTACT_PER_DAY=6
```

## Mode Meta resmi

Untuk pengiriman nyata, ubah:

```env
WA_MODE=meta
```

Kemudian lengkapi kredensial Meta resmi. Antrean pengiriman nyata masih tetap berhenti sampai:

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
