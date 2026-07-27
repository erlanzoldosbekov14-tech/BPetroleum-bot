import os
import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ================= Настройки =================
BOT_TOKEN = "8699906911:AAG9WtpM45hjrHp1wk85zTwDeIKe6vkeRQ"
ADMIN_CHAT_ID = 8107095434

RENDER_URL = "https://bpetroleum-bot.onrender.com"

PRICES_FILE = "prices.json"
default_prices = {"АИ-92": 84.50, "АИ-95": 91.00, "АИ-98": 98.50, "ДТ": 88.20}

if os.path.exists(PRICES_FILE):
    try:
        with open(PRICES_FILE, "r", encoding="utf-8") as f:
            prices = json.load(f)
    except Exception:
        prices = default_prices
else:
    prices = default_prices

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Автоматическая установка Webhook при запуске
@app.on_event("startup")
async def on_startup():
    webhook_url = f"{RENDER_URL}/webhook"
    await bot.set_webhook(webhook_url)

# Эндпоинт, куда Telegram присылает сообщения
@app.post("/webhook")
async def bot_webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

# REST API для сайта
@app.get("/")
def read_root():
    return {"status": "ok", "message": "Bishkek Petroleum Bot API"}

@app.get("/api/prices")
def get_prices():
    return prices

# Команды бота
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Панель Bishkek Petroleum**\n\n"
        "Для смены цены отправь: `/set 92 86.00`",
        parse_mode="Markdown"
    )

@dp.message(Command("set"))
async def cmd_set_price(message: types.Message):
    if ADMIN_CHAT_ID != 0 and message.from_user.id != ADMIN_CHAT_ID:
        await message.answer("⛔ У вас нет прав администратора.")
        return

    args = message.text.split()
    if len(args) < 3:
        await message.answer("⚠️ Использование: `/set 92 86.00`", parse_mode="Markdown")
        return

    fuel_raw = args[1].lower()
    try:
        new_price = float(args[2].replace(',', '.'))
    except ValueError:
        await message.answer("❌ Укажите корректную цену.")
        return

    fuel_map = {"92": "АИ-92", "95": "АИ-95", "98": "АИ-98", "dt": "ДТ"}
    if fuel_raw not in fuel_map:
        await message.answer("❌ Неизвестная марка (используйте 92, 95, 98, dt).")
        return

    fuel_key = fuel_map[fuel_raw]
    prices[fuel_key] = new_price

    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=4)

    await message.answer(f"✅ Цена на **{fuel_key}** обновлена: `{new_price:.2f}` сом/л", parse_mode="Markdown")
