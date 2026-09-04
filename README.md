# Catat Keuangan Bot

Telegram bot sederhana untuk membantu mencatat dan memantau keuangan pribadi langsung melalui Telegram.

🔗 **Live Bot:** [@catatkeuangan_fakhru_bot di Telegram](https://t.me/catatkeuangan_fakhru_bot?utm_source=chatgpt.com)

## Fitur

* 💰 Mencatat pemasukan
* 💸 Mencatat pengeluaran
* 📊 Melihat saldo
* 📋 Melihat riwayat transaksi
* ✏️ Mengedit transaksi
* 🗑️ Menghapus transaksi
* 📅 Melihat statistik keuangan
* 📈 Melihat laporan bulanan
* 🔔 Pengingat untuk mencatat keuangan

## Teknologi

* **Python**
* **python-telegram-bot**
* **Supabase**
* **Telegram Bot API**

## Cara Kerja

```text
Telegram
   ↓
Telegram Bot
   ↓
Python
   ↓
Supabase
```

Setiap pengguna memiliki data transaksi masing-masing sehingga data pengguna tidak tercampur.

## Menjalankan Project

### 1. Clone repository

```bash
git clone https://github.com/fakhrurozyy/catatkeuangan-bot.git
cd catatkeuangan-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Buat file `.env`

Buat file `.env` di folder project dan isi dengan konfigurasi berikut:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
```

### 4. Jalankan bot

```bash
python bot.py
```

Bot akan mulai berjalan dan dapat digunakan melalui Telegram.

## Project Status

🚧 **Actively Developed**

Project ini masih dalam tahap pengembangan dan dapat dikembangkan lebih lanjut dengan fitur tambahan.

## Author

**Fakhru Rozy**

Informatics Graduate — Universitas Ahmad Dahlan

GitHub: [github.com/fakhrurozyy](https://github.com/fakhrurozyy?utm_source=chatgpt.com)
