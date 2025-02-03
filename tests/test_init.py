import os
from unittest.mock import patch

import pytest

from git_llm_commit import EnvironmentError, get_api_key, main


def test_get_api_key_success():
    test_key = "test-api-key"
    with patch.dict(os.environ, {"OPENAI_API_KEY": test_key}):
        assert get_api_key() == test_key


def test_get_api_key_missing():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError) as exc_info:
            get_api_key()
        assert str(exc_info.value) == "OPENAI_API_KEY environment variable is not set."


def test_main_environment_error():
    with (
        patch("git_llm_commit.load_dotenv"),
        patch("git_llm_commit.get_api_key", side_effect=EnvironmentError("Test error")),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_main_unexpected_error():
    test_key = "test-api-key"
    with (
        patch.dict(os.environ, {"OPENAI_API_KEY": test_key}),
        patch("git_llm_commit.load_dotenv"),
        patch("git_llm_commit.llm_commit", side_effect=RuntimeError("Test error")),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


def test_main_success():
    test_key = "test-api-key"
    with (
        patch.dict(os.environ, {"OPENAI_API_KEY": test_key}),
        patch("git_llm_commit.llm_commit") as mock_llm_commit,
        patch("git_llm_commit.load_dotenv"),
    ):
        main()
        mock_llm_commit.assert_called_once_with(api_key=test_key)


def test_main_missing_key():
    with patch.dict(os.environ, {}, clear=True), patch("git_llm_commit.load_dotenv"):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
