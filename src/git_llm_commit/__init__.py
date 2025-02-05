#!/usr/bin/env python3
"""Initialize git-llm-commit and handle environment setup."""

import os
import sys

from dotenv import load_dotenv

from .llm_commit import llm_commit

__version__ = "1.2.1"


class EnvironmentError(Exception):
    """Raised when required environment variables are missing."""

    pass


def get_api_key() -> str:
    """
    Retrieve the OpenAI API key from the environment.

    Returns:
        str: The OpenAI API key

    Raises:
        EnvironmentError: If OPENAI_API_KEY is not set
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")
    return api_key


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
