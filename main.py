import os
import json
import logging
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardRemove
)
import uvicorn

# --- НАСТРОЙКИ ---
# Токен вашего бота от BotFather
BOT_TOKEN = "8699906911:AAG9WtpM45hjrHp1wk85ZTwDeIKe6VkveRQ"

# Ваш Telegram ID (получите его через @userinfobot и вставьте сюда вместо 0)
ADMIN_CHAT_ID = 8107095434

PRICES_FILE = "prices.json"

DEFAULT_PRICES = {
    "АИ-92": 84.50,
    "АИ-95": 91.00,
    "АИ-98": 98.50,
    "ДТ": 88.20
}

def load_prices():
    if not os.path.exists(PRICES_FILE):
        save_prices(DEFAULT_PRICES)
        return DEFAULT_PRICES
    try:
        with open(PRICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_PRICES

def save_prices(prices):
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)

prices_data = load_prices()

# --- FASTAPI И AIOGRAM ---
app = FastAPI()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- КЛАВИАТУРЫ ---
admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Посмотреть текущие цены")],
        [KeyboardButton(text="✏️ Изменить цены")]
    ],
    resize_keyboard=True
)

client_phone_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Поделиться номером телефона", request_contact=True)]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# --- ЛОГИКА ТЕЛЕГРАМ БОТА ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Если зашел администратор
    if message.from_user.id == ADMIN_CHAT_ID:
        await message.answer("Панель администратора Bishkek Petroleum активна.", reply_markup=admin_kb)
        return
    
    # Если зашел клиент
    await message.answer(
        "Здравствуйте! 👋\n"
        "Для получения виртуальной карты Bishkek Petroleum, нажмите кнопку ниже, чтобы поделиться контактом:",
        reply_markup=client_phone_kb
    )

# Прием контакта от клиента
@dp.message(F.contact)
async def handle_contact(message: types.Message):
    phone = message.contact.phone_number
    user_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else "нет username"

    await message.answer(
        "✅ Спасибо! Ваша заявка принята.\n"
        "Менеджер свяжется с вами для активации карты.",
        reply_markup=ReplyKeyboardRemove()
    )

    if ADMIN_CHAT_ID != 0:
        admin_text = (
            "💳 <b>Новая заявка на виртуальную карту!</b>\n\n"
            f"👤 <b>Имя:</b> {user_name} ({username})\n"
            f"📱 <b>Телефон:</b> <code>{phone}</code>"
        )
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode="HTML")

# Управление ценами (для админа)
@dp.message(F.text == "📊 Посмотреть текущие цены")
async def show_prices(message: types.Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    msg = "<b>Текущие цены на топливо:</b>\n\n"
    for fuel, price in prices_data.items():
        msg += f"• <b>{fuel}:</b> {price} сом/л\n"
    await message.answer(msg, parse_mode="HTML")

@dp.message(F.text == "✏️ Изменить цены")
async def edit_prices_info(message: types.Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    help_text = (
        "Чтобы изменить цену, отправьте команду:\n\n"
        "<code>/set 92 85.00</code> — измерить АИ-92\n"
        "<code>/set 95 92.50</code> — измерить АИ-95\n"
        "<code>/set 98 99.00</code> — измерить АИ-98\n"
        "<code>/set dt 89.00</code> — измерить ДТ"
    )
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("set"))
async def set_price(message: types.Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    
    args = message.text.split()
    if len(args) != 3:
        await message.answer("⚠️ Используйте формат: `/set 92 85.00`", parse_mode="Markdown")
        return

    fuel_code = args[1].lower()
    try:
        new_price = float(args[2].replace(',', '.'))
    except ValueError:
        await message.answer("⚠️ Некорректное число!")
        return

    mapping = {"92": "АИ-92", "95": "АИ-95", "98": "АИ-98", "dt": "ДТ", "дт": "ДТ"}
    
    if fuel_code not in mapping:
        await message.answer("⚠️ Неизвестная марка топлива. Доступны: 92, 95, 98, dt")
        return

    fuel_name = mapping[fuel_code]
    prices_data[fuel_name] = new_price
    save_prices(prices_data)

    await message.answer(f"✅ Цена на <b>{fuel_name}</b> обновлена: <b>{new_price} сом/л</b>", parse_mode="HTML")

# --- API ДЛЯ СЕЙТА ---

class LeadRequest(BaseModel):
    phone: str
    fuel: str
    distance: float
    liters: float
    total: float

@app.get("/api/prices")
async def get_prices():
    return prices_data

@app.post("/api/order")
async def send_order(order: LeadRequest):
    if ADMIN_CHAT_ID != 0:
        text = (
            "🚗 <b>Заявка с сайта (Калькулятор)!</b>\n\n"
            f"📱 <b>Телефон:</b> <code>{order.phone}</code>\n"
            f"⛽ <b>Топливо:</b> {order.fuel}\n"
            f"📏 <b>Расстояние:</b> {order.distance} км\n"
            f"🪣 <b>Объем:</b> {order.liters} л\n"
            f"💰 <b>Сумма:</b> {order.total} сом"
        )
        try:
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="HTML")
            return {"status": "ok"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok"}

# --- ЗАПУСК ---
async def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    await asyncio.gather(
        server.serve(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
