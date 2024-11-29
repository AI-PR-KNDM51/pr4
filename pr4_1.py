import logging
import sqlite3
import random
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import requests
from aiogram import F
from aiogram.exceptions import TelegramAPIError

# Токен вашого бота, отриманий від BotFather
API_TOKEN = '8137252780:AAGrFqlpmOXe00EyQjc3cs3D_Ub3Q29FNpE'

# Налаштування логування для відслідковування подій та помилок
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ініціалізація бота та диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Підключення до бази даних SQLite
conn = sqlite3.connect('users.db')
cursor = conn.cursor()

# Створення таблиці користувачів, якщо вона не існує
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        selection_history TEXT
    )
''')
conn.commit()

# Створення клавіатури з командами та кнопкою "Підібрати стиль"
reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="/start"),
            KeyboardButton(text="/help"),
            KeyboardButton(text="/info"),
        ],
        [
            KeyboardButton(text="Підібрати стиль"),
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Обробник команди /start
@dp.message(Command(commands=["start"]))
async def send_welcome(message: types.Message):
    welcome_text = (
        "Ласкаво просимо! Я допоможу вам підібрати діловий одяг."
    )
    await message.answer(welcome_text, reply_markup=reply_keyboard)
    logger.info(f"Користувач {message.from_user.id} розпочав роботу з ботом.")

# Обробник команди /help
@dp.message(Command(commands=["help"]))
async def send_help(message: types.Message):
    help_text = (
        "/start - Запуск бота\n"
        "/help - Допомога\n"
        "/info - Інформація про бота\n"
        "Ви можете надіслати фото для аналізу або скористатися кнопками нижче."
    )
    await message.answer(help_text, reply_markup=reply_keyboard)
    logger.info(f"Користувач {message.from_user.id} запитав допомогу.")

# Обробник команди /info
@dp.message(Command(commands=["info"]))
async def send_info(message: types.Message):
    info_text = (
        "Цей бот допомагає підібрати діловий одяг з урахуванням ваших вподобань, "
        "сезонності, модних тенденцій та бюджету."
    )
    await message.answer(info_text, reply_markup=reply_keyboard)
    logger.info(f"Користувач {message.from_user.id} запитав інформацію про бота.")

# Обробник повідомлення з текстом "Підібрати стиль"
@dp.message(F.text == "Підібрати стиль")
async def pick_style(message: types.Message):
    await message.answer("Оберіть стиль:", reply_markup=style_suggestions())
    logger.info(f"Користувач {message.from_user.id} обрав опцію 'Підібрати стиль'.")

# Обробник інших текстових повідомлень, які не є командами чи кнопками
@dp.message(F.text & ~F.photo & ~F.text.in_(["/start", "/help", "/info", "Підібрати стиль"]))
async def echo_message(message: types.Message):
    await message.answer("Натисніть кнопку нижче для початку.", reply_markup=reply_keyboard)
    logger.info(f"Користувач {message.from_user.id} надіслав невідому команду: {message.text}")

# Обробник повідомлень з фото
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    await message.answer("Дякуємо за фото! Ми проаналізуємо його та надамо рекомендації.")
    logger.info(f"Користувач {message.from_user.id} надіслав фото для аналізу.")

    # Тут можна додати код для аналізу фото
    # Наприклад, використання машинного навчання для розпізнавання одягу

    # Генерація випадкових сум у гривнях
    style_in_photo_uah = random.randint(1000, 10000)
    business_style_uah = random.randint(1000, 10000)
    # Конвертація сум у долари США
    style_in_photo_usd = get_currency_conversion(style_in_photo_uah, 'UAH', 'USD')
    business_style_usd = get_currency_conversion(business_style_uah, 'UAH', 'USD')

    # Формування тексту відповіді з розрахунками
    response_text = (
        f"Вартість стилю на фото: {style_in_photo_uah} UAH (~{style_in_photo_usd:.2f} USD)\n"
        f"Вартість ділового стилю: {business_style_uah} UAH (~{business_style_usd:.2f} USD)"
    )

    # Надсилання відповіді користувачу
    await message.answer(response_text, reply_markup=reply_keyboard)
    logger.info(f"Надіслано розрахунки стилів користувачу {message.from_user.id}.")

# Обробник callback запитів (натискання кнопок Inline клавіатури)
@dp.callback_query(F.df)
async def process_callback(callback_query: types.CallbackQuery):
    code = callback_query.data
    user_id = callback_query.from_user.id
    logger.info(f"Отримано callback запит від користувача {user_id}: {code}")

    if code == 'choose_style':
        # Користувач обрав опцію вибору стилю
        await callback_query.message.answer("Оберіть стиль:", reply_markup=style_suggestions())
        logger.info(f"Користувач {user_id} обрав опцію 'Оберіть стиль'.")
    elif code.startswith('style_'):
        # Користувач обрав конкретний стиль
        style = code.replace('style_', '')
        # Генерація випадкової суми у гривнях для обраного стилю
        uah_amount = random.randint(1000, 10000)
        # Конвертація суми у долари США
        usd_amount = get_currency_conversion(uah_amount, 'UAH', 'USD')
        # Формування тексту відповіді
        response_text = (
            f"Ви обрали стиль: {style}\n"
            f"Приблизна вартість: {uah_amount} UAH (~{usd_amount:.2f} USD)"
        )
        # Надсилання відповіді користувачу
        await callback_query.message.answer(
            response_text,
            reply_markup=reply_keyboard
        )
        # Збереження вибору стилю користувача в базі даних
        save_user_selection(user_id, style)
        logger.info(f"Користувач {user_id} обрав стиль: {style} з вартістю {uah_amount} UAH.")
    # Додати інші обробки, якщо потрібно

    await callback_query.answer()  # Підтвердження отримання callback

# Функція для створення Inline клавіатури з пропозиціями стилів
def style_suggestions():
    builder = InlineKeyboardBuilder()
    builder.button(text="Класичний", callback_data='style_classic')
    builder.button(text="Модерн", callback_data='style_modern')
    builder.button(text="Кежуал", callback_data='style_casual')
    builder.adjust(1, 1, 1)  # Розташування кнопок по одному в ряд
    return builder.as_markup()

# Функція для конвертації валюти за допомогою зовнішнього API
def get_currency_conversion(amount, from_currency, to_currency):
    try:
        # Запит до API для отримання курсу валют
        response = requests.get(f'https://api.exchangerate-api.com/v4/latest/{from_currency}')
        data = response.json()
        rate = data['rates'].get(to_currency)
        if rate:
            # Повернення конвертованої суми
            return amount * rate
        else:
            logging.error(f"Валюта {to_currency} не знайдена.")
            return 0
    except Exception as e:
        # Обробка помилок при запиті до API
        logging.error(f"Помилка конвертації валюти: {e}")
        return 0

# Функція для збереження вибору стилю користувача в базі даних
def save_user_selection(user_id, selection):
    try:
        # Вставка або оновлення запису з історією виборів користувача
        cursor.execute("INSERT OR REPLACE INTO users (user_id, selection_history) VALUES (?, ?)",
                       (user_id, selection))
        conn.commit()
        logger.info(f"Збережено вибір стилю для користувача {user_id}: {selection}")
    except Exception as e:
        # Обробка помилок при записі в базу даних
        logging.error(f"Помилка збереження вибору стилю для користувача {user_id}: {e}")

# Обробник винятків та помилок
@dp.errors()
async def handle_exceptions(update: types.Update, exception: Exception):
    logging.error(f"Update {update} викликала помилку {exception}")
    try:
        if isinstance(update, types.Update):
            if update.message:
                # Надсилання повідомлення про помилку користувачу
                await update.message.answer("Виникла помилка. Спробуйте пізніше.", reply_markup=reply_keyboard)
                logger.error(f"Помилка при обробці повідомлення від користувача {update.message.from_user.id}: {exception}")
            elif update.callback_query:
                # Надсилання повідомлення про помилку користувачу
                await update.callback_query.message.answer("Виникла помилка. Спробуйте пізніше.", reply_markup=reply_keyboard)
                logger.error(f"Помилка при обробці callback запиту від користувача {update.callback_query.from_user.id}: {exception}")
    except TelegramAPIError:
        pass  # Ігнорування помилок у обробнику помилок

# Основна асинхронна функція для запуску бота
async def main():
    await dp.start_polling(bot)
    logger.info("Бот запущено та готовий до роботи.")

# Запуск бота при виконанні скрипту
if __name__ == '__main__':
    asyncio.run(main())