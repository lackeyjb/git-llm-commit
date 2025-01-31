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

from openai import OpenAI


def get_staged_diff():
    """Retrieve the diff of staged changes."""
    try:
        diff = subprocess.check_output(
            ["git", "diff", "--cached"], universal_newlines=True
        )
        return diff
    except subprocess.CalledProcessError:
        print("Error: Unable to obtain staged diff.", file=sys.stderr)
        sys.exit(1)


def generate_commit_message(diff: str, llm_client: OpenAI) -> str:
    """
    Use an LLM (via the OpenAI API) to generate a commit message in Conventional Commit format.

    The commit message should follow the format:

        <type>[optional scope]: <description>

        [optional body]

        [optional footer(s)]

    Where:
      - **type** is one of: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.
      - **scope** (if applicable) is a short string describing the area of code affected.
      - **description** is a brief summary of the change.
      - **body** provides additional context/details if necessary.
      - **footers** may include breaking changes (using "BREAKING CHANGE:") or issue references.
    """
    # Updated system message with instructions per the Conventional Commits specification.
    system_message = (
        "You are a commit message generator that strictly follows the Conventional Commits specification. "
        "Given a git diff, generate a commit message that adheres to the following format:\n\n"
        "  <type>[optional scope]: <description>\n\n"
        "  [optional body]\n\n"
        "  [optional footer(s)]\n\n"
        "Where:\n"
        "  - type is one of: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert.\n"
        "  - scope is optional and should be included if it clarifies the affected area of code.\n"
        "  - The description is a concise summary of the change.\n"
        "  - The body (if provided) explains the reasoning and details of the change.\n"
        "  - Footers (if applicable) may include BREAKING CHANGE information or issue references.\n\n"
        "Ensure that the commit message comprehensively and accurately reflects all changes shown in the diff."
    )

    # Prepare the prompt including the staged diff.
    user_message = f"Git diff:\n\n{diff}\n\nGenerate a commit message following the Conventional Commits specification:"

    try:
        response = llm_client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            temperature=0.7,
            max_tokens=300,  # Increased tokens to allow for body/footers if needed.
        )
    except Exception as e:
        print(f"Error calling OpenAI API: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract and return the generated commit message.
    commit_message = response.choices[0].message.content
    if commit_message is None:
        print("Error: Received empty response from OpenAI API", file=sys.stderr)
        sys.exit(1)
    # Remove any backticks (single or triple) that might wrap the commit message
    cleaned_message = commit_message.strip().strip("`")
    return cleaned_message


def llm_commit(api_key: str):
    # Ensure the API key is available.
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    diff = get_staged_diff()
    if not diff.strip():
        print("No staged changes found. Please stage your changes and try again.")
        sys.exit(0)

    llm_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    commit_message = generate_commit_message(diff, llm_client)

    print("\nGenerated commit message:")
    print("------------------------")
    print(commit_message)
    print("------------------------")

    while True:
        response = input(
            "\nDo you want to commit with this message? (y/n/e[dit]): "
        ).lower()
        if response == "y":
            subprocess.run(["git", "commit", "-m", commit_message])
            break
        elif response == "n":
            print("Commit aborted.")
            sys.exit(0)
        elif response == "e":
            # Open the commit message in the default editor
            try:
                editor_process = subprocess.Popen(
                    ["git", "var", "GIT_EDITOR"], stdout=subprocess.PIPE
                )
                if editor_process.stdout is None:
                    raise subprocess.SubprocessError("Failed to get git editor")
                editor = editor_process.stdout.read().decode("utf-8").strip()
            except subprocess.SubprocessError as e:
                print(f"Error getting git editor: {e}", file=sys.stderr)
                sys.exit(1)

            # Write commit message to temporary file
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            ) as tmp:
                tmp.write(commit_message)
                tmp_path = tmp.name

            # Open editor with the temporary file
            subprocess.call([editor, tmp_path])

            # Read edited message
            with open(tmp_path, "r") as tmp:
                commit_message = tmp.read()

            # Clean up temporary file
            os.unlink(tmp_path)

            # Show the edited message and confirm again
            print("\nEdited commit message:")
            print("------------------------")
            print(commit_message)
            print("------------------------")
            continue
        else:
            print(
                "Please enter 'y' to commit, 'n' to abort, or 'e' to edit the message."
            )
