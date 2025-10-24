import logging
import sqlite3
import csv
import io
import asyncio
import random
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ParseMode, InputFile, ContentType, MediaGroup

load_dotenv()

API_TOKEN = os.environ.get('API_TOKEN')
if not API_TOKEN:
    raise ValueError("API_TOKEN environment variable is required!")

SUPER_ADMIN_ID = int(os.environ.get('SUPER_ADMIN_ID', '0'))
if SUPER_ADMIN_ID == 0:
    raise ValueError("SUPER_ADMIN_ID environment variable is required!")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

conn = sqlite3.connect('dating_database.db', check_same_thread=False)
conn.row_factory = sqlite3.Row
conn.execute('PRAGMA journal_mode=WAL;')
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    photos TEXT,
    age INTEGER,
    gender TEXT,
    description TEXT,
    seeking_gender TEXT,
    country TEXT,
    city TEXT,
    blocked INTEGER DEFAULT 0,
    premium INTEGER DEFAULT 0,
    premium_expiry DATETIME,
    invited_count INTEGER DEFAULT 0,
    last_boost DATETIME
)
''')

cursor.execute("PRAGMA table_info(users)")
columns = [col[1] for col in cursor.fetchall()]
if 'premium' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN premium INTEGER DEFAULT 0")
if 'premium_expiry' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN premium_expiry DATETIME")
if 'invited_count' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN invited_count INTEGER DEFAULT 0")
if 'last_boost' not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN last_boost DATETIME")

cursor.execute('CREATE INDEX IF NOT EXISTS idx_gender ON users(gender);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_seeking_gender ON users(seeking_gender);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_blocked ON users(blocked);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_country ON users(country);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_city ON users(city);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_premium ON users(premium);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_boost ON users(last_boost);')

cursor.execute('''
CREATE TABLE IF NOT EXISTS likes (
    from_user INTEGER,
    to_user INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (from_user, to_user)
)
''')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_from_user ON likes(from_user);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_to_user ON likes(to_user);')

cursor.execute('''
CREATE TABLE IF NOT EXISTS dislikes (
    from_user INTEGER,
    to_user INTEGER,
    PRIMARY KEY (from_user, to_user)
)
''')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_from_user_dis ON dislikes(from_user);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_to_user_dis ON dislikes(to_user);')

cursor.execute('''
CREATE TABLE IF NOT EXISTS skips (
    from_user INTEGER,
    to_user INTEGER,
    PRIMARY KEY (from_user, to_user)
)
''')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_from_user_skip ON skips(from_user);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_to_user_skip ON skips(to_user);')

cursor.execute('''
CREATE TABLE IF NOT EXISTS logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_user ON logs(user_id);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_log_timestamp ON logs(timestamp);')

cursor.execute('''
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS invitations (
    inviter_id INTEGER,
    invited_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (inviter_id, invited_id)
)
''')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_inviter_id ON invitations(inviter_id);')
cursor.execute('CREATE INDEX IF NOT EXISTS idx_invited_id ON invitations(invited_id);')

conn.commit()

cities_by_country = {
    'Россия': ['Москва', 'Санкт-Петербург', 'Новосибирск', 'Екатеринбург', 'Казань', 'Красноярск', 'Нижний Новгород', 'Челябинск', 'Уфа', 'Краснодар', 'Самара', 'Ростов-на-Дону', 'Омск', 'Воронеж', 'Пермь', 'Волгоград', 'Саратов', 'Тюмень', 'Тольятти', 'Махачкала'],
    'Таджикистан': ['Бохтар', 'Бустон', 'Вахдат', 'Гиссар', 'Гулистон', 'Душанбе', 'Истаравшан', 'Истиклол', 'Исфара', 'Канибадам', 'Куляб', 'Левакант', 'Нурек', 'Пенджикент', 'Рогун', 'Турсунзаде', 'Худжанд', 'Хорог'],
    'Узбекистан': ['Ташкент', 'Наманган', 'Андижан', 'Самарканд', 'Бухара', 'Карши', 'Коканд', 'Фергана', 'Маргилан', 'Нукус', 'Чирчик', 'Джизак', 'Ургенч', 'Навои', 'Термез', 'Алмалык', 'Шахрисабз', 'Бекабад', 'Шахрихан', 'Беруни'],
    'Кыргызстан': ['Айдаркен', 'Базар-Коргон', 'Балыкчы', 'Баткен', 'Бишкек', 'Джалал-Абад', 'Кадамжай', 'Каинды', 'Кант', 'Кара-Балта', 'Каракол', 'Кара-Куль', 'Кара-Суу', 'Кемин', 'Кербен', 'Кок-Джангак', 'Кочкор-Ата', 'Кызыл-Кия', 'Майлуу-Суу', 'Нарын', 'Ноокат', 'Орловка', 'Ош', 'Раззаков', 'Сулюкта', 'Талас', 'Таш-Кумыр', 'Токмак', 'Токтогул', 'Узген', 'Чолпон-Ата', 'Шамалды-Сай', 'Шопоков'],
    'Казахстан': ['Алматы', 'Астана', 'Шымкент', 'Актобе', 'Караганда', 'Тараз', 'Усть-Каменогорск', 'Павлодар', 'Атырау', 'Семей', 'Актау', 'Кызылорда', 'Костанай', 'Уральск', 'Туркестан', 'Петропавловск', 'Кокшетау', 'Темиртау', 'Талдыкорган', 'Экибастуз']
}

class SearchContext(StatesGroup):
    search = State()

class ViewingState(StatesGroup):
    likes = State()

def check_admin(user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    cursor.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
    return cursor.fetchone() is not None

def check_super_admin(user_id: int) -> bool:
    return user_id == SUPER_ADMIN_ID

def get_premium_status(user_id: int):
    cursor.execute("SELECT premium, premium_expiry FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    if not result:
        return False, None, False
    premium = result['premium']
    expiry = result['premium_expiry']
    needs_notify = False
    if premium and expiry:
        expiry_dt = datetime.fromisoformat(expiry)
        if datetime.now() >= expiry_dt:
            cursor.execute("UPDATE users SET premium=0, premium_expiry=NULL WHERE user_id=?", (user_id,))
            conn.commit()
            needs_notify = True
            return False, None, True
        expiry_str = expiry_dt.strftime("%Y-%m-%d %H:%M:%S")
        return True, expiry_str, False
    return bool(premium), None, False

async def check_premium(user_id: int) -> bool:
    is_prem, _, notify = get_premium_status(user_id)
    if notify:
        try:
            await bot.send_message(user_id, "🔥 Ваш VIP статус истёк! Продлите для безлимитных лайков и буста анкеты 💎\n\n💎 2 дня - 4 сомони\n💎💎 7 дней - 10 сомони\n💎💎💎 Месяц - 28 сомони\n\nНапишите @x_silence_x2 или @rajabov3 для покупки!")
        except Exception as e:
            logging.error(f"Failed to send expiry notification to {user_id}: {e}")
    return is_prem

async def check_like_limit(user_id: int) -> bool:
    if await check_premium(user_id):
        return True
    cursor.execute("""
        SELECT COUNT(*) FROM likes 
        WHERE from_user=? AND timestamp > datetime('now', '-1 day')
    """, (user_id,))
    count = cursor.fetchone()[0]
    return count < 30

def boost_profile(user_id: int):
    cursor.execute("UPDATE users SET last_boost=datetime('now') WHERE user_id=?", (user_id,))
    conn.commit()

def get_all_admins():
    cursor.execute("SELECT user_id FROM admins")
    admins = [row['user_id'] for row in cursor.fetchall()]
    admins.append(SUPER_ADMIN_ID)
    return admins

class ProfileForm(StatesGroup):
    name = State()
    photos = State()
    age = State()
    gender = State()
    description = State()
    seeking_gender = State()
    country = State()
    city = State()
    invite_code = State()

class EditForm(StatesGroup):
    name = State()
    photos = State()
    age = State()
    gender = State()
    description = State()
    seeking_gender = State()
    country = State()
    city = State()

class AdminForm(StatesGroup):
    view_user_id = State()
    message_text = State()
    broadcast_text = State()
    broadcast_media = State()
    broadcast_filter = State()
    search_name = State()
    search_age_min = State()
    search_age_max = State()
    search_gender = State()
    search_country = State()
    search_city = State()
    search_premium = State()
    likes_user_id = State()
    logs_user_id = State()
    appoint_admin_id = State()
    remove_admin_id = State()
    premium_user_id = State()
    premium_duration = State()
    cancel_premium_user_id = State()

class ReportForm(StatesGroup):
    reason = State()

@dp.message_handler(commands=['start'])
async def start(message: types.Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        args = message.get_args()
        if check_admin(user_id):
            await admin_panel(message)
            return
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        if cursor.fetchone():
            await show_menu(message)
        else:
            if args:
                async with state.proxy() as data:
                    data['invite_code'] = args
                await message.reply("Привет! Ты пришел по приглашению. Давай создадим твою анкету. Введи свое имя: 😊")
                await ProfileForm.name.set()
            else:
                await message.reply("Привет! Давай создадим твою анкету для знакомств. 🙂\nВведи свое имя:")
                await ProfileForm.name.set()
            cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'started_profile_creation'))
            conn.commit()
            await bot.send_message(SUPER_ADMIN_ID, f"Новый пользователь {message.from_user.username or 'без username'} начал создание анкеты.")
        await check_premium(user_id)
    except Exception as e:
        logging.error(f"Error in /start: {e}")
        await message.reply("Произошла ошибка. Попробуй позже. 😔")

@dp.message_handler(commands=['premium'])
async def premium_info(message: types.Message):
    try:
        user_id = message.from_user.id
        await check_premium(user_id)
        is_prem, exp, _ = get_premium_status(user_id)
        if is_prem:
            await message.reply(f"Ты премиум-пользователь до {exp}! 😎 Безлимитные лайки и буст анкеты!")
        else:
            await message.reply("🔥 Премиум-подписка дает безлимитные лайки и буст анкеты! Пригласи 5 друзей и получи премиум на 24 часа. 😊\n\n💎 2 дня - 4 сомони\n💎💎 7 дней - 10 сомони\n💎💎💎 Месяц - 28 сомони\n\nНапиши @x_silence_x2 или @rajabov3 для покупки! 💎")
    except Exception as e:
        logging.error(f"Error in /premium: {e}")
        await message.reply("Ошибка при проверке статуса премиум. 😔")

@dp.message_handler(Text(equals='Отмена'), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    await message.reply("Действие отменено. 😌", reply_markup=types.ReplyKeyboardRemove())
    await show_menu(message)

@dp.message_handler(Text(equals='Назад'), state=EditForm.states)
async def back_handler(message: types.Message, state: FSMContext):
    await state.finish()
    await show_edit_menu(message)

@dp.message_handler(Text(equals='Отмена'), state=AdminForm.states)
async def admin_cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    await message.reply("Действие отменено. 😌", reply_markup=types.ReplyKeyboardRemove())
    await admin_panel(message)

@dp.message_handler(Text(equals='Отмена'), state=ReportForm.states)
async def report_cancel_handler(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply("Жалоба отменена. 😌", reply_markup=types.ReplyKeyboardRemove())
    await show_menu(message)

@dp.message_handler(state=ProfileForm.name)
async def process_name(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await cancel_handler(message, state)
            return
        if not message.text.strip():
            await message.reply("Имя не может быть пустым. Попробуй снова: 🙂")
            return
        async with state.proxy() as data:
            data['name'] = message.text.strip()
            data['username'] = message.from_user.username or data['name']
            data['editing'] = data.get('editing', False)
            data['admin_editing'] = data.get('admin_editing', False)
            data['target_user_id'] = data.get('target_user_id', message.from_user.id)
            data['photos'] = []
        reply_markup = None
        if data['editing'] or data['admin_editing']:
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(KeyboardButton('Готово 📸'), KeyboardButton('Отмена'))
            reply_markup = keyboard
        else:
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(KeyboardButton('Готово 📸'))
            reply_markup = keyboard
        await message.reply("Теперь отправь свои фото (можно несколько, max 10): 📸\nКогда закончишь, нажми 'Готово 📸'", reply_markup=reply_markup)
        await ProfileForm.photos.set()
    except Exception as e:
        logging.error(f"Error in process_name: {e}")
        await message.reply("Ошибка при обработке имени. Попробуй снова. 😔")

@dp.message_handler(content_types=['photo'], state=ProfileForm.photos)
async def process_photo(message: types.Message, state: FSMContext):
    try:
        photo_id = message.photo[-1].file_id
        async with state.proxy() as data:
            if 'photos' not in data:
                data['photos'] = []
            if len(data['photos']) >= 10:
                await message.reply("Максимум 10 фото. Нажми 'Готово 📸'")
                return
            data['photos'].append(photo_id)
        await message.reply(f"Фото добавлено! ({len(data['photos'])}/10) 📸\nМожешь отправить еще или 'Готово 📸'")
    except Exception as e:
        logging.error(f"Error in process_photo: {e}")
        await message.reply("Ошибка при обработке фото. Отправь фото заново. 😔")

@dp.message_handler(state=ProfileForm.photos)
async def process_photos_done(message: types.Message, state: FSMContext):
    if message.text == 'Отмена':
        await cancel_handler(message, state)
        return
    if message.text == 'Готово 📸':
        async with state.proxy() as data:
            if len(data.get('photos', [])) == 0:
                await message.reply("Отправь хотя бы одно фото. 📸")
                return
        reply_markup = None
        if data.get('editing', False) or data.get('admin_editing', False):
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(KeyboardButton('Отмена'))
            reply_markup = keyboard
        await message.reply("Сколько тебе лет? 🔢", reply_markup=reply_markup)
        await ProfileForm.next()
    else:
        await message.reply("Это не фото. Отправь фото или 'Готово 📸'")

@dp.message_handler(state=ProfileForm.age)
async def process_age(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await cancel_handler(message, state)
            return
        age = int(message.text.strip())
        if age <= 0:
            await message.reply("Возраст должен быть больше 0. Попробуй снова: 🔢")
            return
        async with state.proxy() as data:
            data['age'] = age
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Мужской 🚹'), KeyboardButton('Женский 🚺'))
        if data.get('editing', False) or data.get('admin_editing', False):
            keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Укажи свой пол: 🚻", reply_markup=keyboard)
        await ProfileForm.next()
    except ValueError:
        await message.reply("Введи число. Попробуй снова: 🔢")
    except Exception as e:
        logging.error(f"Error in process_age: {e}")
        await message.reply("Ошибка при обработке возраста. 😔")

@dp.message_handler(state=ProfileForm.gender)
async def process_gender(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await cancel_handler(message, state)
            return
        gender = message.text.lower().replace(' ', '').replace('🚹', '').replace('🚺', '')
        if gender not in ['мужской', 'женский']:
            await message.reply("Выбери 'Мужской 🚹' или 'Женский 🚺'. Попробуй снова. 🙂")
            return
        async with state.proxy() as data:
            data['gender'] = gender
            data['editing'] = data.get('editing', False)
            data['admin_editing'] = data.get('admin_editing', False)
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Пропустить 📝'))
        if data['editing'] or data['admin_editing']:
            keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Расскажи о себе (до 500 символов) или пропусти: 📝", reply_markup=keyboard)
        await ProfileForm.next()
    except Exception as e:
        logging.error(f"Error in process_gender: {e}")
        await message.reply("Ошибка при обработке пола. 😔")

@dp.message_handler(state=ProfileForm.description)
async def process_description(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await cancel_handler(message, state)
            return
        if message.text == 'Пропустить 📝':
            desc = ''
        else:
            if not message.text.strip():
                await message.reply("Описание не может быть пустым, если не пропустить. Расскажи о себе или пропусти: 🙂")
                return
            desc = message.text.strip()[:500]
        async with state.proxy() as data:
            data['description'] = desc
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Мужской 🚹'), KeyboardButton('Женский 🚺'))
        if data.get('editing', False) or data.get('admin_editing', False):
            keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Кого ты ищешь? (пол) 🔍", reply_markup=keyboard)
        await ProfileForm.next()
    except Exception as e:
        logging.error(f"Error in process_description: {e}")
        await message.reply("Ошибка при обработке описания. 😔")

@dp.message_handler(state=ProfileForm.seeking_gender)
async def process_seeking_gender(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await cancel_handler(message, state)
            return
        seeking_gender = message.text.lower().replace(' ', '').replace('🚹', '').replace('🚺', '')
        if seeking_gender not in ['мужской', 'женский']:
            await message.reply("Выбери 'Мужской 🚹' или 'Женский 🚺'. Попробуй снова. 🙂")
            return
        async with state.proxy() as data:
            data['seeking_gender'] = seeking_gender
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        countries = ['Россия 🌍', 'Таджикистан 🌍', 'Узбекистан 🌍', 'Кыргызстан 🌍', 'Казахстан 🌍']
        for country in countries:
            keyboard.add(KeyboardButton(country))
        if data.get('editing', False) or data.get('admin_editing', False):
            keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Из какой ты страны? 🌍", reply_markup=keyboard)
        await ProfileForm.next()
    except Exception as e:
        logging.error(f"Error in process_seeking_gender: {e}")
        await message.reply("Ошибка при обработке. 😔")

@dp.message_handler(state=ProfileForm.country)
async def process_country(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await cancel_handler(message, state)
            return
        country = message.text.strip().replace(' 🌍', '')
        if country not in cities_by_country:
            await message.reply("Выбери из списка. Попробуй снова. 🙂")
            return
        async with state.proxy() as data:
            data['country'] = country
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for city in cities_by_country.get(country, []):
            keyboard.add(KeyboardButton(city + ' 🏙️'))
        if data.get('editing', False) or data.get('admin_editing', False):
            keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Выбери свой город: 🏙️", reply_markup=keyboard)
        await ProfileForm.next()
    except Exception as e:
        logging.error(f"Error in process_country: {e}")
        await message.reply("Ошибка при обработке страны. 😔")

@dp.message_handler(state=ProfileForm.city)
async def process_city(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await cancel_handler(message, state)
            return
        city = message.text.strip().replace(' 🏙️', '')
        async with state.proxy() as data:
            if city not in cities_by_country.get(data['country'], []):
                await message.reply("Выбери город из списка. Попробуй снова. 🙂")
                return
            data['city'] = city
            user_id = data['target_user_id']
            photos_json = json.dumps(data['photos'])
            premium = 0
            premium_expiry = None
            invite_code = data.get('invite_code')
            if invite_code:
                try:
                    inviter_id = int(invite_code)
                    cursor.execute("SELECT 1 FROM users WHERE user_id=?", (inviter_id,))
                    if cursor.fetchone():
                        cursor.execute("INSERT OR IGNORE INTO invitations (inviter_id, invited_id) VALUES (?, ?)", (inviter_id, user_id))
                        conn.commit()
                        cursor.execute("SELECT COUNT(*) FROM invitations WHERE inviter_id=?", (inviter_id,))
                        invited_count_result = cursor.fetchone()
                        invited_count = invited_count_result[0]
                        cursor.execute("UPDATE users SET invited_count=? WHERE user_id=?", (invited_count, inviter_id))
                        conn.commit()
                        if invited_count >= 5:
                            cursor.execute("SELECT premium_expiry FROM users WHERE user_id=?", (inviter_id,))
                            current_expiry_result = cursor.fetchone()
                            current_expiry = current_expiry_result['premium_expiry'] if current_expiry_result else None
                            new_expiry = (datetime.fromisoformat(current_expiry) + timedelta(days=1)) if current_expiry else (datetime.now() + timedelta(days=1))
                            cursor.execute("UPDATE users SET premium=1, premium_expiry=? WHERE user_id=?", (new_expiry.isoformat(), inviter_id))
                            conn.commit()
                            await bot.send_message(inviter_id, "Поздравляем! Ты пригласил 5 друзей и получил премиум на 24 часа! 😎")
                except ValueError:
                    pass
            cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, name, photos, age, gender, description, seeking_gender, country, city, blocked, premium, premium_expiry, invited_count, last_boost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT blocked FROM users WHERE user_id=?), 0), ?, ?, COALESCE((SELECT invited_count FROM users WHERE user_id=?), 0), datetime('now'))
            ''', (user_id, data['username'], data['name'], photos_json, data['age'], data['gender'],
                  data['description'], data['seeking_gender'], data['country'], data['city'], user_id, premium, premium_expiry, user_id))
            conn.commit()
            action = 'profile_created' if not data.get('editing', False) and not data.get('admin_editing', False) else 'profile_edited'
            cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, action))
            conn.commit()
            if action == 'profile_created':
                await bot.send_message(SUPER_ADMIN_ID, f"Новый пользователь {data['username']} создал анкету.")
                boost_profile(user_id)
        await state.finish()
        msg = "Анкета обновлена! Теперь можно искать знакомства. 🙂" if data.get('editing', False) or data.get('admin_editing', False) else "Анкета создана! 🙂"
        await message.reply(msg, reply_markup=types.ReplyKeyboardRemove())
        if data.get('admin_editing', False):
            await admin_panel(message)
        else:
            await show_menu(message)
    except Exception as e:
        logging.error(f"Error in process_city: {e}")
        await message.reply("Ошибка при сохранении анкеты. Попробуй заново /start 😔")

async def show_menu(message: types.Message):
    try:
        user_id = message.from_user.id
        await check_premium(user_id)
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row(KeyboardButton('Искать анкеты 🔍'), KeyboardButton('Кто меня лайкнул ❤️'))
        keyboard.row(KeyboardButton('Моя анкета 👤'), KeyboardButton('Редактировать анкету ✏️'))
        keyboard.row(KeyboardButton('Помощь ❓'), KeyboardButton('Мой статус 💎'))
        await message.reply("Вы в главном меню: Выбери действие! 🙂", reply_markup=keyboard)
    except Exception as e:
        logging.error(f"Error in show_menu: {e}")

@dp.message_handler(Text(equals='Мой статус 💎'))
async def view_status(message: types.Message):
    try:
        user_id = message.from_user.id
        await check_premium(user_id)
        cursor.execute("SELECT invited_count, premium, premium_expiry FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        if not result:
            await message.reply("Анкета не найдена. Создай /start 😔")
            return
        invited_count = result['invited_count']
        is_prem, exp, _ = get_premium_status(user_id)
        invite_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
        status = "Обычный" if not is_prem else f"Премиум до {exp}"
        await message.reply(f"Твой статус: {status}\nПриглашено друзей: {invited_count}/5\nТвоя ссылка для приглашения: {invite_link}")
        await message.reply("🔥 VIP статус - лучший выбор для знакомств!\nБезлимитные лайки, буст анкеты, приоритет в рекомендациях! 🌟\n\n💎 2 дня - 4 сомони\n💎💎 7 дней - 10 сомони\n💎💎💎 Месяц - 28 сомони")
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(InlineKeyboardButton("Купить у @x_silence_x2 💎", url="https://t.me/x_silence_x2"))
        keyboard.add(InlineKeyboardButton("Купить у @rajabov3 💎", url="https://t.me/rajabov3"))
        await message.reply("Выберите продавца для покупки VIP:", reply_markup=keyboard)
    except Exception as e:
        logging.error(f"Error in view_status: {e}")
        await message.reply("Ошибка при просмотре статуса. 😔")

@dp.message_handler(Text(equals='Моя анкета 👤'))
async def view_own_profile(message: types.Message):
    try:
        user_id = message.from_user.id
        await check_premium(user_id)
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        profile = cursor.fetchone()
        if not profile:
            await message.reply("Анкета не найдена. Создай /start 😔")
            return
        blocked = profile['blocked']
        if blocked:
            await message.reply("Твоя анкета заблокирована. Обратитесь к админу. 🚫")
            return
        photos_json = profile['photos']
        photos = json.loads(photos_json or '[]')
        if not photos:
            await message.reply("Нет фото в анкете. 😔")
            return
        description = profile['description']
        desc_line = f"{description}\n" if description else ""
        premium = profile['premium']
        status = "💎 VIP" if premium else ""
        name = profile['name']
        age = profile['age']
        gender = profile['gender']
        seeking_gender = profile['seeking_gender']
        country = profile['country']
        city = profile['city']
        caption = f"Твоя анкета:\n{name}, {age} лет, {gender.capitalize()} {status}\n{desc_line}Ищешь: {seeking_gender.capitalize()}\nСтрана: {country}\nГород: {city}"
        media = MediaGroup()
        for i, photo in enumerate(photos):
            if i == 0:
                media.attach_photo(photo, caption=caption, parse_mode=ParseMode.HTML)
            else:
                media.attach_photo(photo)
        await bot.send_media_group(message.chat.id, media)
    except Exception as e:
        logging.error(f"Error in view_own_profile: {e}")
        await message.reply("Ошибка при просмотре анкеты. 😔")

async def show_edit_menu(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('Имя ✏️', 'Фото 📸', 'Возраст 🔢')
    keyboard.row('Пол 🚻', 'Описание 📝', 'Пол поиска 🔍')
    keyboard.row('Страна 🌍', 'Город 🏙️')
    keyboard.row('Завершить редактирование ✅')
    await message.reply("Что хочешь изменить?", reply_markup=keyboard)

@dp.message_handler(Text(equals='Редактировать анкету ✏️'))
async def edit_profile(message: types.Message):
    try:
        user_id = message.from_user.id
        cursor.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        if not result:
            await message.reply("Анкета не найдена. Сначала создай ее с /start 😔")
            return
        blocked = result['blocked']
        if blocked:
            await message.reply("Твоя анкета заблокирована. Нельзя редактировать. 🚫")
            return
        await show_edit_menu(message)
    except Exception as e:
        logging.error(f"Error in edit_profile: {e}")
        await message.reply("Ошибка при редактировании. 😔")

@dp.message_handler(Text(equals='Завершить редактирование ✅'))
async def finish_edit(message: types.Message):
    await show_menu(message)

@dp.message_handler(Text(equals='Имя ✏️'))
async def edit_name_start(message: types.Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Назад ⬅️'))
    await message.reply("Введи новое имя:", reply_markup=keyboard)
    await EditForm.name.set()

@dp.message_handler(state=EditForm.name)
async def edit_name(message: types.Message, state: FSMContext):
    if message.text == 'Назад ⬅️':
        await back_handler(message, state)
        return
    if not message.text.strip():
        await message.reply("Имя не может быть пустым.")
        return
    user_id = message.from_user.id
    cursor.execute("UPDATE users SET name=? WHERE user_id=?", (message.text.strip(), user_id))
    conn.commit()
    cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'edited_name'))
    conn.commit()
    await message.reply("Имя обновлено! 🙂")
    await state.finish()
    await show_edit_menu(message)

@dp.message_handler(Text(equals='Фото 📸'))
async def edit_photo_start(message: types.Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Готово 📸'), KeyboardButton('Назад ⬅️'))
    await message.reply("Отправь новые фото (можно несколько, max 10), заменят старые: 📸\nКогда закончишь, нажми 'Готово 📸'", reply_markup=keyboard)
    await EditForm.photos.set()
    async with state.proxy() as data:
        data['photos'] = []

@dp.message_handler(content_types=['photo'], state=EditForm.photos)
async def edit_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    async with state.proxy() as data:
        if len(data['photos']) >= 10:
            await message.reply("Максимум 10 фото. Нажми 'Готово 📸'")
            return
        data['photos'].append(photo_id)
    await message.reply(f"Фото добавлено! ({len(data['photos'])}/10) 📸\nМожешь отправить еще или 'Готово 📸'")

@dp.message_handler(state=EditForm.photos)
async def edit_photos_done(message: types.Message, state: FSMContext):
    if message.text == 'Назад ⬅️':
        await back_handler(message, state)
        return
    if message.text == 'Готово 📸':
        async with state.proxy() as data:
            if len(data['photos']) == 0:
                await message.reply("Отправь хотя бы одно фото. 📸")
                return
            user_id = message.from_user.id
            photos_json = json.dumps(data['photos'])
            cursor.execute("UPDATE users SET photos=? WHERE user_id=?", (photos_json, user_id))
            conn.commit()
            cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'edited_photos'))
            conn.commit()
            await message.reply("Фото обновлены! 🙂")
            await state.finish()
            await show_edit_menu(message)
    else:
        await message.reply("Это не фото. Отправь фото или 'Готово 📸'")

@dp.message_handler(Text(equals='Возраст 🔢'))
async def edit_age_start(message: types.Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Назад ⬅️'))
    await message.reply("Введи новый возраст:", reply_markup=keyboard)
    await EditForm.age.set()

@dp.message_handler(state=EditForm.age)
async def edit_age(message: types.Message, state: FSMContext):
    if message.text == 'Назад ⬅️':
        await back_handler(message, state)
        return
    try:
        age = int(message.text.strip())
        if age <= 0:
            await message.reply("Возраст должен быть больше 0.")
            return
        user_id = message.from_user.id
        cursor.execute("UPDATE users SET age=? WHERE user_id=?", (age, user_id))
        conn.commit()
        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'edited_age'))
        conn.commit()
        await message.reply("Возраст обновлен! 🙂")
        await state.finish()
        await show_edit_menu(message)
    except ValueError:
        await message.reply("Введи число.")

@dp.message_handler(Text(equals='Пол 🚻'))
async def edit_gender_start(message: types.Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Мужской 🚹'), KeyboardButton('Женский 🚺'))
    keyboard.add(KeyboardButton('Назад ⬅️'))
    await message.reply("Выбери новый пол:", reply_markup=keyboard)
    await EditForm.gender.set()

@dp.message_handler(state=EditForm.gender)
async def edit_gender(message: types.Message, state: FSMContext):
    if message.text == 'Назад ⬅️':
        await back_handler(message, state)
        return
    gender = message.text.lower().replace(' ', '').replace('🚹', '').replace('🚺', '')
    if gender not in ['мужской', 'женский']:
        await message.reply("Выбери 'Мужской 🚹' или 'Женский 🚺'.")
        return
    user_id = message.from_user.id
    cursor.execute("UPDATE users SET gender=? WHERE user_id=?", (gender, user_id))
    conn.commit()
    cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'edited_gender'))
    conn.commit()
    await message.reply("Пол обновлен! 🙂")
    await state.finish()
    await show_edit_menu(message)

@dp.message_handler(Text(equals='Описание 📝'))
async def edit_description_start(message: types.Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Пропустить 📝'), KeyboardButton('Назад ⬅️'))
    await message.reply("Введи новое описание или пропусти:", reply_markup=keyboard)
    await EditForm.description.set()

@dp.message_handler(state=EditForm.description)
async def edit_description(message: types.Message, state: FSMContext):
    if message.text == 'Назад ⬅️':
        await back_handler(message, state)
        return
    if message.text == 'Пропустить 📝':
        desc = ''
    else:
        desc = message.text.strip()[:500]
        if not desc:
            await message.reply("Если не пропустить, описание не может быть пустым.")
            return
    user_id = message.from_user.id
    cursor.execute("UPDATE users SET description=? WHERE user_id=?", (desc, user_id))
    conn.commit()
    cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'edited_description'))
    conn.commit()
    await message.reply("Описание обновлено! 🙂")
    await state.finish()
    await show_edit_menu(message)

@dp.message_handler(Text(equals='Пол поиска 🔍'))
async def edit_seeking_gender_start(message: types.Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Мужской 🚹'), KeyboardButton('Женский 🚺'))
    keyboard.add(KeyboardButton('Назад ⬅️'))
    await message.reply("Выбери новый пол поиска:", reply_markup=keyboard)
    await EditForm.seeking_gender.set()

@dp.message_handler(state=EditForm.seeking_gender)
async def edit_seeking_gender(message: types.Message, state: FSMContext):
    if message.text == 'Назад ⬅️':
        await back_handler(message, state)
        return
    seeking_gender = message.text.lower().replace(' ', '').replace('🚹', '').replace('🚺', '')
    if seeking_gender not in ['мужской', 'женский']:
        await message.reply("Выбери 'Мужской 🚹' или 'Женский 🚺'.")
        return
    user_id = message.from_user.id
    cursor.execute("UPDATE users SET seeking_gender=? WHERE user_id=?", (seeking_gender, user_id))
    conn.commit()
    cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'edited_seeking_gender'))
    conn.commit()
    await message.reply("Пол поиска обновлен! 🙂")
    await state.finish()
    await show_edit_menu(message)

@dp.message_handler(Text(equals='Страна 🌍'))
async def edit_country_start(message: types.Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    countries = ['Россия 🌍', 'Таджикистан 🌍', 'Узбекистан 🌍', 'Кыргызстан 🌍', 'Казахстан 🌍']
    for country in countries:
        keyboard.add(KeyboardButton(country))
    keyboard.add(KeyboardButton('Назад ⬅️'))
    await message.reply("Выбери новую страну:", reply_markup=keyboard)
    await EditForm.country.set()

@dp.message_handler(state=EditForm.country)
async def edit_country(message: types.Message, state: FSMContext):
    if message.text == 'Назад ⬅️':
        await back_handler(message, state)
        return
    country = message.text.strip().replace(' 🌍', '')
    if country not in cities_by_country:
        await message.reply("Выбери из списка.")
        return
    user_id = message.from_user.id
    cursor.execute("UPDATE users SET country=? WHERE user_id=?", (country, user_id))
    conn.commit()
    cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'edited_country'))
    conn.commit()
    await message.reply("Страна обновлена! 🙂 (Возможно, обнови город, если нужно.)")
    await state.finish()
    await show_edit_menu(message)

@dp.message_handler(Text(equals='Город 🏙️'))
async def edit_city_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    cursor.execute("SELECT country FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    country = result['country'] if result else None
    if not country:
        await message.reply("Сначала укажи страну.")
        return
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for city in cities_by_country.get(country, []):
        keyboard.add(KeyboardButton(city + ' 🏙️'))
    keyboard.add(KeyboardButton('Назад ⬅️'))
    await message.reply("Выбери новый город:", reply_markup=keyboard)
    await EditForm.city.set()

@dp.message_handler(state=EditForm.city)
async def edit_city(message: types.Message, state: FSMContext):
    if message.text == 'Назад ⬅️':
        await back_handler(message, state)
        return
    user_id = message.from_user.id
    cursor.execute("SELECT country FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    country = result['country'] if result else None
    city = message.text.strip().replace(' 🏙️', '')
    if city not in cities_by_country.get(country, []):
        await message.reply("Выбери из списка для твоей страны.")
        return
    cursor.execute("UPDATE users SET city=? WHERE user_id=?", (city, user_id))
    conn.commit()
    cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'edited_city'))
    conn.commit()
    await message.reply("Город обновлен! 🙂")
    await state.finish()
    await show_edit_menu(message)

@dp.message_handler(Text(equals='Помощь ❓'))
async def help_command(message: types.Message):
    try:
        help_text = ("Помощь ❓:\n"
                     "- Искать анкеты 🔍: Просматривай и лайкай! 👀\n"
                     "- Кто меня лайкнул ❤️: Посмотри, кто заинтересован в тебе.\n"
                     "- Моя анкета 👤: Посмотри на себя. 👤\n"
                     "- Редактировать ✏️: Измени данные. ✏️\n"
                     "- Мой статус 💎: Проверь премиум и приглашения.\n"
                     "- Если mutual лайк - бот отправит контакты! 🤝\n"
                     "Удачи в поисках! 👍")
        await message.reply(help_text)
    except Exception as e:
        logging.error(f"Error in help_command: {e}")

@dp.message_handler(Text(equals='Искать анкеты 🔍'))
async def search_profiles(message: types.Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        await check_premium(user_id)
        is_admin_flag = check_admin(user_id)
        cursor.execute("SELECT seeking_gender, blocked, city, premium FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        if not result:
            return
        seeking_gender = result['seeking_gender']
        blocked = result['blocked']
        user_city = result['city']
        premium = result['premium']
        if blocked and not is_admin_flag:
            await message.reply("Ты заблокирован. Нельзя искать анкеты. 🚫")
            return
        profile = None
        if not is_admin_flag:
            cursor.execute('''
            SELECT * FROM users 
            WHERE gender = ? AND user_id != ? AND blocked = 0 AND city = ?
            AND user_id NOT IN (SELECT to_user FROM likes WHERE from_user = ?)
            AND user_id NOT IN (SELECT to_user FROM dislikes WHERE from_user = ?)
            AND user_id NOT IN (SELECT to_user FROM skips WHERE from_user = ?)
            ORDER BY premium DESC, last_boost DESC, RANDOM() LIMIT 1
            ''', (seeking_gender, user_id, user_city, user_id, user_id, user_id))
            profile = cursor.fetchone()
        if not profile:
            cursor.execute('''
            SELECT * FROM users 
            WHERE gender = ? AND user_id != ? AND (blocked = 0 OR ? = 1)
            AND (user_id NOT IN (SELECT to_user FROM likes WHERE from_user = ?) OR ? = 1)
            AND (user_id NOT IN (SELECT to_user FROM dislikes WHERE from_user = ?) OR ? = 1)
            AND (user_id NOT IN (SELECT to_user FROM skips WHERE from_user = ?) OR ? = 1)
            ORDER BY premium DESC, last_boost DESC, RANDOM() LIMIT 1
            ''', (seeking_gender, user_id, is_admin_flag, user_id, is_admin_flag, user_id, is_admin_flag, user_id, is_admin_flag))
            profile = cursor.fetchone()

        if not profile:
            await message.reply("Нет подходящих анкет сейчас. Попробуй позже или пригласи друзей! 🔍")
            return

        to_user_id = profile['user_id']
        name = profile['name']
        photos_json = profile['photos']
        age = profile['age']
        gender = profile['gender']
        description = profile['description']
        country = profile['country']
        city = profile['city']
        blocked = profile['blocked']
        premium = profile['premium']
        photos = json.loads(photos_json or '[]')
        if not photos:
            await search_profiles(message, state)
            return
        desc_line = f"{description}\n" if description else ""
        status = "💎 VIP" if premium else ""
        caption = f"{name}, {age} лет, {gender.capitalize()} {status}\n{desc_line}Страна: {country}\nГород: {city}"
        media = MediaGroup()
        for i, photo in enumerate(photos):
            if i == 0:
                media.attach_photo(photo, caption=caption, parse_mode=ParseMode.HTML)
            else:
                media.attach_photo(photo)
        await bot.send_media_group(message.chat.id, media)
        keyboard = InlineKeyboardMarkup(row_width=2)
        if is_admin_flag:
            keyboard.add(
                InlineKeyboardButton("Блокировать 🔒" if not blocked else "Разблокировать 🔓",
                                     callback_data=f"admin_block_{to_user_id}_{blocked}"),
                InlineKeyboardButton("Удалить 🗑️", callback_data=f"admin_delete_{to_user_id}"),
                InlineKeyboardButton("Редактировать ✏️", callback_data=f"admin_edit_{to_user_id}"),
                InlineKeyboardButton("Отправить сообщение 📩", callback_data=f"admin_message_{to_user_id}"),
                InlineKeyboardButton("Следующая ⏭️", callback_data=f"admin_next")
            )
        else:
            keyboard.add(
                InlineKeyboardButton("Лайк 👍", callback_data=f"like_{to_user_id}"),
                InlineKeyboardButton("Дизлайк 👎", callback_data=f"dislike_{to_user_id}"),
                InlineKeyboardButton("Пропустить ⏭️", callback_data=f"skip_{to_user_id}"),
                InlineKeyboardButton("Жалоба ⚠️", callback_data=f"report_{to_user_id}"),
                InlineKeyboardButton("Меню 📋", callback_data="back_to_menu")
            )
        await bot.send_message(message.chat.id, "Действия:", reply_markup=keyboard)
        await SearchContext.search.set()
    except Exception as e:
        logging.error(f"Error in search_profiles: {e}")

@dp.callback_query_handler(lambda c: c.data == 'admin_next', state='*')
async def admin_next_profile(callback_query: types.CallbackQuery):
    if not check_admin(callback_query.from_user.id):
        return
    try:
        await callback_query.answer("Следующая... ⏭️")
        await search_profiles(callback_query.message, None)
    except Exception as e:
        logging.error(f"Error in admin_next_profile: {e}")
        await callback_query.answer("Ошибка. 😔")

@dp.callback_query_handler(lambda c: c.data.startswith('like_'), state=SearchContext.search)
async def process_like_search(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await state.finish()
        to_user_id = int(callback_query.data.split('_')[1])
        from_user_id = callback_query.from_user.id

        cursor.execute("SELECT blocked, premium FROM users WHERE user_id=?", (from_user_id,))
        result = cursor.fetchone()
        if result:
            blocked_from = result['blocked']
            premium = result['premium']
        if blocked_from:
            await callback_query.answer("Ты заблокирован. Нельзя лайкать. 🚫")
            return

        cursor.execute("SELECT blocked FROM users WHERE user_id=?", (to_user_id,))
        blocked_to_result = cursor.fetchone()
        blocked_to = blocked_to_result['blocked'] if blocked_to_result else None
        if blocked_to:
            await callback_query.answer("Этот пользователь заблокирован. 🚫")
            await search_profiles(callback_query.message, None)
            return

        if not await check_like_limit(from_user_id):
            await callback_query.answer("Лимит лайков (30 в день). Стань премиум! 💎")
            return

        cursor.execute("INSERT OR IGNORE INTO likes (from_user, to_user) VALUES (?, ?)", (from_user_id, to_user_id))
        conn.commit()

        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (from_user_id, f'liked_{to_user_id}'))
        conn.commit()

        cursor.execute("SELECT name, username, gender FROM users WHERE user_id=?", (from_user_id,))
        from_profile = cursor.fetchone()
        if not from_profile:
            raise ValueError("From user not found")
        from_name = from_profile['name']
        from_username = from_profile['username']
        from_gender = from_profile['gender']

        cursor.execute("SELECT name, username, gender FROM users WHERE user_id=?", (to_user_id,))
        to_profile = cursor.fetchone()
        if not to_profile:
            raise ValueError("To user not found")
        to_name = to_profile['name']
        to_username = to_profile['username']
        to_gender = to_profile['gender']

        if to_gender == 'женский':
            like_msg = f"Ты понравилась {from_name}! Проверь анкеты, чтобы ответить. 👀"
        else:
            like_msg = f"Ты понравился {from_name}! Проверь анкеты, чтобы ответить. 👀"
        await bot.send_message(to_user_id, like_msg)

        cursor.execute("SELECT * FROM likes WHERE from_user = ? AND to_user = ?", (to_user_id, from_user_id))
        if cursor.fetchone():
            await bot.send_message(from_user_id, f"Взаимный лайк с {to_name}! Напиши ему/ей в ЛС: @{to_username} 🤝")
            await bot.send_message(to_user_id, f"Взаимный лайк с {from_name}! Напиши ему/ей в ЛС: @{from_username} 🤝")
            await bot.send_message(SUPER_ADMIN_ID, f"Новый mutual лайк между {from_user_id} и {to_user_id}.")

        await callback_query.answer("Лайк поставлен! 👍")
        await search_profiles(callback_query.message, None)
    except Exception as e:
        logging.error(f"Error in process_like_search: {e}")
        await callback_query.answer("Ошибка при лайке. 😔")

@dp.callback_query_handler(lambda c: c.data.startswith('like_'), state=ViewingState.likes)
async def process_like_likes(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await state.finish()
        to_user_id = int(callback_query.data.split('_')[1])
        from_user_id = callback_query.from_user.id

        cursor.execute("SELECT blocked, premium FROM users WHERE user_id=?", (from_user_id,))
        result = cursor.fetchone()
        if result:
            blocked_from = result['blocked']
            premium = result['premium']
        if blocked_from:
            await callback_query.answer("Ты заблокирован. Нельзя лайкать. 🚫")
            return

        cursor.execute("SELECT blocked FROM users WHERE user_id=?", (to_user_id,))
        blocked_to_result = cursor.fetchone()
        blocked_to = blocked_to_result['blocked'] if blocked_to_result else None
        if blocked_to:
            await callback_query.answer("Этот пользователь заблокирован. 🚫")
            await view_incoming_likes(callback_query.message)
            return

        if not await check_like_limit(from_user_id):
            await callback_query.answer("Лимит лайков (30 в день). Стань премиум! 💎")
            return

        cursor.execute("INSERT OR IGNORE INTO likes (from_user, to_user) VALUES (?, ?)", (from_user_id, to_user_id))
        conn.commit()

        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (from_user_id, f'liked_{to_user_id}'))
        conn.commit()

        cursor.execute("SELECT name, username, gender FROM users WHERE user_id=?", (from_user_id,))
        from_profile = cursor.fetchone()
        if not from_profile:
            raise ValueError("From user not found")
        from_name = from_profile['name']
        from_username = from_profile['username']
        from_gender = from_profile['gender']

        cursor.execute("SELECT name, username, gender FROM users WHERE user_id=?", (to_user_id,))
        to_profile = cursor.fetchone()
        if not to_profile:
            raise ValueError("To user not found")
        to_name = to_profile['name']
        to_username = to_profile['username']
        to_gender = to_profile['gender']

        if to_gender == 'женский':
            like_msg = f"Ты понравилась {from_name}! Проверь анкеты, чтобы ответить. 👀"
        else:
            like_msg = f"Ты понравился {from_name}! Проверь анкеты, чтобы ответить. 👀"
        await bot.send_message(to_user_id, like_msg)

        cursor.execute("SELECT * FROM likes WHERE from_user = ? AND to_user = ?", (to_user_id, from_user_id))
        if cursor.fetchone():
            await bot.send_message(from_user_id, f"Взаимный лайк с {to_name}! Напиши ему/ей в ЛС: @{to_username} 🤝")
            await bot.send_message(to_user_id, f"Взаимный лайк с {from_name}! Напиши ему/ей в ЛС: @{from_username} 🤝")
            await bot.send_message(SUPER_ADMIN_ID, f"Новый mutual лайк между {from_user_id} и {to_user_id}.")

        await callback_query.answer("Лайк поставлен! 👍")
        await view_incoming_likes(callback_query.message)
    except Exception as e:
        logging.error(f"Error in process_like_likes: {e}")
        await callback_query.answer("Ошибка при лайке. 😔")

@dp.callback_query_handler(lambda c: c.data.startswith('dislike_'), state=SearchContext.search)
async def process_dislike_search(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await state.finish()
        to_user_id = int(callback_query.data.split('_')[1])
        from_user_id = callback_query.from_user.id

        cursor.execute("INSERT OR IGNORE INTO dislikes (from_user, to_user) VALUES (?, ?)", (from_user_id, to_user_id))
        conn.commit()

        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (from_user_id, f'disliked_{to_user_id}'))
        conn.commit()

        await callback_query.answer("Дизлайк! Следующая... 👎")
        await search_profiles(callback_query.message, None)
    except Exception as e:
        logging.error(f"Error in process_dislike_search: {e}")
        await callback_query.answer("Ошибка при дизлайке. 😔")

@dp.callback_query_handler(lambda c: c.data.startswith('dislike_'), state=ViewingState.likes)
async def process_dislike_likes(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await state.finish()
        to_user_id = int(callback_query.data.split('_')[1])
        from_user_id = callback_query.from_user.id

        cursor.execute("INSERT OR IGNORE INTO dislikes (from_user, to_user) VALUES (?, ?)", (from_user_id, to_user_id))
        conn.commit()

        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (from_user_id, f'disliked_{to_user_id}'))
        conn.commit()

        await callback_query.answer("Дизлайк! Следующий... 👎")
        await view_incoming_likes(callback_query.message)
    except Exception as e:
        logging.error(f"Error in process_dislike_likes: {e}")
        await callback_query.answer("Ошибка при дизлайке. 😔")

@dp.callback_query_handler(lambda c: c.data.startswith('skip_'), state=SearchContext.search)
async def process_skip_search(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await state.finish()
        to_user_id = int(callback_query.data.split('_')[1])
        from_user_id = callback_query.from_user.id

        cursor.execute("INSERT OR IGNORE INTO skips (from_user, to_user) VALUES (?, ?)", (from_user_id, to_user_id))
        conn.commit()

        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (from_user_id, f'skipped_{to_user_id}'))
        conn.commit()

        await callback_query.answer("Пропущено! Следующая... ⏭️")
        await search_profiles(callback_query.message, None)
    except Exception as e:
        logging.error(f"Error in process_skip_search: {e}")
        await callback_query.answer("Ошибка при пропуске. 😔")

@dp.callback_query_handler(lambda c: c.data == 'back_to_menu', state='*')
async def back_to_menu(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await state.finish()
        await callback_query.answer("Возврат в меню. 📋")
        await show_menu(callback_query.message)
    except Exception as e:
        logging.error(f"Error in back_to_menu: {e}")
        await callback_query.answer("Ошибка. 😔")

@dp.callback_query_handler(lambda c: c.data.startswith('report_'), state='*')
async def start_report(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        current_state = await state.get_state()
        to_user_id = int(callback_query.data.split('_')[1])
        from_user_id = callback_query.from_user.id
        async with state.proxy() as data:
            data['reported_user_id'] = to_user_id
            data['from_state'] = current_state
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await callback_query.message.reply("Опишите причину жалобы (только текст):", reply_markup=keyboard)
        await ReportForm.reason.set()
        await callback_query.answer()
    except Exception as e:
        logging.error(f"Error in start_report: {e}")
        await callback_query.answer("Ошибка. 😔")

@dp.message_handler(content_types=[ContentType.PHOTO, ContentType.VIDEO, ContentType.DOCUMENT, ContentType.STICKER, ContentType.VOICE, ContentType.AUDIO], state=ReportForm.reason)
async def invalid_report_media(message: types.Message, state: FSMContext):
    await message.reply("Для жалобы нужен только текст. Отправьте текст или 'Отмена'.")
    await ReportForm.reason.set()

@dp.message_handler(state=ReportForm.reason)
async def process_report(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await report_cancel_handler(message, state)
            return
        reason = message.text.strip()
        if not reason:
            await message.reply("Причина не может быть пустой.")
            return
        async with state.proxy() as data:
            reported_user_id = data['reported_user_id']
            from_state = data.get('from_state')
            reporter_id = message.from_user.id
        cursor.execute("SELECT name FROM users WHERE user_id=?", (reporter_id,))
        reporter_result = cursor.fetchone()
        reporter_name = reporter_result['name'] if reporter_result else "Unknown"
        cursor.execute("SELECT name FROM users WHERE user_id=?", (reported_user_id,))
        reported_result = cursor.fetchone()
        reported_name = reported_result['name'] if reported_result else "Unknown"
        report_msg = f"⚠️ Новая жалоба!\nОт: {reporter_name} (ID: {reporter_id})\nНа: {reported_name} (ID: {reported_user_id})\nПричина: {reason}"
        admins = get_all_admins()
        for admin_id in admins:
            try:
                await bot.send_message(admin_id, report_msg)
            except Exception as e:
                logging.error(f"Failed to send report to admin {admin_id}: {e}")
        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (reporter_id, f'reported_{reported_user_id}_{reason[:50]}'))
        conn.commit()
        await message.reply("Жалоба отправлена администраторам. Спасибо! 🙏", reply_markup=types.ReplyKeyboardRemove())
        if from_state == SearchContext.search.state:
            await search_profiles(message, None)
        elif from_state == ViewingState.likes.state:
            await view_incoming_likes(message)
        else:
            await show_menu(message)
        await state.finish()
    except Exception as e:
        logging.error(f"Error in process_report: {e}")
        await message.reply("Ошибка при отправке жалобы. 😔")
        await state.finish()

@dp.message_handler(Text(equals='Кто меня лайкнул ❤️'))
async def view_incoming_likes(message: types.Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        await check_premium(user_id)
        cursor.execute("SELECT blocked FROM users WHERE user_id=?", (user_id,))
        blocked_result = cursor.fetchone()
        blocked = blocked_result['blocked'] if blocked_result else None
        if blocked:
            await message.reply("Ты заблокирован. Нельзя просматривать лайки. 🚫")
            return
        cursor.execute('''
        SELECT * FROM users 
        WHERE user_id IN (SELECT from_user FROM likes WHERE to_user = ?)
        AND blocked = 0
        ORDER BY premium DESC, last_boost DESC, RANDOM() LIMIT 1
        ''', (user_id,))
        profile = cursor.fetchone()
        if not profile:
            await message.reply("Нет лайков пока. Продолжай искать! 😔")
            return
        to_user_id = profile['user_id']
        name = profile['name']
        photos_json = profile['photos']
        age = profile['age']
        gender = profile['gender']
        description = profile['description']
        country = profile['country']
        city = profile['city']
        premium = profile['premium']
        photos = json.loads(photos_json or '[]')
        if not photos:
            await view_incoming_likes(message, state)
            return
        cursor.execute("SELECT 1 FROM likes WHERE from_user=? AND to_user=?", (user_id, to_user_id))
        is_mutual = cursor.fetchone() is not None
        desc_line = f"{description}\n" if description else ""
        status = "💎 VIP" if premium else ""
        mutual_text = "\n🤝 Взаимный лайк! Напишите в ЛС!" if is_mutual else ""
        caption = f"{name}, {age} лет, {gender.capitalize()} {status}\n{desc_line}Страна: {country}\nГород: {city}\nЭтот пользователь лайкнул тебя!{mutual_text}"
        media = MediaGroup()
        for i, photo in enumerate(photos):
            if i == 0:
                media.attach_photo(photo, caption=caption, parse_mode=ParseMode.HTML)
            else:
                media.attach_photo(photo)
        await bot.send_media_group(message.chat.id, media)
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("Лайк в ответ 👍", callback_data=f"like_{to_user_id}"),
            InlineKeyboardButton("Дизлайк 👎", callback_data=f"dislike_{to_user_id}"),
            InlineKeyboardButton("Пропустить ⏭️", callback_data=f"skip_incoming_{to_user_id}"),
            InlineKeyboardButton("Жалоба ⚠️", callback_data=f"report_{to_user_id}"),
            InlineKeyboardButton("Меню 📋", callback_data="back_to_menu")
        )
        await bot.send_message(message.chat.id, "Действия:", reply_markup=keyboard)
        await ViewingState.likes.set()
    except Exception as e:
        logging.error(f"Error in view_incoming_likes: {e}")
        await message.reply("Ошибка при просмотре лайков. 😔")

@dp.callback_query_handler(lambda c: c.data.startswith('skip_incoming_'), state=ViewingState.likes)
async def skip_incoming(callback_query: types.CallbackQuery, state: FSMContext):
    try:
        await state.finish()
        to_user_id = int(callback_query.data.split('_')[2])
        from_user_id = callback_query.from_user.id
        cursor.execute("INSERT OR IGNORE INTO skips (from_user, to_user) VALUES (?, ?)", (from_user_id, to_user_id))
        conn.commit()
        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (from_user_id, f'skipped_{to_user_id}'))
        conn.commit()
        await callback_query.answer("Пропущено! Следующий... ⏭️")
        await view_incoming_likes(callback_query.message)
    except Exception as e:
        logging.error(f"Error in skip_incoming: {e}")
        await callback_query.answer("Ошибка. 😔")

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    try:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.row(KeyboardButton('Искать анкеты 🔍'), KeyboardButton('Статистика 📊'),
                     KeyboardButton('Список пользователей 📋'))
        keyboard.row(KeyboardButton('Просмотр анкеты по ID 👤'), KeyboardButton('Поиск пользователей 🔎'))
        keyboard.row(KeyboardButton('Просмотр лайков ❤️'), KeyboardButton('Рассылка сообщений 📩'))
        keyboard.row(KeyboardButton('Экспорт данных 📤'), KeyboardButton('Просмотр логов 📜'))
        keyboard.row(KeyboardButton('Выдать премиум 💎'), KeyboardButton('Отменить премиум ❌'))
        keyboard.row(KeyboardButton('Пользователи с премиум 💎📋'), KeyboardButton('Жалобы ⚠️'))
        if check_super_admin(message.from_user.id):
            keyboard.row(KeyboardButton('Список админов 👥'), KeyboardButton('Назначить админа ✅'), KeyboardButton('Удалить админа ❌'))
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Админ панель: Выбери действие! 🙂", reply_markup=keyboard)
    except Exception as e:
        logging.error(f"Error in admin_panel: {e}")

@dp.message_handler(Text(equals='Статистика 📊'))
async def stats(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM likes")
        likes_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM dislikes")
        dislikes_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM skips")
        skips_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE blocked=1")
        blocked_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE premium=1")
        premium_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT from_user) FROM likes")
        active_likers = cursor.fetchone()[0]
        cursor.execute("""
        SELECT COUNT(*) FROM likes l1
        WHERE EXISTS (SELECT 1 FROM likes l2 WHERE l1.from_user = l2.to_user AND l1.to_user = l2.from_user)
        """)
        matches_count = cursor.fetchone()[0] // 2
        await message.reply(f"Пользователей: {users_count}\nПремиум: {premium_count}\nЛайков: {likes_count}\nДизлайков: {dislikes_count}\nСкипов: {skips_count}\nЗаблокировано: {blocked_count}\nАктивных лайкеров: {active_likers}\nMutual matches: {matches_count} 📊")
    except Exception as e:
        logging.error(f"Error in stats: {e}")
        await message.reply("Ошибка при получении статистики. 😔")

@dp.message_handler(Text(equals='Список пользователей 📋'))
async def list_users(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    try:
        cursor.execute("SELECT user_id, name, age, gender, country, city, blocked, premium FROM users ORDER BY user_id")
        users = cursor.fetchall()
        if not users:
            await message.reply("Нет пользователей. 😔")
            return
        response = "Список пользователей: 📋\n"
        for user in users:
            user_id = user['user_id']
            name = user['name']
            age = user['age']
            gender = user['gender']
            country = user['country']
            city = user['city']
            blocked = user['blocked']
            premium = user['premium']
            status = "Заблокирован 🔒" if blocked else "Активен ✅"
            premium_status = "💎 VIP" if premium else ""
            response += f"ID: {user_id}, {name}, {age} лет, {gender.capitalize()}, {country}, {city} {status} {premium_status}\n"
        await message.reply(response)
    except Exception as e:
        logging.error(f"Error in list_users: {e}")
        await message.reply("Ошибка при получении списка. 😔")

@dp.message_handler(Text(equals='Жалобы ⚠️'))
async def view_reports(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    try:
        cursor.execute("SELECT * FROM logs WHERE action LIKE 'reported_%' ORDER BY timestamp DESC LIMIT 50")
        logs = cursor.fetchall()
        if not logs:
            await message.reply("Нет жалоб.")
            return
        response = "Жалобы ⚠️:\n"
        for log in logs:
            ts = log['timestamp']
            uid = log['user_id']
            action = log['action']
            parts = action.split('_', 2)
            if len(parts) >= 3:
                reported_id = parts[1]
                reason = parts[2]
                cursor.execute("SELECT name FROM users WHERE user_id=?", (uid,))
                r = cursor.fetchone()
                reporter_name = r['name'] if r else 'Unknown'
                cursor.execute("SELECT name FROM users WHERE user_id=?", (reported_id,))
                r = cursor.fetchone()
                reported_name = r['name'] if r else 'Unknown'
                response += f"{ts}: {reporter_name} (ID:{uid}) жалуется на {reported_name} (ID:{reported_id}): {reason}\n"
        await message.reply(response)
    except Exception as e:
        logging.error(f"Error in view_reports: {e}")
        await message.reply("Ошибка при просмотре жалоб. 😔")

@dp.message_handler(Text(equals='Просмотр анкеты по ID 👤'))
async def admin_view_profile_start(message: types.Message, state: FSMContext):
    if not check_admin(message.from_user.id):
        return
    try:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Введи ID пользователя для просмотра анкеты: 🙂", reply_markup=keyboard)
        await AdminForm.view_user_id.set()
    except Exception as e:
        logging.error(f"Error in admin_view_profile_start: {e}")

@dp.message_handler(state=AdminForm.view_user_id)
async def admin_view_profile(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        user_id = int(message.text.strip())
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        profile = cursor.fetchone()
        if not profile:
            await message.reply("Пользователь не найден. 😔")
            await state.finish()
            return
        name = profile['name']
        photos_json = profile['photos']
        age = profile['age']
        gender = profile['gender']
        description = profile['description']
        seeking_gender = profile['seeking_gender']
        country = profile['country']
        city = profile['city']
        blocked = profile['blocked']
        premium = profile['premium']
        photos = json.loads(photos_json or '[]')
        status = "Заблокирован 🔒" if blocked else "Активен ✅"
        premium_status = "💎 VIP" if premium else ""
        desc_line = f"{description}\n" if description else ""
        caption = f"Анкета ID {user_id}:\n{name}, {age} лет, {gender.capitalize()} {premium_status}\n{desc_line}Ищешь: {seeking_gender.capitalize()}\nСтрана: {country}\nГород: {city}\nСтатус: {status}"
        if photos:
            media = MediaGroup()
            for i, photo in enumerate(photos):
                if i == 0:
                    media.attach_photo(photo, caption=caption, parse_mode=ParseMode.HTML)
                else:
                    media.attach_photo(photo)
            await bot.send_media_group(message.chat.id, media)
        else:
            await bot.send_message(message.chat.id, caption, parse_mode=ParseMode.HTML)
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("Блокировать 🔒" if not blocked else "Разблокировать 🔓",
                                 callback_data=f"admin_block_{user_id}_{blocked}"),
            InlineKeyboardButton("Удалить 🗑️", callback_data=f"admin_delete_{user_id}"),
            InlineKeyboardButton("Редактировать ✏️", callback_data=f"admin_edit_{user_id}"),
            InlineKeyboardButton("Отправить сообщение 📩", callback_data=f"admin_message_{user_id}")
        )
        await bot.send_message(message.chat.id, "Действия:", reply_markup=keyboard)
        await state.finish()
    except ValueError:
        await message.reply("Введи число (ID). Попробуй снова. 🙂")
    except Exception as e:
        logging.error(f"Error in admin_view_profile: {e}")
        await message.reply("Ошибка при просмотре. 😔")
        await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('admin_block_'), state='*')
async def admin_block_callback(callback_query: types.CallbackQuery):
    if not check_admin(callback_query.from_user.id):
        return
    try:
        parts = callback_query.data.split('_')
        user_id = int(parts[2])
        current_blocked = int(parts[3])
        new_blocked = 1 if current_blocked == 0 else 0
        cursor.execute("UPDATE users SET blocked=? WHERE user_id=?", (new_blocked, user_id))
        conn.commit()
        action = "заблокирован 🔒" if new_blocked else "разблокирован 🔓"
        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, f'blocked_{new_blocked}'))
        conn.commit()
        await callback_query.answer(f"Пользователь {action}.")
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logging.error(f"Error in admin_block_callback: {e}")
        await callback_query.answer("Ошибка при блокировке/разблокировке. 😔")

@dp.callback_query_handler(lambda c: c.data.startswith('admin_delete_'), state='*')
async def admin_delete_callback(callback_query: types.CallbackQuery):
    if not check_admin(callback_query.from_user.id):
        return
    try:
        user_id = int(callback_query.data.split('_')[2])
        cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
        cursor.execute("DELETE FROM likes WHERE from_user=? OR to_user=?", (user_id, user_id))
        cursor.execute("DELETE FROM dislikes WHERE from_user=? OR to_user=?", (user_id, user_id))
        cursor.execute("DELETE FROM skips WHERE from_user=? OR to_user=?", (user_id, user_id))
        cursor.execute("DELETE FROM logs WHERE user_id=?", (user_id,))
        cursor.execute("DELETE FROM invitations WHERE inviter_id=? OR invited_id=?", (user_id, user_id))
        conn.commit()
        await callback_query.answer("Пользователь удален. 🗑️")
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logging.error(f"Error in admin_delete_callback: {e}")
        await callback_query.answer("Ошибка при удалении. 😔")

@dp.callback_query_handler(lambda c: c.data.startswith('admin_edit_'), state='*')
async def admin_edit_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if not check_admin(callback_query.from_user.id):
        return
    try:
        user_id = int(callback_query.data.split('_')[2])
        async with state.proxy() as data:
            data['admin_editing'] = True
            data['target_user_id'] = user_id
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await callback_query.message.reply("Редактируем анкету пользователя. Введи новое имя: 🙂", reply_markup=keyboard)
        await ProfileForm.name.set()
        await callback_query.answer("Начато редактирование. ✏️")
    except Exception as e:
        logging.error(f"Error in admin_edit_callback: {e}")
        await callback_query.answer("Ошибка. 😔")

@dp.callback_query_handler(lambda c: c.data.startswith('admin_message_'), state='*')
async def admin_message_callback(callback_query: types.CallbackQuery, state: FSMContext):
    if not check_admin(callback_query.from_user.id):
        return
    try:
        user_id = int(callback_query.data.split('_')[2])
        async with state.proxy() as data:
            data['user_id'] = user_id
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await callback_query.message.reply("Введи текст сообщения:", reply_markup=keyboard)
        await AdminForm.message_text.set()
        await callback_query.answer("Введи текст сообщения. 📝")
    except Exception as e:
        logging.error(f"Error in admin_message_callback: {e}")
        await callback_query.answer("Ошибка. 😔")

@dp.message_handler(state=AdminForm.message_text)
async def admin_message_text(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        text = message.text.strip()
        if not text:
            await message.reply("Текст не может быть пустым. Попробуй снова. 🙂")
            return
        async with state.proxy() as data:
            user_id = data['user_id']
        await bot.send_message(user_id, f"Сообщение от админа: {text}")
        await message.reply(f"Сообщение отправлено пользователю ID {user_id}. 📩")
        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'received_admin_message'))
        conn.commit()
        await state.finish()
    except Exception as e:
        logging.error(f"Error in admin_message_text: {e}")
        await message.reply("Ошибка при отправке. 😔")
        await state.finish()

@dp.message_handler(Text(equals='Выдать премиум 💎'))
async def admin_premium_start(message: types.Message, state: FSMContext):
    if not check_admin(message.from_user.id):
        return
    try:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Введи ID пользователя для выдачи премиум:", reply_markup=keyboard)
        await AdminForm.premium_user_id.set()
    except Exception as e:
        logging.error(f"Error in admin_premium_start: {e}")

@dp.message_handler(state=AdminForm.premium_user_id)
async def admin_premium_id(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        user_id = int(message.text.strip())
        async with state.proxy() as data:
            data['premium_user'] = user_id
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Сколько дней дать премиум?", reply_markup=keyboard)
        await AdminForm.premium_duration.set()
    except ValueError:
        await message.reply("Введи число (ID).")
    except Exception as e:
        logging.error(f"Error in admin_premium_id: {e}")

@dp.message_handler(state=AdminForm.premium_duration)
async def admin_premium_duration(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        days = int(message.text.strip())
        if days <= 0:
            await message.reply("Дней должно быть больше 0.")
            return
        async with state.proxy() as data:
            user_id = data['premium_user']
        cursor.execute("SELECT premium_expiry FROM users WHERE user_id=?", (user_id,))
        current_expiry_result = cursor.fetchone()
        current_expiry = current_expiry_result['premium_expiry'] if current_expiry_result and current_expiry_result['premium_expiry'] else None
        if current_expiry:
            new_expiry = datetime.fromisoformat(current_expiry) + timedelta(days=days)
        else:
            new_expiry = datetime.now() + timedelta(days=days)
        cursor.execute("UPDATE users SET premium=1, premium_expiry=? WHERE user_id=?", (new_expiry.isoformat(), user_id))
        conn.commit()
        await bot.send_message(user_id, f"Администратор выдал тебе премиум на {days} дней! 😎")
        await message.reply(f"Премиум выдан пользователю ID {user_id} на {days} дней. 💎")
        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, f'admin_granted_premium_{days}_days'))
        conn.commit()
        await state.finish()
    except ValueError:
        await message.reply("Введи число (дней).")
    except Exception as e:
        logging.error(f"Error in admin_premium_duration: {e}")
        await message.reply("Ошибка при выдаче премиум.")

@dp.message_handler(Text(equals='Отменить премиум ❌'))
async def admin_cancel_premium_start(message: types.Message, state: FSMContext):
    if not check_admin(message.from_user.id):
        return
    try:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Введи ID пользователя для отмены премиум:", reply_markup=keyboard)
        await AdminForm.cancel_premium_user_id.set()
    except Exception as e:
        logging.error(f"Error in admin_cancel_premium_start: {e}")

@dp.message_handler(state=AdminForm.cancel_premium_user_id)
async def admin_cancel_premium(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        user_id = int(message.text.strip())
        cursor.execute("SELECT premium FROM users WHERE user_id=?", (user_id,))
        result = cursor.fetchone()
        if not result or not result['premium']:
            await message.reply("У пользователя нет премиум.")
            await state.finish()
            return
        cursor.execute("UPDATE users SET premium=0, premium_expiry=NULL WHERE user_id=?", (user_id,))
        conn.commit()
        await bot.send_message(user_id, "Администратор отменил твой премиум статус. 😔")
        await message.reply(f"Премиум отменен для пользователя ID {user_id}. ❌")
        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'admin_canceled_premium'))
        conn.commit()
        await state.finish()
    except ValueError:
        await message.reply("Введи число (ID).")
    except Exception as e:
        logging.error(f"Error in admin_cancel_premium: {e}")
        await message.reply("Ошибка при отмене премиум.")

@dp.message_handler(Text(equals='Пользователи с премиум 💎📋'))
async def list_premium_users(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    try:
        cursor.execute("""
            SELECT user_id, name, age, gender, country, city, premium_expiry, blocked 
            FROM users 
            WHERE premium = 1 
            ORDER BY premium_expiry DESC
        """)
        premium_users = cursor.fetchall()
        if not premium_users:
            await message.reply("Нет пользователей с премиум. 😔")
            return
        response = "Пользователи с премиум 💎:\n"
        for user in premium_users:
            user_id = user['user_id']
            name = user['name']
            age = user['age']
            gender = user['gender']
            country = user['country']
            city = user['city']
            expiry = user['premium_expiry']
            blocked = user['blocked']
            status = "Заблокирован 🔒" if blocked else "Активен ✅"
            expiry_str = datetime.fromisoformat(expiry).strftime("%Y-%m-%d %H:%M") if expiry else "Неизвестно"
            response += f"ID: {user_id}, {name}, {age} лет, {gender.capitalize()}, {country}, {city} | До: {expiry_str} | {status}\n"
        await message.reply(response)
    except Exception as e:
        logging.error(f"Error in list_premium_users: {e}")
        await message.reply("Ошибка при получении списка. 😔")

@dp.message_handler(Text(equals='Поиск пользователей 🔎'))
async def admin_search_users_start(message: types.Message, state: FSMContext):
    if not check_admin(message.from_user.id):
        return
    try:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Введи имя для поиска (или оставь пустым для любого):", reply_markup=keyboard)
        await AdminForm.search_name.set()
    except Exception as e:
        logging.error(f"Error in admin_search_users_start: {e}")

@dp.message_handler(state=AdminForm.search_name)
async def admin_search_name(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        async with state.proxy() as data:
            data['name'] = message.text.strip() if message.text.strip() else '%'
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Введи минимальный возраст (или 0):", reply_markup=keyboard)
        await AdminForm.search_age_min.set()
    except Exception as e:
        logging.error(f"Error in admin_search_name: {e}")

@dp.message_handler(state=AdminForm.search_age_min)
async def admin_search_age_min(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        min_age = int(message.text) if message.text.isdigit() else 0
        async with state.proxy() as data:
            data['min_age'] = min_age
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Введи максимальный возраст (или 999):", reply_markup=keyboard)
        await AdminForm.search_age_max.set()
    except Exception as e:
        logging.error(f"Error in admin_search_age_min: {e}")
        await message.reply("Введи число.")

@dp.message_handler(state=AdminForm.search_age_max)
async def admin_search_age_max(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        max_age = int(message.text) if message.text.isdigit() else 999
        async with state.proxy() as data:
            data['max_age'] = max_age
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.row(KeyboardButton('Мужской 🚹'), KeyboardButton('Женский 🚺'))
        keyboard.add(KeyboardButton('Любой ❓'), KeyboardButton('Отмена'))
        await message.reply("Выбери пол (или Любой):", reply_markup=keyboard)
        await AdminForm.search_gender.set()
    except Exception as e:
        logging.error(f"Error in admin_search_age_max: {e}")
        await message.reply("Введи число.")

@dp.message_handler(state=AdminForm.search_gender)
async def admin_search_gender(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        gender = message.text.lower().replace('🚹', '').replace('🚺', '').replace(' ❓', '')
        if gender not in ['мужской', 'женский', 'любой']:
            await message.reply("Выбери правильно.")
            return
        gender_query = '%' if gender == 'любой' else gender
        async with state.proxy() as data:
            data['gender'] = gender_query
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        countries = ['Любой ❓', 'Россия 🌍', 'Таджикистан 🌍', 'Узбекистан 🌍', 'Кыргызстан 🌍', 'Казахстан 🌍']
        for country in countries:
            keyboard.add(KeyboardButton(country))
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Выбери страну (или Любой):", reply_markup=keyboard)
        await AdminForm.search_country.set()
    except Exception as e:
        logging.error(f"Error in admin_search_gender: {e}")

@dp.message_handler(state=AdminForm.search_country)
async def admin_search_country(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        country = message.text.strip().replace(' 🌍', '').replace(' ❓', '')
        async with state.proxy() as data:
            data['country'] = country if country != 'Любой' else '%'
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.row(KeyboardButton('Любой ❓'), KeyboardButton('VIP 💎'), KeyboardButton('Обычный 👤'))
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Выбери статус премиум (или Любой):", reply_markup=keyboard)
        await AdminForm.search_premium.set()
    except Exception as e:
        logging.error(f"Error in admin_search_country: {e}")

@dp.message_handler(state=AdminForm.search_premium)
async def admin_search_premium(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        premium_status = message.text.replace(' ❓', '').replace(' 💎', '').replace(' 👤', '')
        premium_query = None
        if premium_status == 'VIP':
            premium_query = 1
        elif premium_status == 'Обычный':
            premium_query = 0
        async with state.proxy() as data:
            data['premium'] = premium_query
            name = f"%{data['name']}%"
            min_age = data['min_age']
            max_age = data['max_age']
            gender_query = data['gender']
            country_query = data['country']
        query = """
        SELECT user_id, name, age, gender, country, city, blocked, premium FROM users 
        WHERE name LIKE ? AND age BETWEEN ? AND ? AND gender LIKE ?
        """
        params = [name, min_age, max_age, gender_query]
        if country_query != '%':
            query += " AND country LIKE ?"
            params.append(f"%{country_query}%")
        if premium_query is not None:
            query += " AND premium = ?"
            params.append(premium_query)
        query += " ORDER BY user_id"
        cursor.execute(query, params)
        users = cursor.fetchall()
        if not users:
            await message.reply("Нет результатов.")
        else:
            response = "Результаты поиска 🔎:\n"
            for user in users:
                user_id = user['user_id']
                name = user['name']
                age = user['age']
                g = user['gender']
                country = user['country']
                city = user['city']
                blocked = user['blocked']
                premium = user['premium']
                status = "Заблокирован 🔒" if blocked else "Активен ✅"
                premium_status = "💎 VIP" if premium else ""
                response += f"ID: {user_id}, {name}, {age}, {g.capitalize()}, {country}, {city} {status} {premium_status}\n"
            await message.reply(response, reply_markup=types.ReplyKeyboardRemove())
        await state.finish()
    except Exception as e:
        logging.error(f"Error in admin_search_premium: {e}")
        await message.reply("Ошибка поиска.")

@dp.message_handler(Text(equals='Просмотр лайков ❤️'))
async def admin_view_likes_start(message: types.Message, state: FSMContext):
    if not check_admin(message.from_user.id):
        return
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Отмена'))
    await message.reply("Введи ID пользователя для просмотра лайков:", reply_markup=keyboard)
    await AdminForm.likes_user_id.set()

@dp.message_handler(state=AdminForm.likes_user_id)
async def admin_view_likes(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        user_id = int(message.text)
        cursor.execute("SELECT to_user FROM likes WHERE from_user=?", (user_id,))
        liked = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT from_user FROM likes WHERE to_user=?", (user_id,))
        likers = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT to_user FROM dislikes WHERE from_user=?", (user_id,))
        disliked = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT to_user FROM skips WHERE from_user=?", (user_id,))
        skipped = [row[0] for row in cursor.fetchall()]
        mutual = set(liked) & set(likers)
        response = f"Лайки от {user_id}: {', '.join(map(str, liked)) or 'Нет'}\n"
        response += f"Лайки к {user_id}: {', '.join(map(str, likers)) or 'Нет'}\n"
        response += f"Дизлайки от {user_id}: {', '.join(map(str, disliked)) or 'Нет'}\n"
        response += f"Скипы от {user_id}: {', '.join(map(str, skipped)) or 'Нет'}\n"
        response += f"Mutual: {', '.join(map(str, mutual)) or 'Нет'}"
        await message.reply(response)
        await state.finish()
    except ValueError:
        await message.reply("Введи число (ID).")
    except Exception as e:
        logging.error(f"Error in admin_view_likes: {e}")
        await message.reply("Ошибка или неверный ID.")
        await state.finish()

@dp.message_handler(Text(equals='Рассылка сообщений 📩'))
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if not check_admin(message.from_user.id):
        return
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Отмена'))
    await message.reply("Введи текст для рассылки:", reply_markup=keyboard)
    await AdminForm.broadcast_text.set()

@dp.message_handler(state=AdminForm.broadcast_text)
async def admin_broadcast_text(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        text = message.text.strip()
        if not text:
            await message.reply("Текст не может быть пустым.")
            return
        async with state.proxy() as data:
            data['text'] = text
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Пропустить 📝'), KeyboardButton('Отмена'))
        await message.reply("Теперь отправь фото, видео или документ для прикрепления, или нажми 'Пропустить 📝'.", reply_markup=keyboard)
        await AdminForm.broadcast_media.set()
    except Exception as e:
        logging.error(f"Error in admin_broadcast_text: {e}")

@dp.message_handler(content_types=[ContentType.PHOTO, ContentType.VIDEO, ContentType.DOCUMENT, ContentType.TEXT], state=AdminForm.broadcast_media)
async def admin_broadcast_media(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        async with state.proxy() as data:
            media = None
            media_type = None
            if message.text and message.text == 'Пропустить 📝':
                pass
            elif message.photo:
                media = message.photo[-1].file_id
                media_type = 'photo'
            elif message.video:
                media = message.video.file_id
                media_type = 'video'
            elif message.document:
                media = message.document.file_id
                media_type = 'document'
            else:
                await message.reply("Неверный тип. Отправь фото, видео, документ или 'Пропустить 📝'.")
                return
            data['media'] = media
            data['media_type'] = media_type
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.row(KeyboardButton('Все 🌍'), KeyboardButton('Активные ✅'))
        keyboard.row(KeyboardButton('Заблокированные 🔒'), KeyboardButton('Отмена'))
        await message.reply("Выбери фильтр:", reply_markup=keyboard)
        await AdminForm.broadcast_filter.set()
    except Exception as e:
        logging.error(f"Error in admin_broadcast_media: {e}")
        await message.reply("Ошибка при обработке медиа.")

@dp.message_handler(state=AdminForm.broadcast_filter)
async def admin_broadcast_filter(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        filter_type = message.text.replace(' 🌍', '').replace(' ✅', '').replace(' 🔒', '')
        where = ""
        if filter_type == 'Активные':
            where = "WHERE blocked=0"
        elif filter_type == 'Заблокированные':
            where = "WHERE blocked=1"
        elif filter_type != 'Все':
            await message.reply("Неверный фильтр.")
            return
        cursor.execute(f"SELECT user_id FROM users {where}")
        users = [row[0] for row in cursor.fetchall()]
        async with state.proxy() as data:
            text = data['text']
            media = data.get('media')
            media_type = data.get('media_type')
        sent = 0
        caption_or_text = f"Сообщение от админа: {text}"
        for uid in users:
            try:
                if media_type == 'photo':
                    await bot.send_photo(uid, media, caption=caption_or_text)
                elif media_type == 'video':
                    await bot.send_video(uid, media, caption=caption_or_text)
                elif media_type == 'document':
                    await bot.send_document(uid, media, caption=caption_or_text)
                else:
                    await bot.send_message(uid, caption_or_text)
                sent += 1
                await asyncio.sleep(0.01)
            except Exception as send_e:
                logging.warning(f"Failed to send to {uid}: {send_e}")
        await message.reply(f"Рассылка отправлена {sent} пользователям.", reply_markup=types.ReplyKeyboardRemove())
        await state.finish()
    except Exception as e:
        logging.error(f"Error in broadcast: {e}")
        await message.reply("Ошибка рассылки.")
        await state.finish()

@dp.message_handler(Text(equals='Экспорт данных 📤'))
async def admin_export_data(message: types.Message):
    if not check_admin(message.from_user.id):
        return
    try:
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['user_id', 'username', 'name', 'photos', 'age', 'gender', 'description', 'seeking_gender', 'country', 'city', 'blocked', 'premium', 'premium_expiry', 'invited_count', 'last_boost'])
        for user in users:
            writer.writerow([user['user_id'], user['username'], user['name'], user['photos'], user['age'], user['gender'], user['description'], user['seeking_gender'], user['country'], user['city'], user['blocked'], user['premium'], user['premium_expiry'], user['invited_count'], user['last_boost']])
        output.seek(0)
        await bot.send_document(message.chat.id, InputFile(io.BytesIO(output.getvalue().encode()), filename='users.csv'))
    except Exception as e:
        logging.error(f"Error in export: {e}")
        await message.reply("Ошибка экспорта.")

@dp.message_handler(Text(equals='Просмотр логов 📜'))
async def admin_view_logs_start(message: types.Message, state: FSMContext):
    if not check_admin(message.from_user.id):
        return
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(KeyboardButton('Отмена'))
    await message.reply("Введи ID пользователя для логов (или 0 для всех последних 50):", reply_markup=keyboard)
    await AdminForm.logs_user_id.set()

@dp.message_handler(state=AdminForm.logs_user_id)
async def admin_view_logs(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        user_id = int(message.text)
        if user_id == 0:
            cursor.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 50")
        else:
            cursor.execute("SELECT * FROM logs WHERE user_id=? ORDER BY timestamp DESC", (user_id,))
        logs = cursor.fetchall()
        if not logs:
            await message.reply("Нет логов.")
        else:
            response = "Логи 📜:\n"
            for log in logs:
                log_id = log['log_id']
                uid = log['user_id']
                action = log['action']
                ts = log['timestamp']
                response += f"{ts}: User {uid} - {action}\n"
            await message.reply(response)
        await state.finish()
    except ValueError:
        await message.reply("Введи число.")
    except Exception as e:
        logging.error(f"Error in admin_view_logs: {e}")
        await message.reply("Ошибка.")
        await state.finish()

@dp.message_handler(Text(equals='Список админов 👥'))
async def list_admins(message: types.Message):
    if not check_super_admin(message.from_user.id):
        return
    try:
        cursor.execute("""
        SELECT u.user_id, u.name, u.age, u.gender, u.blocked 
        FROM admins a 
        JOIN users u ON a.user_id = u.user_id 
        ORDER BY u.user_id
        """)
        admins = cursor.fetchall()
        response = "Список админов 👥: 📋\n"
        cursor.execute("SELECT name, age, gender, blocked FROM users WHERE user_id=?", (SUPER_ADMIN_ID,))
        super_profile = cursor.fetchone()
        if super_profile:
            name = super_profile['name']
            age = super_profile['age']
            gender = super_profile['gender']
            blocked = super_profile['blocked']
            status = "Заблокирован 🔒" if blocked else "Активен ✅"
            response += f"ID: {SUPER_ADMIN_ID}, {name}, {age} лет, {gender.capitalize()} {status} (Главный админ)\n"
        else:
            response += f"ID: {SUPER_ADMIN_ID} (Главный админ, анкета не найдена)\n"
        for admin in admins:
            user_id = admin['user_id']
            name = admin['name']
            age = admin['age']
            gender = admin['gender']
            blocked = admin['blocked']
            status = "Заблокирован 🔒" if blocked else "Активен ✅"
            response += f"ID: {user_id}, {name}, {age} лет, {gender.capitalize()} {status}\n"
        if not admins and not super_profile:
            response = "Нет админов. 😔"
        await message.reply(response)
    except Exception as e:
        logging.error(f"Error in list_admins: {e}")
        await message.reply("Ошибка при получении списка. 😔")

@dp.message_handler(Text(equals='Назначить админа ✅'))
async def appoint_admin_start(message: types.Message, state: FSMContext):
    if not check_super_admin(message.from_user.id):
        return
    try:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Введи ID пользователя для назначения админом: 🙂", reply_markup=keyboard)
        await AdminForm.appoint_admin_id.set()
    except Exception as e:
        logging.error(f"Error in appoint_admin_start: {e}")

@dp.message_handler(state=AdminForm.appoint_admin_id)
async def appoint_admin(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        user_id = int(message.text.strip())
        if user_id == SUPER_ADMIN_ID:
            await message.reply("Это главный админ, нельзя назначать заново.")
            await state.finish()
            return
        cursor.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
        if not cursor.fetchone():
            await message.reply("Пользователь не найден.")
            await state.finish()
            return
        cursor.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
        if cursor.fetchone():
            await message.reply("Пользователь уже админ.")
            await state.finish()
            return
        cursor.execute("INSERT INTO admins (user_id) VALUES (?)", (user_id,))
        conn.commit()
        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'appointed_admin'))
        conn.commit()
        await message.reply(f"Пользователь ID {user_id} назначен админом. ✅")
        await state.finish()
    except ValueError:
        await message.reply("Введи число (ID). Попробуй снова.")
    except Exception as e:
        logging.error(f"Error in appoint_admin: {e}")
        await message.reply("Ошибка при назначении.")
        await state.finish()

@dp.message_handler(Text(equals='Удалить админа ❌'))
async def remove_admin_start(message: types.Message, state: FSMContext):
    if not check_super_admin(message.from_user.id):
        return
    try:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        keyboard.add(KeyboardButton('Отмена'))
        await message.reply("Введи ID пользователя для удаления админки: 🙂", reply_markup=keyboard)
        await AdminForm.remove_admin_id.set()
    except Exception as e:
        logging.error(f"Error in remove_admin_start: {e}")

@dp.message_handler(state=AdminForm.remove_admin_id)
async def remove_admin(message: types.Message, state: FSMContext):
    try:
        if message.text == 'Отмена':
            await admin_cancel_handler(message, state)
            return
        user_id = int(message.text.strip())
        if user_id == SUPER_ADMIN_ID:
            await message.reply("Нельзя удалить главного админа.")
            await state.finish()
            return
        cursor.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
        if not cursor.fetchone():
            await message.reply("Пользователь не является админом.")
            await state.finish()
            return
        cursor.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        conn.commit()
        cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, 'removed_admin'))
        conn.commit()
        await message.reply(f"Админка удалена у пользователя ID {user_id}. ❌")
        await state.finish()
    except ValueError:
        await message.reply("Введи число (ID). Попробуй снова.")
    except Exception as e:
        logging.error(f"Error in remove_admin: {e}")
        await message.reply("Ошибка при удалении.")
        await state.finish()

@dp.errors_handler()
async def errors_handler(update, exception):
    logging.error(f"Global error: {exception}")
    return True

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)