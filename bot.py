import os
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from supabase import create_client, Client

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)


# ============================================================
# KONFIGURASI
# ============================================================

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

TIMEZONE = ZoneInfo("Asia/Jakarta")

REMINDER_HOUR = 21
REMINDER_MINUTE = 0


# ============================================================
# VALIDASI KONFIGURASI
# ============================================================

if not TOKEN:
    raise ValueError(
        "TELEGRAM_BOT_TOKEN tidak ditemukan di .env"
    )

if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL tidak ditemukan di .env"
    )

if not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError(
        "SUPABASE_SERVICE_ROLE_KEY tidak ditemukan di .env"
    )


# ============================================================
# SUPABASE
# ============================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
)


# ============================================================
# CONVERSATION STATES
# ============================================================

(
    JUMLAH_PENGELUARAN,
    KATEGORI_PENGELUARAN,
    KETERANGAN_PENGELUARAN,

    JUMLAH_PEMASUKAN,
    KATEGORI_PEMASUKAN,
    KETERANGAN_PEMASUKAN,

    PILIH_EDIT,
    PILIH_BAGIAN_EDIT,
    NILAI_EDIT,

    PILIH_HAPUS,

    PILIH_BULAN_LAPORAN,
) = range(11)


# ============================================================
# HELPER
# ============================================================

def rupiah(amount):
    return f"Rp{int(amount):,}".replace(",", ".")


def parse_amount(text):

    text = (
        str(text)
        .replace(".", "")
        .replace(",", "")
        .strip()
    )

    if not text.isdigit():
        return None

    amount = int(text)

    if amount <= 0:
        return None

    return amount


# ============================================================
# USER
# ============================================================

def get_user(user_id):

    response = (
        supabase
        .table("users")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    row = response.data[0]

    return {
        "user_id": str(row["user_id"]),
        "username": row.get("username") or "",
        "nama": row.get("nama") or "",
        "reminder": row.get("reminder") or "OFF",
    }


def save_or_update_user(
    user_id,
    username,
    nama,
):

    supabase.table("users").upsert(
        {
            "user_id": user_id,
            "username": username or "",
            "nama": nama or "",
        },
        on_conflict="user_id",
    ).execute()


def set_user_reminder(
    user_id,
    status,
):

    response = (
        supabase
        .table("users")
        .update({
            "reminder": status
        })
        .eq("user_id", user_id)
        .execute()
    )

    return bool(response.data)


# ============================================================
# TRANSACTIONS
# ============================================================

def get_all_transactions():

    response = (
        supabase
        .table("transactions")
        .select("*")
        .order("id")
        .execute()
    )

    transactions = []

    for row in response.data:

        transactions.append({
            "id": str(row["id"]),
            "user id": str(row["user_id"]),
            "tanggal": row["tanggal"],
            "jenis": row["jenis"],
            "nominal": str(row["nominal"]),
            "kategori": row.get("kategori") or "",
            "keterangan": row.get("keterangan") or "",
        })

    return transactions


def save_transaction(
    user_id,
    transaction_type,
    amount,
    category,
    description,
):

    response = (
        supabase
        .table("transactions")
        .insert({
            "user_id": user_id,
            "tanggal": datetime.now(
                TIMEZONE
            ).isoformat(),
            "jenis": transaction_type,
            "nominal": amount,
            "kategori": category,
            "keterangan": description,
        })
        .select("id")
        .execute()
    )

    if not response.data:
        raise Exception(
            "Gagal menyimpan transaksi ke Supabase."
        )

    return response.data[0]["id"]


def get_user_transactions(user_id):

    response = (
        supabase
        .table("transactions")
        .select("*")
        .eq("user_id", user_id)
        .order("id")
        .execute()
    )

    transactions = []

    for row in response.data:

        transactions.append({
            "id": str(row["id"]),
            "user id": str(row["user_id"]),
            "tanggal": row["tanggal"],
            "jenis": row["jenis"],
            "nominal": str(row["nominal"]),
            "kategori": row.get("kategori") or "",
            "keterangan": row.get("keterangan") or "",
        })

    return transactions


def get_user_transaction_by_id(
    user_id,
    transaction_id,
):

    response = (
        supabase
        .table("transactions")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", transaction_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    row = response.data[0]

    return {
        "id": str(row["id"]),
        "user id": str(row["user_id"]),
        "tanggal": row["tanggal"],
        "jenis": row["jenis"],
        "nominal": str(row["nominal"]),
        "kategori": row.get("kategori") or "",
        "keterangan": row.get("keterangan") or "",
    }


# ============================================================
# UPDATE TRANSAKSI
# ============================================================

def update_transaction(
    user_id,
    transaction_id,
    nominal=None,
    kategori=None,
    keterangan=None,
):

    data = {}

    if nominal is not None:
        data["nominal"] = nominal

    if kategori is not None:
        data["kategori"] = kategori

    if keterangan is not None:
        data["keterangan"] = keterangan

    if not data:
        return False

    response = (
        supabase
        .table("transactions")
        .update(data)
        .eq("id", transaction_id)
        .eq("user_id", user_id)
        .execute()
    )

    return bool(response.data)


# ============================================================
# HAPUS TRANSAKSI
# ============================================================

def delete_transaction(
    user_id,
    transaction_id,
):

    response = (
        supabase
        .table("transactions")
        .delete()
        .eq("id", transaction_id)
        .eq("user_id", user_id)
        .execute()
    )

    return bool(response.data)


# ============================================================
# CEK PENGELUARAN HARI INI
# ============================================================

def has_expense_today(user_id):

    transactions = get_user_transactions(
        user_id
    )

    today = datetime.now(
        TIMEZONE
    ).date()

    for transaction in transactions:

        if transaction["jenis"] != "Pengeluaran":
            continue

        try:

            transaction_date = (
                datetime.fromisoformat(
                    transaction["tanggal"]
                )
                .astimezone(TIMEZONE)
                .date()
            )

        except (
            ValueError,
            TypeError,
        ):
            continue

        if transaction_date == today:
            return True

    return False


# ============================================================
# REMINDER OTOMATIS
# ============================================================

async def reminder_loop(application):

    last_reminder_date = None

    while True:

        try:

            now = datetime.now(
                TIMEZONE
            )

            if (
                now.hour == REMINDER_HOUR
                and now.minute == REMINDER_MINUTE
                and last_reminder_date != now.date()
            ):

                print(
                    "🔔 Menjalankan reminder harian..."
                )

                response = (
                    supabase
                    .table("users")
                    .select("*")
                    .eq("reminder", "ON")
                    .execute()
                )

                for row in response.data:

                    user_id = str(
                        row["user_id"]
                    )

                    try:

                        already_recorded = (
                            has_expense_today(
                                user_id
                            )
                        )

                        if already_recorded:
                            continue

                        await application.bot.send_message(
                            chat_id=int(user_id),
                            text=(
                                "🌙✨ Jangan lupa catat "
                                "pengeluaran kamu hari ini ya! 💸📝\n\n"
                                "Biar catatan keuangan kamu "
                                "tetap rapi dan nggak ada yang kelewat 📊💰"
                            ),
                        )

                    except Exception as e:

                        print(
                            f"❌ Gagal reminder "
                            f"{user_id}: {e}"
                        )

                last_reminder_date = now.date()

        except Exception as e:

            print(
                "❌ Reminder error:",
                repr(e),
            )

        await asyncio.sleep(30)


async def post_init(application):

    application.create_task(
        reminder_loop(application)
    )


# ============================================================
# MENU UTAMA
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    save_or_update_user(
        user_id=user.id,
        username=user.username,
        nama=user.full_name,
    )

    keyboard = [
        [
            "💸 Catat Pengeluaran",
            "💰 Catat Pemasukan",
        ],
        [
            "📊 Lihat Saldo",
            "📜 Riwayat",
        ],
        [
            "✏️ Edit Transaksi",
            "🗑️ Hapus Transaksi",
        ],
        [
            "📈 Statistik",
            "📋 Laporan Bulanan",
        ],
        [
            "🔔 Reminder Harian",
        ],
    ]

    await update.message.reply_text(
        "👋 Halo!\n\n"
        "💰 BOT CATAT KEUANGAN\n\n"
        "Semua transaksi tersimpan "
        "langsung di Supabase.\n\n"
        "Data setiap pengguna dipisahkan "
        "berdasarkan akun Telegram.\n\n"
        "Pilih menu:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )


# ============================================================
# REMINDER MENU
# ============================================================

async def menu_reminder(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id

    user = get_user(user_id)

    status = "OFF"

    if user:
        status = (
            user["reminder"].upper()
            or "OFF"
        )

    keyboard = [
        [
            InlineKeyboardButton(
                "🔔 Aktifkan Reminder",
                callback_data="reminder_on",
            )
        ],
        [
            InlineKeyboardButton(
                "🔕 Matikan Reminder",
                callback_data="reminder_off",
            )
        ],
    ]

    await update.message.reply_text(
        "🔔 REMINDER HARIAN\n\n"
        f"Status saat ini: "
        f"{'🟢 ON' if status == 'ON' else '🔴 OFF'}\n\n"
        "⏰ Jam reminder: 21:00 WIB\n\n"
        "Reminder hanya dikirim kalau kamu "
        "belum mencatat pengeluaran hari ini.\n\n"
        "Pilih pengaturan:",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


async def reminder_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if query.data == "reminder_on":

        success = set_user_reminder(
            user_id,
            "ON",
        )

        if success:

            await query.edit_message_text(
                "🟢 Reminder berhasil diaktifkan!\n\n"
                "⏰ Setiap hari pukul 21:00 WIB\n\n"
                "🌙✨ Jangan lupa catat pengeluaran "
                "kamu hari ini ya! 💸📝"
            )

        else:

            await query.edit_message_text(
                "❌ Gagal mengaktifkan reminder."
            )

    elif query.data == "reminder_off":

        success = set_user_reminder(
            user_id,
            "OFF",
        )

        if success:

            await query.edit_message_text(
                "🔴 Reminder berhasil dimatikan."
            )

        else:

            await query.edit_message_text(
                "❌ Gagal mematikan reminder."
            )


# ============================================================
# CATAT PENGELUARAN
# ============================================================

async def pilih_pengeluaran(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "💸 Masukkan jumlah pengeluaran.\n\n"
        "Contoh:\n25000"
    )

    return JUMLAH_PENGELUARAN


async def jumlah_pengeluaran(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    amount = parse_amount(
        update.message.text
    )

    if amount is None:

        await update.message.reply_text(
            "❌ Nominal tidak valid.\n\n"
            "Contoh: 25000"
        )

        return JUMLAH_PENGELUARAN

    context.user_data["amount"] = amount

    await update.message.reply_text(
        "🏷️ Masukkan kategori pengeluaran."
    )

    return KATEGORI_PENGELUARAN


async def kategori_pengeluaran(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    category = update.message.text.strip()

    if not category:

        await update.message.reply_text(
            "❌ Kategori tidak boleh kosong."
        )

        return KATEGORI_PENGELUARAN

    context.user_data["category"] = category

    await update.message.reply_text(
        "📝 Masukkan keterangan.\n\n"
        "Kalau tidak ada, ketik: -"
    )

    return KETERANGAN_PENGELUARAN


async def keterangan_pengeluaran(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    amount = context.user_data["amount"]
    category = context.user_data["category"]

    description = (
        update.message.text.strip()
    )

    if description == "-":
        description = ""

    transaction_id = save_transaction(
        user_id=update.effective_user.id,
        transaction_type="Pengeluaran",
        amount=amount,
        category=category,
        description=description,
    )

    await update.message.reply_text(
        "✅ Pengeluaran berhasil disimpan!\n\n"
        f"🆔 ID: {transaction_id}\n"
        f"💸 {rupiah(amount)}\n"
        f"🏷️ {category}\n"
        f"📝 {description or '-'}"
    )

    context.user_data.clear()

    return ConversationHandler.END


# ============================================================
# CATAT PEMASUKAN
# ============================================================

async def pilih_pemasukan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    await update.message.reply_text(
        "💰 Masukkan jumlah pemasukan.\n\n"
        "Contoh:\n500000"
    )

    return JUMLAH_PEMASUKAN


async def jumlah_pemasukan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    amount = parse_amount(
        update.message.text
    )

    if amount is None:

        await update.message.reply_text(
            "❌ Nominal tidak valid."
        )

        return JUMLAH_PEMASUKAN

    context.user_data["amount"] = amount

    await update.message.reply_text(
        "🏷️ Masukkan kategori pemasukan."
    )

    return KATEGORI_PEMASUKAN


async def kategori_pemasukan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    category = update.message.text.strip()

    if not category:

        await update.message.reply_text(
            "❌ Kategori tidak boleh kosong."
        )

        return KATEGORI_PEMASUKAN

    context.user_data["category"] = category

    await update.message.reply_text(
        "📝 Masukkan keterangan.\n\n"
        "Kalau tidak ada, ketik: -"
    )

    return KETERANGAN_PEMASUKAN


async def keterangan_pemasukan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    amount = context.user_data["amount"]
    category = context.user_data["category"]

    description = (
        update.message.text.strip()
    )

    if description == "-":
        description = ""

    transaction_id = save_transaction(
        user_id=update.effective_user.id,
        transaction_type="Pemasukan",
        amount=amount,
        category=category,
        description=description,
    )

    await update.message.reply_text(
        "✅ Pemasukan berhasil disimpan!\n\n"
        f"🆔 ID: {transaction_id}\n"
        f"💰 {rupiah(amount)}\n"
        f"🏷️ {category}\n"
        f"📝 {description or '-'}"
    )

    context.user_data.clear()

    return ConversationHandler.END


# ============================================================
# SALDO
# ============================================================

async def lihat_saldo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    transactions = get_user_transactions(
        update.effective_user.id
    )

    total_income = 0
    total_expense = 0

    for transaction in transactions:

        amount = parse_amount(
            transaction["nominal"]
        )

        if amount is None:
            continue

        if transaction["jenis"] == "Pemasukan":

            total_income += amount

        elif transaction["jenis"] == "Pengeluaran":

            total_expense += amount

    balance = (
        total_income
        - total_expense
    )

    await update.message.reply_text(
        "📊 SALDO KAMU\n\n"
        f"💰 Total pemasukan:\n"
        f"{rupiah(total_income)}\n\n"
        f"💸 Total pengeluaran:\n"
        f"{rupiah(total_expense)}\n\n"
        "━━━━━━━━━━━━━━\n"
        f"💵 SALDO:\n"
        f"{rupiah(balance)}"
    )


# ============================================================
# RIWAYAT
# ============================================================

async def pilih_riwayat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    keyboard = [
        [
            "📅 Hari Ini",
            "📆 Minggu Ini",
        ],
        [
            "🗓️ Bulan Ini",
            "📚 Semua",
        ],
        [
            "🔙 Kembali",
        ],
    ]

    await update.message.reply_text(
        "📜 Pilih periode riwayat:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )


async def tampilkan_riwayat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id
    pilihan = update.message.text

    transactions = get_user_transactions(
        user_id
    )

    now = datetime.now(TIMEZONE)

    if pilihan == "📅 Hari Ini":

        start_date = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        title = "📅 RIWAYAT HARI INI"

    elif pilihan == "📆 Minggu Ini":

        start_date = (
            now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            - timedelta(
                days=now.weekday()
            )
        )

        title = "📆 RIWAYAT MINGGU INI"

    elif pilihan == "🗓️ Bulan Ini":

        start_date = now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        title = "🗓️ RIWAYAT BULAN INI"

    elif pilihan == "📚 Semua":

        start_date = None
        title = "📚 SEMUA RIWAYAT"

    else:
        return

    filtered = []

    for transaction in transactions:

        try:

            transaction_date = (
                datetime.fromisoformat(
                    transaction["tanggal"]
                ).astimezone(TIMEZONE)
            )

        except (
            ValueError,
            TypeError,
        ):
            continue

        if (
            start_date is None
            or transaction_date >= start_date
        ):

            filtered.append(
                (
                    transaction,
                    transaction_date,
                )
            )

    if not filtered:

        await update.message.reply_text(
            f"{title}\n\nBelum ada transaksi."
        )

        return

    filtered.sort(
        key=lambda item: item[1],
        reverse=True,
    )

    total_income = 0
    total_expense = 0

    lines = [
        title,
        "",
    ]

    for transaction, transaction_date in filtered:

        amount = parse_amount(
            transaction["nominal"]
        )

        if amount is None:
            continue

        if transaction["jenis"] == "Pemasukan":

            icon = "💰"
            total_income += amount

        else:

            icon = "💸"
            total_expense += amount

        lines.extend([
            f"🆔 {transaction['id']}",
            f"{icon} {rupiah(amount)}",
            f"🏷️ {transaction['kategori']}",
            f"📝 {transaction['keterangan'] or '-'}",
            "🕒 "
            + transaction_date.strftime(
                "%d/%m/%Y %H:%M"
            ),
            "",
        ])

    balance = (
        total_income
        - total_expense
    )

    lines.extend([
        "━━━━━━━━━━━━━━",
        f"💰 Pemasukan: {rupiah(total_income)}",
        f"💸 Pengeluaran: {rupiah(total_expense)}",
        f"💵 Selisih: {rupiah(balance)}",
    ])

    await update.message.reply_text(
        "\n".join(lines)
    )


# ============================================================
# EDIT
# ============================================================

async def mulai_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    transactions = get_user_transactions(
        update.effective_user.id
    )

    if not transactions:

        await update.message.reply_text(
            "Belum ada transaksi yang bisa diedit."
        )

        return ConversationHandler.END

    transactions.sort(
        key=lambda transaction:
        int(transaction["id"])
        if transaction["id"].isdigit()
        else 0,
        reverse=True,
    )

    lines = [
        "✏️ EDIT TRANSAKSI",
        "",
        "Ketik ID transaksi:",
        "",
    ]

    for transaction in transactions[:15]:

        amount = parse_amount(
            transaction["nominal"]
        )

        if amount is None:
            continue

        lines.append(
            f"ID {transaction['id']} | "
            f"{rupiah(amount)} | "
            f"{transaction['kategori']}"
        )

    await update.message.reply_text(
        "\n".join(lines)
    )

    return PILIH_EDIT


async def pilih_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    transaction_id = (
        update.message.text.strip()
    )

    transaction = (
        get_user_transaction_by_id(
            update.effective_user.id,
            transaction_id,
        )
    )

    if transaction is None:

        await update.message.reply_text(
            "❌ Transaksi tidak ditemukan."
        )

        return PILIH_EDIT

    context.user_data[
        "edit_transaction_id"
    ] = transaction_id

    await update.message.reply_text(
        "Apa yang ingin diubah?\n\n"
        "1️⃣ Nominal\n"
        "2️⃣ Kategori\n"
        "3️⃣ Keterangan"
    )

    return PILIH_BAGIAN_EDIT


async def pilih_bagian_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    pilihan = (
        update.message.text
        .strip()
        .lower()
    )

    mapping = {
        "1": "nominal",
        "nominal": "nominal",
        "2": "kategori",
        "kategori": "kategori",
        "3": "keterangan",
        "keterangan": "keterangan",
    }

    field = mapping.get(pilihan)

    if field is None:

        await update.message.reply_text(
            "❌ Ketik 1, 2, atau 3."
        )

        return PILIH_BAGIAN_EDIT

    context.user_data[
        "edit_field"
    ] = field

    if field == "nominal":

        text = "Masukkan nominal baru."

    elif field == "kategori":

        text = "Masukkan kategori baru."

    else:

        text = (
            "Masukkan keterangan baru.\n"
            "Ketik - untuk kosong."
        )

    await update.message.reply_text(
        text
    )

    return NILAI_EDIT


async def nilai_edit(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user_id = update.effective_user.id

    transaction_id = (
        context.user_data[
            "edit_transaction_id"
        ]
    )

    field = (
        context.user_data[
            "edit_field"
        ]
    )

    value = update.message.text.strip()

    if field == "nominal":

        amount = parse_amount(value)

        if amount is None:

            await update.message.reply_text(
                "❌ Nominal tidak valid."
            )

            return NILAI_EDIT

        success = update_transaction(
            user_id,
            transaction_id,
            nominal=amount,
        )

    elif field == "kategori":

        if not value:

            await update.message.reply_text(
                "❌ Kategori tidak boleh kosong."
            )

            return NILAI_EDIT

        success = update_transaction(
            user_id,
            transaction_id,
            kategori=value,
        )

    else:

        if value == "-":
            value = ""

        success = update_transaction(
            user_id,
            transaction_id,
            keterangan=value,
        )

    if success:

        await update.message.reply_text(
            "✅ Transaksi berhasil diperbarui!"
        )

    else:

        await update.message.reply_text(
            "❌ Gagal memperbarui transaksi."
        )

    context.user_data.clear()

    return ConversationHandler.END


# ============================================================
# HAPUS
# ============================================================

async def mulai_hapus(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    transactions = get_user_transactions(
        update.effective_user.id
    )

    if not transactions:

        await update.message.reply_text(
            "Belum ada transaksi yang bisa dihapus."
        )

        return ConversationHandler.END

    lines = [
        "🗑️ HAPUS TRANSAKSI",
        "",
        "Ketik ID transaksi:",
        "",
    ]

    for transaction in transactions[-15:]:

        amount = parse_amount(
            transaction["nominal"]
        )

        lines.append(
            f"ID {transaction['id']} | "
            f"{rupiah(amount or 0)} | "
            f"{transaction['kategori']}"
        )

    await update.message.reply_text(
        "\n".join(lines)
    )

    return PILIH_HAPUS


async def pilih_hapus(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    transaction_id = (
        update.message.text.strip()
    )

    transaction = (
        get_user_transaction_by_id(
            update.effective_user.id,
            transaction_id,
        )
    )

    if transaction is None:

        await update.message.reply_text(
            "❌ Transaksi tidak ditemukan."
        )

        return PILIH_HAPUS

    keyboard = [
        [
            InlineKeyboardButton(
                "✅ Ya, Hapus",
                callback_data=(
                    f"delete_yes:{transaction_id}"
                ),
            ),
            InlineKeyboardButton(
                "❌ Batal",
                callback_data=(
                    f"delete_no:{transaction_id}"
                ),
            ),
        ]
    ]

    await update.message.reply_text(
        "⚠️ Yakin ingin menghapus transaksi ini?",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )

    return ConversationHandler.END


async def konfirmasi_hapus(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    data = query.data

    transaction_id = (
        data.split(":", 1)[1]
    )

    user_id = query.from_user.id

    if data.startswith("delete_yes:"):

        success = delete_transaction(
            user_id,
            transaction_id,
        )

        if success:

            await query.edit_message_text(
                "✅ Transaksi berhasil dihapus."
            )

        else:

            await query.edit_message_text(
                "❌ Gagal menghapus transaksi."
            )

    else:

        await query.edit_message_text(
            "❌ Penghapusan dibatalkan."
        )


# ============================================================
# STATISTIK
# ============================================================

async def statistik(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    transactions = get_user_transactions(
        update.effective_user.id
    )

    if not transactions:

        await update.message.reply_text(
            "📈 STATISTIK\n\nBelum ada transaksi."
        )

        return

    total_income = 0
    total_expense = 0

    categories = {}

    for transaction in transactions:

        amount = parse_amount(
            transaction["nominal"]
        )

        if amount is None:
            continue

        if transaction["jenis"] == "Pemasukan":

            total_income += amount

        elif transaction["jenis"] == "Pengeluaran":

            total_expense += amount

            category = (
                transaction["kategori"]
                or "Tanpa Kategori"
            )

            categories[category] = (
                categories.get(category, 0)
                + amount
            )

    balance = (
        total_income
        - total_expense
    )

    lines = [
        "📈 STATISTIK KEUANGAN",
        "",
        f"📊 Jumlah transaksi: {len(transactions)}",
        "",
        f"💰 Pemasukan: {rupiah(total_income)}",
        f"💸 Pengeluaran: {rupiah(total_expense)}",
        f"💵 Saldo: {rupiah(balance)}",
    ]

    if categories:

        biggest = max(
            categories.items(),
            key=lambda item: item[1],
        )

        lines.extend([
            "",
            "🏆 PENGELUARAN TERBESAR",
            f"🏷️ {biggest[0]}",
            f"💸 {rupiah(biggest[1])}",
        ])

    await update.message.reply_text(
        "\n".join(lines)
    )


# ============================================================
# LAPORAN BULANAN
# ============================================================

async def pilih_laporan_bulanan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    now = datetime.now(TIMEZONE)

    previous_date = (
        now.replace(day=1)
        - timedelta(days=1)
    )

    keyboard = [
        [
            f"🗓️ {now.strftime('%B %Y')}",
        ],
        [
            f"🗓️ {previous_date.strftime('%B %Y')}",
        ],
        [
            "🔙 Kembali",
        ],
    ]

    await update.message.reply_text(
        "📋 LAPORAN BULANAN\n\nPilih bulan:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

    return PILIH_BULAN_LAPORAN


async def buat_laporan_bulanan(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    pilihan = (
        update.message.text.strip()
    )

    now = datetime.now(TIMEZONE)

    previous_date = (
        now.replace(day=1)
        - timedelta(days=1)
    )

    if pilihan == (
        f"🗓️ {now.strftime('%B %Y')}"
    ):

        selected_month = (
            now.strftime("%Y-%m")
        )

        title = now.strftime(
            "%B %Y"
        )

    elif pilihan == (
        f"🗓️ {previous_date.strftime('%B %Y')}"
    ):

        selected_month = (
            previous_date.strftime(
                "%Y-%m"
            )
        )

        title = previous_date.strftime(
            "%B %Y"
        )

    else:

        return PILIH_BULAN_LAPORAN

    transactions = get_user_transactions(
        update.effective_user.id
    )

    total_income = 0
    total_expense = 0

    for transaction in transactions:

        try:

            date = (
                datetime.fromisoformat(
                    transaction["tanggal"]
                ).astimezone(TIMEZONE)
            )

        except (
            ValueError,
            TypeError,
        ):
            continue

        if (
            date.strftime("%Y-%m")
            != selected_month
        ):
            continue

        amount = parse_amount(
            transaction["nominal"]
        )

        if amount is None:
            continue

        if transaction["jenis"] == "Pemasukan":

            total_income += amount

        else:

            total_expense += amount

    balance = (
        total_income
        - total_expense
    )

    await update.message.reply_text(
        f"📋 LAPORAN {title.upper()}\n\n"
        "━━━━━━━━━━━━━━\n"
        f"💰 Pemasukan: {rupiah(total_income)}\n"
        f"💸 Pengeluaran: {rupiah(total_expense)}\n"
        f"💵 Selisih: {rupiah(balance)}"
    )

    context.user_data.clear()

    return ConversationHandler.END


# ============================================================
# KEMBALI
# ============================================================

async def kembali(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.clear()

    await start(
        update,
        context,
    )


# ============================================================
# BATAL
# ============================================================

async def batal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.clear()

    await update.message.reply_text(
        "❌ Proses dibatalkan."
    )

    await start(
        update,
        context,
    )

    return ConversationHandler.END


# ============================================================
# ERROR
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    print(
        "ERROR:",
        repr(context.error),
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("====================================")
    print("🤖 BOT CATAT KEUANGAN - SUPABASE")
    print("====================================")
    print("☁️ Database  : Supabase")
    print("👥 Users     : AKTIF")
    print("📈 Statistik : AKTIF")
    print("📋 Laporan   : AKTIF")
    print("✏️ Edit      : AKTIF")
    print("🗑️ Hapus     : AKTIF")
    print("🔔 Reminder  : 21:00 WIB")
    print("====================================")

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )


    # ========================================================
    # CONVERSATION HANDLER
    # ========================================================

    conversation = ConversationHandler(

        entry_points=[

            MessageHandler(
                filters.Regex(
                    "^💸 Catat Pengeluaran$"
                ),
                pilih_pengeluaran,
            ),

            MessageHandler(
                filters.Regex(
                    "^💰 Catat Pemasukan$"
                ),
                pilih_pemasukan,
            ),

            MessageHandler(
                filters.Regex(
                    "^✏️ Edit Transaksi$"
                ),
                mulai_edit,
            ),

            MessageHandler(
                filters.Regex(
                    "^🗑️ Hapus Transaksi$"
                ),
                mulai_hapus,
            ),

            MessageHandler(
                filters.Regex(
                    "^📋 Laporan Bulanan$"
                ),
                pilih_laporan_bulanan,
            ),
        ],

        states={

            JUMLAH_PENGELUARAN: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    jumlah_pengeluaran,
                )
            ],

            KATEGORI_PENGELUARAN: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    kategori_pengeluaran,
                )
            ],

            KETERANGAN_PENGELUARAN: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    keterangan_pengeluaran,
                )
            ],

            JUMLAH_PEMASUKAN: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    jumlah_pemasukan,
                )
            ],

            KATEGORI_PEMASUKAN: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    kategori_pemasukan,
                )
            ],

            KETERANGAN_PEMASUKAN: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    keterangan_pemasukan,
                )
            ],

            PILIH_EDIT: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    pilih_edit,
                )
            ],

            PILIH_BAGIAN_EDIT: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    pilih_bagian_edit,
                )
            ],

            NILAI_EDIT: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    nilai_edit,
                )
            ],

            PILIH_HAPUS: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    pilih_hapus,
                )
            ],

            PILIH_BULAN_LAPORAN: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    buat_laporan_bulanan,
                )
            ],
        },

        fallbacks=[
            CommandHandler(
                "batal",
                batal,
            )
        ],
    )


    # ========================================================
    # /START
    # ========================================================

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        conversation
    )


    # ========================================================
    # SALDO
    # ========================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                "^📊 Lihat Saldo$"
            ),
            lihat_saldo,
        )
    )


    # ========================================================
    # RIWAYAT
    # ========================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                "^📜 Riwayat$"
            ),
            pilih_riwayat,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex(
                "^(📅 Hari Ini|📆 Minggu Ini|🗓️ Bulan Ini|📚 Semua)$"
            ),
            tampilkan_riwayat,
        )
    )


    # ========================================================
    # STATISTIK
    # ========================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                "^📈 Statistik$"
            ),
            statistik,
        )
    )


    # ========================================================
    # REMINDER
    # ========================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                "^🔔 Reminder Harian$"
            ),
            menu_reminder,
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            reminder_callback,
            pattern=r"^reminder_(on|off)$",
        )
    )


    # ========================================================
    # KEMBALI
    # ========================================================

    app.add_handler(
        MessageHandler(
            filters.Regex(
                "^🔙 Kembali$"
            ),
            kembali,
        )
    )


    # ========================================================
    # HAPUS CALLBACK
    # ========================================================

    app.add_handler(
        CallbackQueryHandler(
            konfirmasi_hapus,
            pattern=r"^delete_(yes|no):",
        )
    )


    # ========================================================
    # ERROR
    # ========================================================

    app.add_error_handler(
        error_handler
    )


    print("🚀 Bot sedang berjalan...")
    print("====================================")

    app.run_polling()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()