from core.prompt import SYSTEM_PROMPT


def test_prompt_is_nonempty_string():
    assert isinstance(SYSTEM_PROMPT, str)
    assert len(SYSTEM_PROMPT.strip()) > 200


def test_prompt_addresses_pavan_by_name():
    assert "Pavan" in SYSTEM_PROMPT


def test_prompt_enforces_voice_first_length():
    assert "sentence" in SYSTEM_PROMPT.lower()


def test_prompt_prohibits_markdown():
    assert "bullet" in SYSTEM_PROMPT.lower() or "markdown" in SYSTEM_PROMPT.lower()


def test_prompt_defines_honesty_rules():
    assert "wrong" in SYSTEM_PROMPT.lower() or "not right" in SYSTEM_PROMPT.lower()
