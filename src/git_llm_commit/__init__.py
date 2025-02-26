#!/usr/bin/env python3
"""Initialize git-llm-commit and handle environment setup."""

import argparse
import os
import sys

from dotenv import load_dotenv

from .llm_commit import llm_commit

__version__ = "2.1.0"


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


def main(argv=None) -> None:
    """
    Main entry point for the git-llm-commit command.
    Handles environment setup and error handling.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Generate a Conventional Commit message from staged changes using an LLM."
        )
    )
    parser.add_argument(
        "--dynamic",
        "-d",
        action="store_true",
        help=(
            "Generate a detailed commit message with body and footer, "
            "based on change size."
        ),
    )
    parser.add_argument(
        "--version", "-v", action="version", version=f"git-llm-commit {__version__}"
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    try:
        load_dotenv()
        api_key = get_api_key()
        llm_commit(api_key=api_key, dynamic_length=args.dynamic)
    except EnvironmentError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
