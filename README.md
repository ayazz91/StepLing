# Telegram-бот «Репетитор иностранных языков»

Асинхронный Telegram-бот на aiogram 3 с Gemini, SQLite, ежедневными напоминаниями и повторением слов по интервальной схеме.

## Требования

- Python 3.11 или новее
- Токен Telegram-бота
- Ключ Gemini API из Google AI Studio

## Получение ключей

1. Откройте Telegram и напишите [@BotFather](https://t.me/BotFather).
2. Выполните `/newbot`, задайте имя и username бота. Сохраните выданный токен.
3. Создайте API key в [Google AI Studio](https://aistudio.google.com/apikey).
4. Не публикуйте ключи и не добавляйте `.env` в систему контроля версий.

## Локальный запуск

Из корня проекта:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Откройте `.env` и укажите как минимум:

```dotenv
BOT_TOKEN=токен_от_BotFather
GEMINI_API_KEY=ключ_из_Google_AI_Studio
GEMINI_MODEL=gemini-2.5-flash
DATABASE_PATH=data/tutor.sqlite3
LOG_LEVEL=INFO
RATE_LIMIT_PER_MINUTE=10
ADMIN_IDS=
ALLOWED_USER_IDS=
```

`ADMIN_IDS` — список Telegram ID администраторов через запятую для `/admin_stats`. Если `ALLOWED_USER_IDS` оставить пустым, бот принимает сообщения от всех пользователей; иначе он будет отвечать только перечисленным ID. `GEMINI_MODEL` можно заменить на любую доступную вашей учётной записи модель Gemini.

Запустите long polling:

```powershell
python -m bot.main
```

При первом `/start` настройте родной и изучаемый языки, уровень, цель, интересы, время напоминания и часовой пояс IANA (например, `Europe/Moscow`). Профиль и прогресс хранятся в SQLite-файле, указанном в `DATABASE_PATH`.

Поддерживаемые команды: `/dialogue`, `/lesson`, `/quiz`, `/translate`, `/words`, `/review`, `/stats` и `/settings`. Команда `/start` запускает настройку профиля.

Системный промпт находится в [prompts/tutor_system.md](./prompts/tutor_system.md). Все сообщения и подписи интерфейса собраны в `bot/texts.py`; для изменения формулировок редактируйте этот модуль.

## Тесты и проверки

```powershell
python -m pytest
python -m compileall -q bot tests
```

Тесты используют временную SQLite и mock Gemini API; для запуска тестов не нужны токены и сетевой доступ.

## Развёртывание через systemd

Пример unit-файла: [deploy/language-tutor-bot.service](./deploy/language-tutor-bot.service).

1. Скопируйте проект в `/opt/language-tutor-bot`, создайте системного пользователя и назначьте ему владельца каталога.
2. В каталоге проекта создайте виртуальное окружение, установите зависимости и заполните `/opt/language-tutor-bot/.env`.
3. Создайте каталог данных и установите unit:

```sh
sudo useradd --system --home /opt/language-tutor-bot --shell /usr/sbin/nologin language-tutor
sudo mkdir -p /opt/language-tutor-bot/data
sudo chown -R language-tutor:language-tutor /opt/language-tutor-bot
cd /opt/language-tutor-bot
sudo -u language-tutor python3.11 -m venv .venv
sudo -u language-tutor .venv/bin/pip install -r requirements.txt
sudo chmod 600 .env
sudo install -m 0644 deploy/language-tutor-bot.service /etc/systemd/system/language-tutor-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now language-tutor-bot
```

Логи и состояние службы:

```sh
sudo systemctl status language-tutor-bot
sudo journalctl -u language-tutor-bot -f
```

Служба ограничивает запись каталогом `data`; убедитесь, что он принадлежит `language-tutor`.

## Развёртывание через Docker Compose

Создайте и заполните `.env` по образцу выше, затем выполните:

```sh
docker compose up -d --build
docker compose logs -f tutor-bot
```

Docker Compose использует именованный том `tutor-data` для постоянного хранения SQLite. Чтобы остановить бота без удаления данных:

```sh
docker compose down
```

Не используйте `docker compose down -v`, если хотите сохранить словарь и прогресс.
