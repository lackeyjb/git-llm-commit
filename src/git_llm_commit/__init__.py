#!/usr/bin/env python3
"""Initialize git-llm-commit and handle environment setup."""

import os
import sys

from dotenv import load_dotenv

from .llm_commit import llm_commit

__version__ = "2.0.0"


class EnvironmentError(Exception):
    """Raised when required environment variables are missing."""

    pass


def get_api_key() -> str:
    """
    Retrieve the API key from the environment, preferring OpenRouter if available.

    Returns:
        str: The API key (OpenRouter or OpenAI)

    Raises:
        EnvironmentError: If neither OPENROUTER_API_KEY nor OPENAI_API_KEY is set.
    """
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if openrouter_key:
        return openrouter_key
    elif openai_key:
        return openai_key
    else:
        raise EnvironmentError(
            "Neither OPENROUTER_API_KEY nor OPENAI_API_KEY environment variable is set."
        )


def main() -> None:
    """
    Main entry point for the git-llm-commit command.
    Handles environment setup and error handling.
    """
    try:
        load_dotenv()
        api_key = get_api_key()
        llm_commit(api_key=api_key)
    except EnvironmentError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
