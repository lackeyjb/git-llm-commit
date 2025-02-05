#!/usr/bin/env python3
"""
git-llm-commit: Generate a Conventional Commit message from staged changes using an LLM.
Usage:
    Stage your changes, then run: git llm-commit
    (Ensure your OPENAI_API_KEY is set in your environment)

Environment Variables:
    OPENAI_API_KEY: Required. Your OpenAI API key.
    LLM_COMMIT_TEMPERATURE: Optional. Control the creativity of the LLM (0.0-1.0, default: 0.7).
"""

import os
import re
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
    temperature: float = float(os.getenv("LLM_COMMIT_TEMPERATURE", "0.7"))
    # Size thresholds for determining commit message detail level
    small_change_threshold: int = 50  # lines
    large_change_threshold: int = 200  # lines
    # Token limits for different change sizes
    small_change_tokens: int = 100
    medium_change_tokens: int = 200
    large_change_tokens: int = 400


def count_diff_lines(diff: str) -> int:
    """Count the number of changed lines in a git diff"""
    lines = diff.splitlines()
    count = 0
    for line in lines:
        # Don't count file metadata lines (+++/---), only single +/- lines
        if (
            (line.startswith("+") or line.startswith("-"))
            and not line.startswith("+++")
            and not line.startswith("---")
        ):
            count += 1
    return count


class GitCommand(Protocol):
    """Protocol for git command execution"""

    def get_diff(self) -> str: ...
    def get_editor(self) -> str: ...
    def commit(self, message: str) -> None: ...
    def get_staged_files(self) -> list[str]: ...


class RiskyFileDetector:
    """Detects potentially risky files in staged changes"""

    DEFAULT_PATTERNS = [
        r"\.env$",
        r"\.secret$",
        r"credentials.*",
        r".*_key$",
        r"secrets?\.(yml|yaml|json|toml)$",
    ]

    def detect_risky_files(self, files: list[str]) -> list[str]:
        """
        Check for potentially risky files in the staged changes.

        Args:
            files: List of staged file paths

        Returns:
            List of file paths that match risky patterns
        """

        risky_files = []
        for file in files:
            for pattern in self.DEFAULT_PATTERNS:
                if re.search(pattern, file):
                    risky_files.append(file)
                    break
        return risky_files


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

    def get_staged_files(self) -> list[str]:
        """Get list of staged files"""
        try:
            output = subprocess.check_output(
                ["git", "diff", "--cached", "--name-only"], universal_newlines=True
            )
            return [f for f in output.splitlines() if f]
        except subprocess.CalledProcessError as e:
            raise RuntimeError("Unable to get staged files") from e


class CommitMessageGenerator:
    """Generates commit messages using OpenAI's API"""

    def __init__(self, llm_client: OpenAI, config: CommitConfig):
        self.llm_client = llm_client
        self.config = config

    def generate(self, diff: str) -> str:
        system_message = self._get_system_message()

        # Determine message detail level based on diff size
        diff_size = count_diff_lines(diff)
        if diff_size <= self.config.small_change_threshold:
            max_tokens = self.config.small_change_tokens
            detail_level = "concise"
        elif diff_size <= self.config.large_change_threshold:
            max_tokens = self.config.medium_change_tokens
            detail_level = "moderate"
        else:
            max_tokens = self.config.large_change_tokens
            detail_level = "detailed"

        user_message = (
            f"Git diff:\n\n{diff}\n\n"
            f"Generate a {detail_level} commit message following the Conventional "
            f"Commits specification. This is a {detail_level} change with {diff_size} "
            "lines modified."
        )

        try:
            response = self.llm_client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                temperature=self.config.temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            error_msg = f"Error calling OpenAI API: {e}"
            raise RuntimeError(error_msg) from e

        if not response.choices[0].message.content:
            raise RuntimeError("Received empty response from OpenAI API")

        return response.choices[0].message.content.strip().strip("`")

    def _get_system_message(self) -> str:
        return (
            "You are a commit message generator that strictly follows the Conventional "
            "Commits specification. "
            "Given a git diff, generate a commit message that adheres to the following "
            "format:\n\n"
            "  <type>[optional scope]: <description>\n\n"
            "  [optional body]\n\n"
            "  [optional footer(s)]\n\n"
            "Where:\n"
            f"  - type is one of: {', '.join(CONVENTIONAL_COMMIT_TYPES)}.\n"
            "  - scope is optional and should be included if it clarifies the affected "
            "area of code.\n"
            "  - The description is a concise summary of the change.\n"
            "  - For small changes, provide only a clear description line.\n"
            "  - For moderate changes, include a brief body explaining key changes.\n"
            "  - For large changes, provide a detailed body and relevant footers.\n"
            "  - The body (if provided) explains the reasoning and details of the "
            "change.\n"
            "  - Footers (if applicable) may include BREAKING CHANGE information or "
            "issue references.\n\n"
            "Ensure that the commit message comprehensively and accurately reflects all"
            " changes shown in the diff, with detail appropriate to the change size."
        )


class CommitMessageEditor:
    """Handles editing of commit messages"""

    def edit_message(self, message: str, editor: str) -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write(message)
            tmp_path = tmp.name

        try:
            subprocess.call([editor, tmp_path])
            with open(tmp_path) as tmp:
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


def prompt_risky_files(files: list[str]) -> bool:
    """Prompt user about risky files and return whether to proceed"""
    print("\nPotentially risky files staged:")
    for file in files:
        print(f"  - {file}")
    return input("\nCommit anyway? (y/N): ").lower().startswith("y")


def llm_commit(api_key: str) -> None:
    """Main function to handle the commit process"""
    git = GitCommandLine()
    config = CommitConfig()
    llm_client = OpenAI(api_key=api_key)
    generator = CommitMessageGenerator(llm_client, config)
    editor = CommitMessageEditor()

    try:
        # Check for risky files first
        staged_files = git.get_staged_files()
        detector = RiskyFileDetector()
        risky_files = detector.detect_risky_files(staged_files)

        if risky_files and not prompt_risky_files(risky_files):
            print("Commit aborted.")
            sys.exit(1)

        # Proceed with normal commit flow
        diff = git.get_diff()
        if not diff.strip():
            msg = "No staged changes found. Please stage your changes and try again."
            print(msg)
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
                    "Please enter 'y' to commit, 'n' to abort, or 'e' to edit the "
                    "message."
                )

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
