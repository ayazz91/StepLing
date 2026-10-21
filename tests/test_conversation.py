from pathlib import Path

import pytest

from bot.db.database import Database
from bot.db.repository import Repository
from bot.services.conversation import tutor_turn


class MockTutor:
    async def respond(self, system_prompt: str, history: list[dict[str, str]]) -> str:
        assert "learner requested level placement" in system_prompt
        assert history[-1]["content"] == "I goes yesterday."
        assert len(history) == 16
        return (
            "❌ I goes → ✅ I went + 💡 Past actions use the past form. "
            "[[QUIZ_RESULT]]correct[[/QUIZ_RESULT]] "
            "[[LEVEL_ESTIMATE]]A2[[/LEVEL_ESTIMATE]]\n"
            '[[VOCAB_JSON]]{"items":[{"word":"ayer","translation":"yesterday",'
            '"example":"Lo vi ayer."}]}[[/VOCAB_JSON]]'
        )


@pytest.mark.asyncio
async def test_tutor_turn_persists_clean_reply_vocabulary_mistakes_and_level() -> None:
    database = Database(Path(":memory:"))
    connection = await database.connect()
    repository = Repository(connection)
    await repository.create_user(19, {
        "native_lang": "Russian",
        "target_lang": "Spanish",
        "level": "Определить тестом",
        "goal": "Travel",
        "interests": "",
        "timezone": "UTC",
        "reminder_time": "",
    })
    for index in range(15):
        role = "user" if index % 2 == 0 else "assistant"
        await repository.save_message(19, role, f"prior message {index}")
    try:
        response = await tutor_turn(19, "I goes yesterday.", repository, MockTutor(), "{level}")

        assert response.text.startswith("❌ I goes → ✅ I went")
        assert response.quiz_correct is True
        assert "[[LEVEL_ESTIMATE]]" not in response.text
        user = await repository.get_user(19)
        assert user is not None and user["level"] == "A2"
        words = await repository.list_vocabulary(19)
        assert words[0]["word"] == "ayer"
        mistakes = await repository.known_mistakes(19)
        assert mistakes[0]["category"] == "i goes"
        history = await repository.get_history(19)
        assert "[[" not in history[-1]["content"]
    finally:
        await database.close()
