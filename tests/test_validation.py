import pytest

from backend.helpers import validate_token_request


def test_validate_token_request_without_session_id():
    result = validate_token_request(
        token="a" * 60,
        folder_id="b1g123456789abcdefghi",
        session_id=""
    )

    assert result == "Не найден ID сессии"


def test_validate_token_request_with_invalid_token_length():
    result = validate_token_request(
        token="short_token",
        folder_id="b1g123456789abcdefghi",
        session_id="test-session-id"
    )

    assert result == "Некорректная длина OAuth-токена"


def test_validate_token_request_with_valid_data():
    result = validate_token_request(
        token="a" * 60,
        folder_id="b1g123456789abcdefghi",
        session_id="test-session-id"
    )

    assert result is None