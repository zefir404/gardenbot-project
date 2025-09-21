import telebot
from telebot import types
import requests
from datetime import datetime, timedelta
from openai import OpenAI
import logging
import calendar
from apscheduler.schedulers.background import BackgroundScheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = telebot.TeleBot('8008817220:AAE1Ct3dvzDljz3NFt2dHS99oDSyMpkgAk4')  # Замените на ваш токен

# API-ключ от OpenWeatherMap
API_KEY = '4a00d55bf645cc138e67fad888b89495'  # Замените на ваш ключ

# API-ключ от OpenAI
OPENAI_API_KEY = 'sk-lUzFuUtf0DYYVSeJceQEy6OcpoM5rEnc2G9YXYI1H2EiHcc9gOOfTDODv8iY'  # Замените на ваш ключ

# Инициализация OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)

# Инициализация планировщика
scheduler = BackgroundScheduler()
scheduler.start()

# Хранение планов и напоминаний (в реальном приложении используйте базу данных)
user_plans = {}


# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    show_main_menu(message)


# Функция для отображения главного меню с кнопками
def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button_location = types.KeyboardButton("Отправить мою локацию 🗺", request_location=True)
    button_advice = types.KeyboardButton("Получить совет по выращиванию 🌱")
    button_calendar = types.KeyboardButton("Календарь посадок 📅")
    button_view_plans = types.KeyboardButton("Мои планы 📋")
    button_reminders = types.KeyboardButton("Напоминания 🔔")
    button_site = types.KeyboardButton("Сайт для садоводов 🌐")
    markup.add(button_location, button_advice, button_calendar,
               button_view_plans, button_reminders, button_site)
    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)


# Обработка кнопки "Сайт для садоводов 🌐"
@bot.message_handler(func=lambda message: message.text == "Сайт для садоводов 🌐")
def send_site_link(message):
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton("Перейти на сайт", url="https://www.dacha6.ru/")
    markup.add(button)
    bot.send_message(message.chat.id, "Нажмите кнопку, чтобы перейти на сайт для садоводов:", reply_markup=markup)


# Обработка геолокации
@bot.message_handler(content_types=['location'])
def handle_location(message):
    latitude = message.location.latitude
    longitude = message.location.longitude
    logger.info(f"Получена локация: {latitude}, {longitude}")

    city = get_city_by_coordinates(latitude, longitude)
    if city:
        weather_data = get_weather(latitude, longitude)
        if weather_data:
            bot.send_message(message.chat.id, weather_data)
        else:
            bot.send_message(message.chat.id, "Не удалось получить данные о погоде.")
    else:
        bot.send_message(message.chat.id, "Не удалось определить город по вашим координатам.")


# Обработка кнопки "Календарь посадок 📅"
@bot.message_handler(func=lambda message: message.text == "Календарь посадок 📅")
def handle_calendar_button(message):
    show_calendar(message)


# Обработка кнопки "Мои планы 📋"
@bot.message_handler(func=lambda message: message.text == "Мои планы 📋")
def handle_view_plans_button(message):
    view_plans(message)


# Обработка кнопки "Напоминания 🔔"
@bot.message_handler(func=lambda message: message.text == "Напоминания 🔔")
def handle_reminders_button(message):
    ask_for_reminder_type(message)


# Функция для отображения календаря
def show_calendar(message):
    now = datetime.now()
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("<<", callback_data=f"prev_month_{now.year}_{now.month}"),
        types.InlineKeyboardButton(f"{calendar.month_name[now.month]} {now.year}", callback_data="ignore"),
        types.InlineKeyboardButton(">>", callback_data=f"next_month_{now.year}_{now.month}")
    )

    # Генерация календаря
    cal = calendar.monthcalendar(now.year, now.month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                row.append(types.InlineKeyboardButton(str(day), callback_data=f"day_{now.year}_{now.month}_{day}"))
        markup.row(*row)

    bot.send_message(message.chat.id, "Выберите дату:", reply_markup=markup)


# Обработка callback-запросов от календаря
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        if call.data.startswith("prev_month_"):
            year, month = map(int, call.data.split("_")[2:])
            if month == 1:
                year -= 1
                month = 12
            else:
                month -= 1
            update_calendar(call.message, year, month)
        elif call.data.startswith("next_month_"):
            year, month = map(int, call.data.split("_")[2:])
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            update_calendar(call.message, year, month)
        elif call.data.startswith("day_"):
            year, month, day = map(int, call.data.split("_")[1:])
            selected_date = datetime(year, month, day).strftime("%Y-%m-%d")
            ask_for_plan(call.message, selected_date)
        elif call.data == "ignore":
            bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка в обработке callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка, попробуйте позже")


# Функция для обновления календаря
def update_calendar(message, year, month):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("<<", callback_data=f"prev_month_{year}_{month}"),
        types.InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore"),
        types.InlineKeyboardButton(">>", callback_data=f"next_month_{year}_{month}")
    )

    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                row.append(types.InlineKeyboardButton(str(day), callback_data=f"day_{year}_{month}_{day}"))
        markup.row(*row)

    bot.edit_message_text("Выберите дату:", message.chat.id, message.message_id, reply_markup=markup)


# Функция для запроса плана на выбранную дату
def ask_for_plan(message, selected_date):
    msg = bot.send_message(message.chat.id, f"Введите план на {selected_date}:")
    bot.register_next_step_handler(msg, save_plan, selected_date)


# Функция для сохранения плана
def save_plan(message, selected_date):
    try:
        user_id = message.from_user.id
        if user_id not in user_plans:
            user_plans[user_id] = {}
        user_plans[user_id][selected_date] = message.text
        bot.send_message(message.chat.id, f"✅ План на {selected_date} сохранен!")
    except Exception as e:
        logger.error(f"Ошибка при сохранении плана: {e}")
        bot.send_message(message.chat.id, "❌ Не удалось сохранить план, попробуйте позже")


# Функция для просмотра сохраненных планов
def view_plans(message):
    try:
        user_id = message.from_user.id
        if user_id in user_plans and user_plans[user_id]:
            plans_text = "📋 Ваши планы:\n\n"
            for date, plan in user_plans[user_id].items():
                if date != "reminders":  # Исключаем напоминания из списка планов
                    plans_text += f"📅 {date}: {plan}\n"
            bot.send_message(message.chat.id, plans_text)
        else:
            bot.send_message(message.chat.id, "ℹ️ У вас пока нет сохраненных планов.")
    except Exception as e:
        logger.error(f"Ошибка при просмотре планов: {e}")
        bot.send_message(message.chat.id, "❌ Не удалось загрузить планы, попробуйте позже")


# Функция для запроса типа напоминания
def ask_for_reminder_type(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button_water = types.KeyboardButton("Полив 💧")
    button_fertilize = types.KeyboardButton("Подкормка 🌿")
    button_care = types.KeyboardButton("Уход 🌱")
    button_back = types.KeyboardButton("Назад ↩️")
    markup.add(button_water, button_fertilize, button_care, button_back)
    bot.send_message(message.chat.id, "Выберите тип напоминания:", reply_markup=markup)


# Обработка кнопки "Назад ↩️"
@bot.message_handler(func=lambda message: message.text == "Назад ↩️")
def handle_back_button(message):
    show_main_menu(message)


# Обработка выбора типа напоминания
@bot.message_handler(func=lambda message: message.text in ["Полив 💧", "Подкормка 🌿", "Уход 🌱"])
def handle_reminder_type_selection(message):
    reminder_type = message.text
    ask_for_reminder_date(message, reminder_type)


# Функция для запроса даты и времени напоминания
def ask_for_reminder_date(message, reminder_type):
    msg = bot.send_message(
        message.chat.id,
        f"Введите дату и время для напоминания '{reminder_type}' в формате ГГГГ-ММ-ДД ЧЧ:ММ (например, {datetime.now().strftime('%Y-%m-%d %H:%M')}):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, save_reminder, reminder_type)


# Функция для сохранения напоминания
def save_reminder(message, reminder_type):
    try:
        user_id = message.from_user.id
        reminder_datetime_str = message.text

        # Парсим введенную дату и время
        reminder_datetime = datetime.strptime(reminder_datetime_str, "%Y-%m-%d %H:%M")

        # Проверяем, что дата в будущем
        if reminder_datetime <= datetime.now():
            bot.send_message(message.chat.id, "❌ Пожалуйста, укажите дату и время в будущем.")
            return

        if user_id not in user_plans:
            user_plans[user_id] = {}

        if "reminders" not in user_plans[user_id]:
            user_plans[user_id]["reminders"] = []

        # Добавляем новое напоминание
        user_plans[user_id]["reminders"].append({
            "type": reminder_type,
            "datetime": reminder_datetime_str,
            "timestamp": reminder_datetime.timestamp()
        })

        # Планируем напоминание
        schedule_reminder(user_id, reminder_type, reminder_datetime)

        bot.send_message(
            message.chat.id,
            f"✅ Напоминание '{reminder_type}' установлено на {reminder_datetime_str}."
        )

    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат даты и времени. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Ошибка при сохранении напоминания: {e}")
        bot.send_message(message.chat.id, "❌ Не удалось установить напоминание, попробуйте позже.")


# Функция для планирования напоминания
def schedule_reminder(user_id, reminder_type, reminder_datetime):
    try:
        # Вычисляем задержку в секундах
        delay = (reminder_datetime - datetime.now()).total_seconds()

        if delay > 0:
            scheduler.add_job(
                send_reminder,
                'date',
                run_date=reminder_datetime,
                args=[user_id, reminder_type],
                id=f"{user_id}_{reminder_datetime.timestamp()}"
            )
            logger.info(f"Напоминание запланировано для user_id={user_id} на {reminder_datetime}")
    except Exception as e:
        logger.error(f"Ошибка при планировании напоминания: {e}")


# Функция для отправки напоминания
def send_reminder(user_id, reminder_type):
    try:
        bot.send_message(
            user_id,
            f"⏰ Напоминание: {reminder_type}!\n\n" +
            "Не забудьте выполнить запланированное действие."
        )
        logger.info(f"Отправлено напоминание для user_id={user_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания: {e}")


# Обработка кнопки "Получить совет по выращиванию 🌱"
@bot.message_handler(func=lambda message: message.text == "Получить совет по выращиванию 🌱")
def handle_advice_button(message):
    ask_for_plant_name(message)


# Функция для запроса названия растения
def ask_for_plant_name(message):
    msg = bot.send_message(
        message.chat.id,
        "Введите название растения (например, розы, помидоры, яблони):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(msg, get_growing_advice)


# Функция для получения советов по выращиванию
def get_growing_advice(message):
    plant_name = message.text
    logger.info(f"Пользователь запросил советы для растения: {plant_name}")

    # Получаем советы от OpenAI
    bot.send_chat_action(message.chat.id, 'typing')
    advice = get_plant_advice_from_openai(plant_name)

    if advice:
        # Разбиваем длинный текст на части, если он превышает лимит Telegram
        if len(advice) > 4000:
            for x in range(0, len(advice), 4000):
                bot.send_message(message.chat.id, advice[x:x + 4000])
        else:
            bot.send_message(message.chat.id, advice)
    else:
        bot.send_message(message.chat.id, "❌ Не удалось получить советы. Попробуйте позже.")


# Функция для получения советов от OpenAI
def get_plant_advice_from_openai(plant_name):
    try:
        prompt = (
            f"Дай подробные советы по выращиванию {plant_name} на русском языке. "
            "Опиши основные шаги по уходу, включая полив, подкормку, освещение, "
            "температурный режим и борьбу с вредителями. Ответ должен быть структурированным "
            "и содержать практические рекомендации."
        )

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system",
                 "content": "Ты опытный садовод, который дает подробные инструкции по выращиванию растений."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )

        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content.strip()
        return None
    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenAI API: {e}")
        return None


# Функция для получения города по координатам
def get_city_by_coordinates(lat, lon):
    url = f'http://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=1&appid={API_KEY}'
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0].get('name', 'Неизвестный город')
    except Exception as e:
        logger.error(f"Ошибка при запросе к гео API: {e}")
    return None


# Функция для получения прогноза погоды по координатам
def get_weather(lat, lon):
    url = f'http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={API_KEY}&units=metric&lang=ru'
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get('cod') != '200':
            return None

        city = data['city']['name']
        forecast = data['list']
        weather_info = f"🌦 Прогноз погоды для {city}:\n\n"

        # Группируем прогноз по дате (сегодня и завтра)
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)

        for day, date in [("Сегодня", today), ("Завтра", tomorrow)]:
            weather_info += f"📅 {day} ({date.strftime('%d.%m.%Y')}):\n"

            day_forecasts = [f for f in forecast if datetime.fromtimestamp(f['dt']).date() == date]
            if not day_forecasts:
                weather_info += "   Нет данных\n\n"
                continue

            # Берем утренний, дневной и вечерний прогноз
            for f in [day_forecasts[0], day_forecasts[len(day_forecasts) // 2], day_forecasts[-1]]:
                time = datetime.fromtimestamp(f['dt']).strftime('%H:%M')
                weather_info += (
                    f"   🕒 {time}: "
                    f"{f['weather'][0]['description'].capitalize()}, "
                    f"{round(f['main']['temp'])}°C, "
                    f"ощущается как {round(f['main']['feels_like'])}°C, "
                    f"влажность {f['main']['humidity']}%, "
                    f"ветер {f['wind']['speed']} м/с\n"
                )
            weather_info += "\n"

        return weather_info
    except Exception as e:
        logger.error(f"Ошибка при запросе к погодному API: {e}")
    return None


# Обработка неизвестных команд
@bot.message_handler(func=lambda message: True)
def handle_unknown(message):
    bot.send_message(message.chat.id, "Я не понимаю эту команду. Пожалуйста, используйте меню.")


# Запуск бота
if __name__ == '__main__':
    logger.info("Бот запущен")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logger.error(f"Ошибка в работе бота: {e}")
    finally:
        scheduler.shutdown()