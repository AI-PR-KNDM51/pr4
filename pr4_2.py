import logging
import sqlite3
import random
import asyncio
import hashlib
import base64
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import requests
from urllib.parse import urlencode

# Токен вашого бота від BotFather
API_TOKEN = '8137252780:AAGrFqlpmOXe00EyQjc3cs3D_Ub3Q29FNpE'
# Публічний та приватний ключі LiqPay (sandbox режим)
LIQPAY_PUBLIC_KEY = 'sandbox_i19990232683'
LIQPAY_PRIVATE_KEY = 'sandbox_kXVqu8mLQTajwan5jhC4pOKRspRPeMToewNh2QPW'

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ініціалізація бота та диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Підключення до бази даних SQLite
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Створення таблиці користувачів з колонкою балансу, якщо вона не існує
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        balance REAL DEFAULT 0.0
    )
''')
# Створення таблиці замовлень з колонками order_id, user_id, amount та status
cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        status TEXT
    )
''')
conn.commit()

# Перевірка, чи існує колонка 'balance' в таблиці users, і додавання її, якщо ні
cursor.execute("PRAGMA table_info(users)")
columns = [info[1] for info in cursor.fetchall()]
if 'balance' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0.0")
    conn.commit()
    logger.info("Додано колонку 'balance' до таблиці 'users'.")

# Створення клавіатури для відповіді з кнопками
reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/register"), KeyboardButton(text="/balance")],
        [KeyboardButton(text="/topup")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Функція для створення Inline клавіатури для підтвердження платежу
def get_confirm_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Підтвердити платіж", callback_data=f"confirm_order:{order_id}")
            ]
        ]
    )

# Обробник команди /start
@dp.message(Command(commands=["start"]))
async def send_welcome(message: types.Message):
    welcome_text = "Ласкаво просимо! Використовуйте /register для реєстрації."
    await message.answer(welcome_text, reply_markup=reply_keyboard)
    logger.info(f"Користувач {message.from_user.id} розпочав роботу з ботом.")

# Обробник команди /register
@dp.message(Command(commands=["register"]))
async def register_user(message: types.Message):
    user_id = message.from_user.id
    name = message.from_user.full_name
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        await message.answer("Ви вже зареєстровані.", reply_markup=reply_keyboard)
        logger.info(f"Користувач {user_id} спробував зареєструватися, але вже зареєстрований.")
    else:
        cursor.execute("INSERT INTO users (user_id, name, balance) VALUES (?, ?, ?)", (user_id, name, 0.0))
        conn.commit()
        await message.answer("Ви успішно зареєстровані!", reply_markup=reply_keyboard)
        logger.info(f"Зареєстровано нового користувача: {user_id} - {name}")

# Обробник команди /balance
@dp.message(Command(commands=["balance"]))
async def show_balance(message: types.Message):
    user_id = message.from_user.id
    try:
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            balance = result[0]
            await message.answer(f"Ваш баланс: {balance} UAH", reply_markup=reply_keyboard)
            logger.info(f"Користувач {user_id} перевірив баланс: {balance} UAH")
        else:
            await message.answer("Ви не зареєстровані. Використовуйте /register для реєстрації.", reply_markup=reply_keyboard)
            logger.warning(f"Користувач {user_id} спробував перевірити баланс без реєстрації.")
    except sqlite3.OperationalError as e:
        logger.error(f"Помилка бази даних при перевірці балансу для користувача {user_id}: {e}")
        await message.answer("Виникла помилка при отриманні балансу. Спробуйте пізніше.", reply_markup=reply_keyboard)

# Обробник команди /topup
@dp.message(Command(commands=["topup"]))
async def topup_balance(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        await message.answer("Ви не зареєстровані. Використовуйте /register для реєстрації.", reply_markup=reply_keyboard)
        logger.warning(f"Користувач {user_id} спробував поповнити баланс без реєстрації.")
        return
    amount = 100.00  # Приклад суми, можна змінити або запросити у користувача
    order_id = f"{user_id}_{random.randint(100000, 999999)}"  # Генерація унікального ID замовлення
    data = {
        'public_key': LIQPAY_PUBLIC_KEY,
        'version': '3',
        'action': 'pay',
        'amount': f"{amount:.2f}",
        'currency': 'UAH',
        'description': 'Поповнення балансу',
        'order_id': order_id,
        'sandbox': '1'  # Встановіть '0' для продакшн режиму
    }
    try:
        data_json = json.dumps(data)
        data_encoded = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
        signature_str = LIQPAY_PRIVATE_KEY + data_encoded + LIQPAY_PRIVATE_KEY
        signature = base64.b64encode(hashlib.sha1(signature_str.encode('utf-8')).digest()).decode('utf-8')
        params = {'data': data_encoded, 'signature': signature}
        checkout_url = f"https://www.liqpay.ua/api/3/checkout?{urlencode(params)}"

        logger.info(f"Ініціюється поповнення для користувача {user_id}: Order ID {order_id}, Сума {amount} UAH")
        logger.info(f"Checkout URL: {checkout_url}")

        # Додавання замовлення до бази даних зі статусом 'pending'
        cursor.execute("INSERT INTO orders (order_id, user_id, amount, status) VALUES (?, ?, ?, ?)",
                       (order_id, user_id, amount, 'pending'))
        conn.commit()
        await message.answer(
            f"Ваш order_id: {order_id}\nПерейдіть за посиланням для поповнення балансу:\n{checkout_url}",
            reply_markup=reply_keyboard
        )
        await message.answer(
            "Після оплати натисніть кнопку нижче, щоб підтвердити платіж.",
            reply_markup=get_confirm_keyboard(order_id)
        )
        logger.info(f"Замовлення на поповнення створено: {order_id} для користувача {user_id}")
    except Exception as e:
        await message.answer("Сталася помилка при поповненні балансу.", reply_markup=reply_keyboard)
        logger.error(f"Виняток під час поповнення балансу: {e}")

# Обробник callback запитів для підтвердження платежу
@dp.callback_query(lambda c: c.data and c.data.startswith('confirm_order:'))
async def confirm_payment_callback(callback_query: types.CallbackQuery):
    order_id = callback_query.data.split(':')[1]
    user_id = callback_query.from_user.id

    # Отримання деталей замовлення з бази даних
    cursor.execute("SELECT user_id, amount, status FROM orders WHERE order_id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        await bot.answer_callback_query(callback_query.id, "Замовлення не знайдено.")
        await bot.send_message(user_id, "Замовлення не знайдено.", reply_markup=reply_keyboard)
        logger.warning(f"Замовлення ID {order_id} не знайдено при підтвердженні.")
        return
    db_user_id, amount, status = order
    if db_user_id != user_id:
        await bot.answer_callback_query(callback_query.id, "Ви не можете підтвердити це замовлення.")
        await bot.send_message(user_id, "Ви не можете підтвердити це замовлення.", reply_markup=reply_keyboard)
        logger.warning(f"Користувач {user_id} спробував підтвердити замовлення {order_id}, яке належить користувачу {db_user_id}.")
        return
    if status == 'success':
        await bot.answer_callback_query(callback_query.id, "Це замовлення вже було підтверджено.")
        await bot.send_message(user_id, "Це замовлення вже було підтверджено.", reply_markup=reply_keyboard)
        logger.info(f"Замовлення ID {order_id} вже підтверджено.")
        return

    # Підготовка даних для перевірки статусу платежу
    verify_data = {
        'action': 'status',
        'version': '3',
        'public_key': LIQPAY_PUBLIC_KEY,
        'order_id': order_id
    }
    data_json = json.dumps(verify_data)
    data_encoded = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
    signature_str = LIQPAY_PRIVATE_KEY + data_encoded + LIQPAY_PRIVATE_KEY
    verify_signature = base64.b64encode(hashlib.sha1(signature_str.encode('utf-8')).digest()).decode('utf-8')
    verify_payload = {
        'data': data_encoded,
        'signature': verify_signature
    }
    verify_url = "https://www.liqpay.ua/api/request"

    logger.info(f"Перевірка платежу для замовлення ID {order_id}")
    logger.info(f"URL перевірки: {verify_url}")
    logger.info(f"Дані перевірки: {verify_payload}")

    try:
        # Надсилання запиту на перевірку статусу платежу
        verify_response = requests.post(verify_url, data=verify_payload)
        logger.info(f"Статус відповіді перевірки: {verify_response.status_code}")
        logger.info(f"Текст відповіді перевірки: {verify_response.text}")
        verify_json = verify_response.json()
        status_payment = verify_json.get('status')
        if status_payment == 'sandbox':
            # Оновлення статусу замовлення на 'success' та поповнення балансу користувача
            cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", ('success', order_id))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            conn.commit()
            await bot.answer_callback_query(callback_query.id, "Платіж підтверджено успішно.")
            await bot.send_message(user_id, f"Ваш баланс було поповнено на {amount} UAH.", reply_markup=reply_keyboard)
            logger.info(f"Замовлення ID {order_id} підтверджено. Баланс користувача {user_id} оновлено.")
        else:
            await bot.answer_callback_query(callback_query.id, "Платіж не був успішним.")
            await bot.send_message(user_id, "Платіж не був успішним.", reply_markup=reply_keyboard)
            logger.warning(f"Платіж для замовлення ID {order_id} не був успішним. Статус: {status_payment}")
    except json.JSONDecodeError as e:
        # Обробка помилки декодування JSON
        await bot.answer_callback_query(callback_query.id, "Не вдалося обробити підтвердження платежу. Спробуйте пізніше.")
        await bot.send_message(user_id, "Не вдалося обробити підтвердження платежу. Спробуйте пізніше.", reply_markup=reply_keyboard)
        logger.error(f"Помилка декодування JSON при підтвердженні платежу для замовлення ID {order_id}: {e}")
    except Exception as e:
        # Обробка інших винятків
        await bot.answer_callback_query(callback_query.id, "Сталася помилка при підтвердженні платежу.")
        await bot.send_message(user_id, "Сталася помилка при підтвердженні платежу.", reply_markup=reply_keyboard)
        logger.error(f"Виняток під час підтвердження платежу для замовлення ID {order_id}: {e}")

# Обробник невідомих команд
@dp.message()
async def unauthorized(message: types.Message):
    await message.answer("Невідома команда. Використовуйте /register, /balance або /topup.", reply_markup=reply_keyboard)
    logger.warning(f"Користувач {message.from_user.id} надіслав невідому команду: {message.text}")

# Основна асинхронна функція для запуску бота
async def main():
    await dp.start_polling(bot)

# Запуск бота
if __name__ == '__main__':
    asyncio.run(main())
