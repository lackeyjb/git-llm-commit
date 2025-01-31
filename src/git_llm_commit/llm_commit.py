#!/usr/bin/env python3
"""
git-llm-commit: Generate a Conventional Commit message from staged changes using an LLM.
Usage:
    Stage your changes, then run: git llm-commit
    (Ensure your OPENAI_API_KEY is set in your environment)
"""

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

# Constants
CONVENTIONAL_COMMIT_TYPES = [
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
]


@dataclass
class CommitConfig:
    """Configuration for commit message generation"""

    model: str = "gpt-4-turbo"
    temperature: float = 0.7
    max_tokens: int = 300


class GitCommand(Protocol):
    """Protocol for git command execution"""

    def get_diff(self) -> str: ...
    def get_editor(self) -> str: ...
    def commit(self, message: str) -> None: ...


class GitCommandLine:
    """Git command implementation using subprocess"""

    def get_diff(self) -> str:
        try:
            return subprocess.check_output(
                ["git", "diff", "--cached"], universal_newlines=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError("Unable to obtain staged diff") from e

    def get_editor(self) -> str:
        try:
            process = subprocess.Popen(
                ["git", "var", "GIT_EDITOR"], stdout=subprocess.PIPE
            )
            if process.stdout is None:
                raise RuntimeError("Failed to get git editor")
            return process.stdout.read().decode("utf-8").strip()
        except subprocess.SubprocessError as e:
            raise RuntimeError(f"Error getting git editor: {e}") from e

    def commit(self, message: str) -> None:
        subprocess.run(["git", "commit", "-m", message])


class CommitMessageGenerator:
    """Generates commit messages using OpenAI's API"""

    def __init__(self, llm_client: OpenAI, config: CommitConfig):
        self.llm_client = llm_client
        self.config = config

    def generate(self, diff: str) -> str:
        system_message = self._get_system_message()
        user_message = f"Git diff:\n\n{diff}\n\nGenerate a commit message following the Conventional Commits specification:"

        try:
            response = self.llm_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )
        except Exception as e:
            raise RuntimeError(f"Error calling OpenAI API: {e}") from e

        if not response.choices[0].message.content:
            raise RuntimeError("Received empty response from OpenAI API")

        return response.choices[0].message.content.strip().strip("`")

    def _get_system_message(self) -> str:
        return (
            "You are a commit message generator that strictly follows the Conventional Commits specification. "
            "Given a git diff, generate a commit message that adheres to the following format:\n\n"
            "  <type>[optional scope]: <description>\n\n"
            "  [optional body]\n\n"
            "  [optional footer(s)]\n\n"
            "Where:\n"
            f"  - type is one of: {', '.join(CONVENTIONAL_COMMIT_TYPES)}.\n"
            "  - scope is optional and should be included if it clarifies the affected area of code.\n"
            "  - The description is a concise summary of the change.\n"
            "  - The body (if provided) explains the reasoning and details of the change.\n"
            "  - Footers (if applicable) may include BREAKING CHANGE information or issue references.\n\n"
            "Ensure that the commit message comprehensively and accurately reflects all changes shown in the diff."
        )


class CommitMessageEditor:
    """Handles editing of commit messages"""

    def edit_message(self, message: str, editor: str) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write(message)
            tmp_path = tmp.name

        try:
            subprocess.call([editor, tmp_path])
            with open(tmp_path, "r") as tmp:
                return tmp.read()
        finally:
            os.unlink(tmp_path)


def prompt_user(message: str) -> str:
    """Prompts user for input and returns response"""
    print("\nGenerated commit message:")
    print("------------------------")
    print(message)
    print("------------------------")
    return input("\nDo you want to commit with this message? (y/n/e[dit]): ").lower()


def llm_commit(api_key: str) -> None:
    """Main function to handle the commit process"""
    git = GitCommandLine()
    config = CommitConfig()
    llm_client = OpenAI(api_key=api_key)
    generator = CommitMessageGenerator(llm_client, config)
    editor = CommitMessageEditor()

    try:
        diff = git.get_diff()
        if not diff.strip():
            print("No staged changes found. Please stage your changes and try again.")
            sys.exit(0)

        commit_message = generator.generate(diff)

        while True:
            response = prompt_user(commit_message)

            if response == "y":
                git.commit(commit_message)
                break
            elif response == "n":
                print("Commit aborted.")
                sys.exit(0)
            elif response == "e":
                git_editor = git.get_editor()
                commit_message = editor.edit_message(commit_message, git_editor)
                continue
            else:
                print(
                    "Please enter 'y' to commit, 'n' to abort, or 'e' to edit the message."
                )

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
