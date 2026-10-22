FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 botuser \
    && mkdir -p /app/data /app/backups \
    && chown botuser:botuser /app/data /app/backups

COPY bot ./bot
COPY prompts ./prompts

USER botuser
CMD ["python", "-m", "bot.main"]
