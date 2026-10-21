from bot.services.prompts import PROMPT_VARIABLES, build_system_prompt


def test_prompt_substitutes_profile_and_context_without_formatting_user_braces() -> None:
    template = " ".join(f"{{{key}}}" for key in PROMPT_VARIABLES)
    user = {
        "target_lang": "Spanish",
        "native_lang": "Russian",
        "level": "B1",
        "goal": "Travel",
        "interests": "I like {music}",
        "mode": "dialogue",
    }

    prompt = build_system_prompt(
        template,
        user,
        [{"category": "verbs", "example": "I goes", "count": 2}],
        [{"word": "viaje", "translation": "trip"}],
    )

    assert "Spanish Russian B1 Travel I like {music} dialogue" in prompt
    assert "verbs: I goes (2)" in prompt
    assert "viaje = trip" in prompt
    assert not any("{" + variable + "}" in prompt for variable in PROMPT_VARIABLES)


def test_prompt_handles_missing_learning_context() -> None:
    prompt = build_system_prompt("{known_mistakes} | {recent_vocab}", {})
    assert prompt == "none recorded | none recorded"
