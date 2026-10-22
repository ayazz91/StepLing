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
GEMINI_DAILY_REQUEST_LIMIT=100
REVIEW_INTERVALS_DAYS=1,3,7,14,30
ADMIN_IDS=
ALLOWED_USER_IDS=
```

`GEMINI_DAILY_REQUEST_LIMIT` задаёт число запросов к ИИ на пользователя за сутки UTC; `0` отключает этот лимит. Это ограничение приложения, а не гарантия максимальной суммы расходов. `ADMIN_IDS` — список Telegram ID администраторов через запятую для `/admin_stats`. Если `ALLOWED_USER_IDS` оставить пустым, бот принимает сообщения от всех пользователей; для закрытого тестирования укажите свой Telegram ID. `GEMINI_MODEL` можно заменить на любую доступную вашей учётной записи модель Gemini.

Запустите long polling:

```powershell
python -m bot.main
```

При первом `/start` настройте родной и изучаемый языки, уровень, цель, интересы, время напоминания и часовой пояс IANA (например, `Europe/Moscow`). Профиль и прогресс хранятся в SQLite-файле, указанном в `DATABASE_PATH`.

Поддерживаемые команды: `/dialogue`, `/lesson`, `/quiz`, `/translate`, `/words`, `/review`, `/stats` и `/settings`. Команда `/start` запускает настройку профиля.

Команда `/review` принимает основной перевод и сохранённые равноценные варианты ответа. Варианты отображаются в `/words`. Интервалы повторения для пяти уровней можно настроить через `REVIEW_INTERVALS_DAYS` в `.env` (например, `1,2,5,10,21`); значения должны быть положительными и строго возрастать. Правильный ответ перемещает слово на следующий интервал, ошибка возвращает его к первому.

Команда `/privacy` объясняет, какие данные сохраняются и передаются Gemini. Профиль, диалоги, словарь и ошибки хранятся в SQLite; временное состояние сценариев в Docker — в Redis. В настройках можно очистить историю или удалить данные из рабочей базы. Резервные копии могут храниться отдельно. Не отправляйте боту пароли и другую чувствительную информацию.

Системный промпт находится в [prompts/tutor_system.md](./prompts/tutor_system.md). Все сообщения и подписи интерфейса собраны в `bot/texts.py`; для изменения формулировок редактируйте этот модуль.

## Тесты и проверки

```powershell
python -m pytest
python -m compileall -q bot tests
```

Тесты используют временную SQLite и mock Gemini API; для запуска тестов не нужны токены и сетевой доступ.

## Резервные копии SQLite

Создайте согласованную резервную копию работающей базы через SQLite backup API:

```sh
docker compose exec -T tutor-bot python -m bot.backup
```

Копии сохраняются в Docker-том `tutor-backups`; скрипт удаляет копии старше семи дней. Для ежедневного запуска на VPS добавьте в `crontab -e` (замените путь на каталог проекта):

```cron
15 3 * * * cd /opt/language-tutor-bot && docker compose exec -T tutor-bot python -m bot.backup >> /opt/language-tutor-bot/backup.log 2>&1
```

Том на том же VPS не защищает от потери самого сервера. Периодически копируйте резервные файлы в отдельное защищённое хранилище. Чтобы восстановить выбранную копию, остановите бота и выполните команду, заменив имя файла:

```sh
docker compose stop tutor-bot
docker compose run --rm --no-deps tutor-bot python -m bot.backup --restore /app/backups/tutor-20261021T031500Z.sqlite3
docker compose up -d tutor-bot
```

Перед восстановлением бот проверяет целостность и структуру копии, а текущую базу сохраняет в `BACKUP_PATH`. Путь к этой копии выводится в консоль после успешного восстановления. Восстановление выполняется через временный файл, чтобы не заменять рабочую базу непроверенными данными.

FSM-состояния (в том числе прогресс квиза) в Docker сохраняются в Redis с AOF и отдельным томом. При запуске без `REDIS_URL` используется хранилище в памяти: состояние сбрасывается при перезапуске.

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

Для сохранения состояний викторин и других FSM-сценариев после перезапуска установите Redis (`sudo apt install redis-server`) и укажите в `.env` `REDIS_URL=redis://localhost:6379/0`. Без `REDIS_URL` бот использует хранилище в памяти, и незавершённые сценарии сбрасываются при перезапуске.

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

Docker Compose использует отдельные именованные тома для SQLite, резервных копий и Redis. Чтобы остановить бота без удаления данных:

```sh
docker compose down
```

Не используйте `docker compose down -v`, если хотите сохранить словарь и прогресс.
