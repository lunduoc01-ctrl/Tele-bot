
# app.py
# Python 3.10+ | pip install -r requirements.txt
# Bot cửa hàng dịch vụ số "UI kiểu RentOTP" nhưng dùng hợp pháp

import os, uuid, asyncio, aiosqlite, datetime as dt
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

# ========= Cấu hình =========
BOT_TOKEN = os.getenv("BOT_TOKEN") or "PUT_YOUR_TOKEN_HERE"
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")}
DB_PATH = os.getenv("DB_PATH", "shop.db")

# ========= DB =========
CREATE_SQL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(
  user_id INTEGER PRIMARY KEY,
  username TEXT,
  balance INTEGER DEFAULT 0,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS services(
  id TEXT PRIMARY KEY,
  name TEXT,
  price INTEGER,
  enabled INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS orders(
  id TEXT PRIMARY KEY,
  user_id INTEGER,
  service_id TEXT,
  price INTEGER,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS deposits(
  id TEXT PRIMARY KEY,
  user_id INTEGER,
  amount INTEGER,
  status TEXT, -- pending, approved, rejected
  created_at TEXT
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        for s in CREATE_SQL.strip().split(";"):
            ss = s.strip()
            if ss:
                await db.execute(ss)
        # seed demo
        cur = await db.execute("SELECT COUNT(*) FROM services")
        (count,) = await cur.fetchone()
        if count == 0:
            demo = [
                ("zalo-data-1", "Zalo+Data 1 ngày", 15000),
                ("gamecode-7", "Mở slot nhân vật (7 ngày)", 30000),
                ("vip-support", "Hỗ trợ VIP (tháng)", 90000),
            ]
            await db.executemany("INSERT INTO services(id,name,price) VALUES(?,?,?)", demo)
        await db.commit()

# ========= Helpers =========
def money(v: int) -> str:
    return f"{v:,}đ".replace(",", ".")

def menu_kb():
    kb = [
        [InlineKeyboardButton(text="💰 Số Dư", callback_data="balance"),
         InlineKeyboardButton(text="🛒 Dịch Vụ", callback_data="services")],
        [InlineKeyboardButton(text="➕ Nạp Tiền", callback_data="deposit"),
         InlineKeyboardButton(text="🧑‍💼 CSKH", url="https://t.me/your_support_handle")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Về Menu", callback_data="back_menu")]
    ])

# ========= Bot =========
dp = Dispatcher()

@dp.message(Command("start"))
async def start(m: Message):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users(user_id, username, created_at) VALUES(?,?,?)",
            (m.from_user.id, m.from_user.username, dt.datetime.utcnow().isoformat()),
        )
        await db.commit()
    await m.answer(
        "👋 Chào bạn! Đây là bot cửa hàng dịch vụ số (demo hợp pháp).\n"
        "Dùng các nút bên dưới để thao tác.",
        reply_markup=menu_kb()
    )

@dp.callback_query(F.data == "balance")
async def cb_balance(cq: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT balance FROM users WHERE user_id=?", (cq.from_user.id,))
        row = await cur.fetchone()
    bal = row[0] if row else 0
    await cq.message.edit_text(f"💰 Số dư hiện tại của bạn: <b>{money(bal)}</b>", reply_markup=menu_kb())

@dp.callback_query(F.data == "services")
async def cb_services(cq: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id,name,price FROM services WHERE enabled=1 ORDER BY rowid")
        items = await cur.fetchall()
    kb = [[InlineKeyboardButton(text=f"{name} — {money(price)}", callback_data=f"buy:{sid}")]
          for (sid, name, price) in items]
    kb.append([InlineKeyboardButton(text="⬅️ Về Menu", callback_data="back_menu")])
    await cq.message.edit_text("🛍 Chọn dịch vụ muốn mua:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buy:"))
async def cb_buy(cq: CallbackQuery):
    sid = cq.data.split(":",1)[1]
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name,price FROM services WHERE id=?", (sid,))
        svc = await cur.fetchone()
        cur = await db.execute("SELECT balance FROM users WHERE user_id=?", (cq.from_user.id,))
        row = await cur.fetchone()
    if not svc:
        return await cq.answer("Dịch vụ không tồn tại!", show_alert=True)
    name, price = svc
    bal = row[0] if row else 0
    if bal < price:
        return await cq.answer("❌ Số dư không đủ. Hãy nạp tiền.", show_alert=True)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (price, cq.from_user.id))
        await db.execute(
            "INSERT INTO orders(id,user_id,service_id,price,created_at) VALUES(?,?,?,?,?)",
            (uuid.uuid4().hex, cq.from_user.id, sid, price, dt.datetime.utcnow().isoformat())
        )
        await db.commit()

    await cq.message.edit_text(
        f"✅ Mua thành công: <b>{name}</b> ({money(price)})\n"
        f"— Hệ thống sẽ xử lý & gửi nội dung dịch vụ (demo).",
        reply_markup=menu_kb()
    )

@dp.callback_query(F.data == "deposit")
async def cb_deposit(cq: CallbackQuery):
    dep_id = uuid.uuid4().hex[:10]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO deposits(id,user_id,amount,status,created_at) VALUES(?,?,?,?,?)",
            (dep_id, cq.from_user.id, 0, "pending", dt.datetime.utcnow().isoformat())
        )
        await db.commit()
    text = (
        "💳 Nạp tiền (DEMO):\n"
        f"• Mã yêu cầu: <code>{dep_id}</code>\n"
        "• Nhắn admin duyệt nạp với cú pháp:\n"
        f"<code>/approve {dep_id} 50000</code>  → cộng 50.000đ\n\n"
        "⚠️ Production: tích hợp cổng thanh toán hợp pháp + xử lý webhook."
    )
    await cq.message.edit_text(text, reply_markup=back_kb())

@dp.callback_query(F.data == "back_menu")
async def cb_back_menu(cq: CallbackQuery):
    await cq.message.edit_text("Bạn đang ở Menu chính.", reply_markup=menu_kb())

# ========= Admin =========
@dp.message(Command("approve"))
async def approve(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    try:
        _, dep_id, amount = m.text.split()
        amount = int(amount)
    except Exception:
        return await m.reply("Cú pháp: /approve <deposit_id> <amount>")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id,status FROM deposits WHERE id=?", (dep_id,))
        row = await cur.fetchone()
        if not row:
            return await m.reply("Không tìm thấy deposit.")
        user_id, status = row
        if status != "pending":
            return await m.reply("Deposit đã xử lý.")
        await db.execute("UPDATE deposits SET amount=?, status='approved' WHERE id=?", (amount, dep_id))
        await db.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
        await db.commit()
    await m.reply(f"✅ Đã cộng {amount:,}đ cho user {user_id}".replace(",", "."))
    try:
        await m.bot.send_message(user_id, f"💳 Nạp tiền thành công: +{amount:,}đ".replace(",", "."))
    except Exception:
        pass

@dp.message(Command("reject"))
async def reject(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    try:
        _, dep_id = m.text.split()
    except Exception:
        return await m.reply("Cú pháp: /reject <deposit_id>")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE deposits SET status='rejected' WHERE id=?", (dep_id,))
        await db.commit()
    await m.reply("❌ Đã từ chối deposit.")

# ========= Run =========
async def main():
    await init_db()
    bot = Bot(BOT_TOKEN, parse_mode="HTML")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
