"""Centralized Russian UI strings for Telegram messages and buttons."""

from __future__ import annotations

WELCOME = "Привет! Я помогу тебе практиковать {target_language}. Напиши пару предложений о себе — и начнём."
ONBOARDING_NATIVE = "На каком языке тебе удобнее получать объяснения?"
ONBOARDING_NATIVE_OTHER = "Напиши свой родной язык."
ONBOARDING_TARGET = "Какой язык будем изучать?"
ONBOARDING_LEVEL = "Какой у тебя уровень CEFR?"
ONBOARDING_GOAL = "Какова твоя главная цель?"
ONBOARDING_INTERESTS = "Расскажи о своих интересах (до 200 символов), чтобы я подбирал подходящие темы."
ONBOARDING_REMINDER = "Когда присылать ежедневное напоминание?"
ONBOARDING_TIMEZONE = "Укажи часовой пояс IANA, например Europe/Moscow или America/New_York."
INVALID_TIMEZONE = "Не удалось распознать часовой пояс. Пример: Europe/Moscow."
INVALID_INTERESTS = "Пожалуйста, напиши не более 200 символов."
ONBOARDING_DONE = "Отлично, профиль настроен!"
NOT_REGISTERED = "Сначала настрой профиль командой /start."
RATE_LIMITED = "Ты отправляешь сообщения слишком часто. Подожди немного и попробуй снова."
MESSAGE_TOO_LONG = "Сообщение слишком длинное. Максимум — 1500 символов."
LLM_ERROR = "Извини, сейчас не получается получить ответ. Попробуй ещё раз немного позже."
UNKNOWN_ERROR = "Не удалось выполнить запрос. Попробуй ещё раз."
WORDS_EMPTY = "Пока слов нет. Продолжай практику — я буду сохранять новые слова."
WORDS_HEADER = "Твои последние слова:"
REVIEW_EMPTY = "Сейчас нет слов для повторения. Загляни позже!"
REVIEW_PROMPT = "Как переводится: {word}?"
REVIEW_CORRECT = "✅ Верно!"
REVIEW_INCORRECT = "Пока нет. Правильный перевод: {translation}"
REVIEW_DONE = "Повторение завершено. Отличная работа!"
STATS = "Твоя статистика:\nСообщений: {messages}\nСлов в словаре: {words}\nСерия дней: {streak}\nЧастые ошибки:\n{mistakes}"
STATS_NO_MISTAKES = "Пока нет записанных ошибок."
ADMIN_STATS = "Всего пользователей: {users}\nАктивны за сутки: {active}"
SETTINGS_HEADER = "Настройки профиля:"
SETTINGS_CURRENT = "Изучаемый язык: {target_language}\nЯзык объяснений: {native_language}\nУровень: {level}\nЦель: {goal}\nИнтересы: {interests}\nНапоминание: {reminder}\nЧасовой пояс: {timezone}"
SETTINGS_PROMPT = "Выбери, что изменить:"
SETTINGS_SAVED = "Настройка обновлена."
SETTINGS_TIMEZONE = "Укажи часовой пояс IANA, например Europe/Moscow."
ONBOARDING_TARGET_OTHER = "Напиши язык, который хочешь изучать."
SETTINGS_INTERESTS = "Напиши новые интересы (до 200 символов)."
SETTINGS_CLEAR_CONFIRM = "Удалить историю диалога? Профиль и словарь останутся."
SETTINGS_DELETE_CONFIRM = "Удалить профиль и все данные без возможности восстановления?"
SETTINGS_CLEARED = "История диалога удалена."
SETTINGS_DELETED = "Все данные удалены. Чтобы начать заново, отправь /start."
SETTINGS_CANCELLED = "Действие отменено."
SETTINGS_INVALID = "Пожалуйста, выбери вариант из кнопок."
INVALID_CHOICE = "Этот вариант больше недоступен. Попробуй выбрать ещё раз."
MODE_SET = "Режим «{mode}» включён."
MODE_LABELS = {
    "dialogue": "свободного разговора",
    "lesson": "мини-урока",
    "quiz": "квиза",
    "translate": "перевода",
}
QUIZ_FINISHED = "Квиз завершён: {score} из 5 правильных ответов. Режим диалога включён."
REMINDER_TEXT = "Небольшая ежедневная практика: напиши одно предложение на {target_language} о том, что планируешь сегодня."
RATE_LIMIT_NOTICE = "Сообщения ограничены для защиты от перегрузки."
MENU_BUTTONS = ("/dialogue", "/lesson", "/quiz", "/translate", "/words", "/review", "/stats", "/settings")
TARGET_LANGUAGES = ("Английский", "Испанский", "Немецкий", "Французский", "Итальянский", "Китайский", "Другой")
CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
GOALS = ("Путешествия", "Работа", "Экзамен", "Разговорная практика", "Общее развитие")
REMINDER_OPTIONS = (("Утро (09:00)", "09:00"), ("День (13:00)", "13:00"),
                    ("Вечер (19:00)", "19:00"), ("Не нужно", "off"))
NATIVE_LANGUAGES = ("Русский", "English", "Другой")
SETTINGS_LEVEL_BUTTON = "Изменить уровень"
SETTINGS_TARGET_BUTTON = "Изменить изучаемый язык"
SETTINGS_NATIVE_BUTTON = "Изменить язык объяснений"
SETTINGS_GOAL_BUTTON = "Изменить цель"
SETTINGS_INTERESTS_BUTTON = "Изменить интересы"
SETTINGS_REMINDER_BUTTON = "Изменить напоминание"
SETTINGS_TIMEZONE_BUTTON = "Изменить часовой пояс"
SETTINGS_CLEAR_BUTTON = "Очистить историю"
SETTINGS_DELETE_BUTTON = "Удалить все данные"
SETTINGS_CANCEL_BUTTON = "Отмена"
SETTINGS_CONFIRM_BUTTON = "Подтвердить"
LEVEL_TEST_BUTTON = "Не знаю, определить тестом"
QUIZ_START = "Начни квиз из пяти вопросов и задай первый вопрос."
QUIZ_NEXT = "Ты проверяешь ответ на вопрос {question} из 5. Объясни результат кратко. "
QUIZ_NEXT += "Добавь в конец ответа скрытый маркер [[QUIZ_RESULT]]correct[[/QUIZ_RESULT]] "
QUIZ_NEXT += "или [[QUIZ_RESULT]]incorrect[[/QUIZ_RESULT]] согласно ответу. "
QUIZ_NEXT += "Если это вопрос 5, подведи итог и не задавай новый вопрос."
QUIZ_FIRST = "Начни квиз из пяти вопросов и задай только первый вопрос."
MODE_KICKOFF = {
    "dialogue": "Начни непринуждённый разговор и задай мне короткий вопрос.",
    "lesson": "Начни мини-урок: объясни один небольшой полезный концепт и дай одно упражнение.",
    "translate": "Дай мне первое короткое предложение для перевода.",
}
REMINDER_NONE = "не настроено"
COMMAND_DESCRIPTIONS = (
    ("start", "Настроить профиль"),
    ("dialogue", "Свободный разговор"),
    ("lesson", "Мини-урок"),
    ("quiz", "Квиз из пяти вопросов"),
    ("translate", "Практика перевода"),
    ("words", "Мой словарь"),
    ("review", "Повторить слова"),
    ("stats", "Мой прогресс"),
    ("settings", "Настройки"),
    ("admin_stats", "Статистика администратора"),
)
