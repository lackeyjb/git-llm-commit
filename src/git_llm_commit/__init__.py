#!/usr/bin/env python3
import os
import sys

from dotenv import load_dotenv

from .llm_commit import llm_commit


def get_api_key() -> str:
    """Retrieve the OpenAI API key from the environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    return api_key


def main() -> None:
    load_dotenv(verbose=True)
    api_key = get_api_key()
    llm_commit(api_key=api_key)
