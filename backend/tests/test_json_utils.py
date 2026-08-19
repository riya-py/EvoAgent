import pytest

from app.json_utils import extract_json_array


def test_extract_clean_json_array():
    text = '[{"answer_id": "A", "overall": 8.0}]'
    assert extract_json_array(text) == [{"answer_id": "A", "overall": 8.0}]


def test_extract_json_wrapped_in_markdown_fence():
    text = '```json\n[{"answer_id": "A", "overall": 8.0}]\n```'
    assert extract_json_array(text) == [{"answer_id": "A", "overall": 8.0}]


def test_extract_json_with_preamble_text():
    text = 'Sure, here is my evaluation:\n[{"answer_id": "A", "overall": 8.0}]\nHope that helps!'
    assert extract_json_array(text) == [{"answer_id": "A", "overall": 8.0}]


def test_extract_single_object_wrapped_into_list():
    text = '{"answer_id": "A", "overall": 8.0}'
    assert extract_json_array(text) == [{"answer_id": "A", "overall": 8.0}]


def test_extract_raises_on_unparseable_text():
    with pytest.raises(ValueError):
        extract_json_array("no json here at all")