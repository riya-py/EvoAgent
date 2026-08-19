import pytest

from app.model_assignment import PERSONALITY_MODEL_FAMILY, get_preferred_family
from app.models.ollama import KNOWN_MODEL_FAMILIES
from app.personalities import PERSONALITIES, get_personality, list_personalities

EXPECTED_IDS = {
    "scientist",
    "engineer",
    "professor",
    "researcher",
    "devils_advocate",
    "creative",
    "minimalist",
    "strategist",
}


def test_exactly_eight_personalities_with_unique_ids():
    assert len(PERSONALITIES) == 8
    ids = {p.id for p in PERSONALITIES}
    assert ids == EXPECTED_IDS


def test_every_personality_has_required_fields():
    for p in list_personalities():
        assert p.name
        assert p.description
        assert p.system_prompt
        assert len(p.specialties) > 0
        assert len(p.weaknesses) > 0
        # Original 8 are generation 0 with no parent.
        assert p.generation == 0
        assert p.parent_agent is None


def test_get_personality_returns_correct_one():
    scientist = get_personality("scientist")
    assert scientist.name == "Scientist"


def test_get_personality_unknown_id_raises():
    with pytest.raises(ValueError):
        get_personality("does-not-exist")


def test_every_personality_has_a_model_family_assigned():
    ids = {p.id for p in PERSONALITIES}
    assert set(PERSONALITY_MODEL_FAMILY.keys()) == ids
    for family in PERSONALITY_MODEL_FAMILY.values():
        assert family in KNOWN_MODEL_FAMILIES


def test_model_family_matches_spec_examples():
    # Scientist -> Qwen, Engineer -> Llama, Creative -> Mistral
    assert get_preferred_family("scientist") == "qwen"
    assert get_preferred_family("engineer") == "llama"
    assert get_preferred_family("creative") == "mistral"


def test_get_preferred_family_unknown_id_raises():
    with pytest.raises(ValueError):
        get_preferred_family("does-not-exist")


def test_model_is_not_baked_into_personality():
    # MODEL != PERSONALITY: the Personality object itself should carry
    # no notion of which Ollama model it runs on.
    scientist = get_personality("scientist")
    assert not hasattr(scientist, "model")