import subprocess
import sys
from unittest.mock import MagicMock, call, patch

import pytest
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

from git_llm_commit.llm_commit import (
    CONVENTIONAL_COMMIT_TYPES,
    CommitConfig,
    CommitMessageEditor,
    CommitMessageGenerator,
    GitCommandLine,
    RiskyFileDetector,
    count_diff_lines,
    llm_commit,
    prompt_user,
)

# Test data
SAMPLE_DIFF = """diff --git a/test.py b/test.py
index 1234567..89abcdef 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
+def new_feature():
     return "Hello, World!"
"""

SAMPLE_COMMIT_MESSAGE = "feat: add new greeting function"

# Test data for risky files
SAMPLE_STAGED_FILES = [
    "src/app.py",
    "src/.env",
    "config/credentials.json",
    "test/test_app.py",
]


def test_risky_file_detector():
    """Test risky file detection"""
    detector = RiskyFileDetector()
    risky_files = detector.detect_risky_files(SAMPLE_STAGED_FILES)
    assert len(risky_files) == 2
    assert "src/.env" in risky_files
    assert "config/credentials.json" in risky_files
    assert "src/app.py" not in risky_files
    assert "test/test_app.py" not in risky_files


def test_get_staged_files_success():
    """Test successful staged files retrieval"""
    git = GitCommandLine()
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value = "file1.py\nfile2.py\n"
        result = git.get_staged_files()
        assert result == ["file1.py", "file2.py"]
        mock_check_output.assert_called_once_with(
            ["git", "diff", "--cached", "--name-only"], universal_newlines=True
        )


def test_get_staged_files_error():
    """Test staged files error handling"""
    git = GitCommandLine()
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "cmd")
        with pytest.raises(RuntimeError, match="Unable to get staged files"):
            git.get_staged_files()


def test_llm_commit_with_risky_files():
    """Test commit workflow with risky files"""
    with (
        patch("git_llm_commit.llm_commit.GitCommandLine") as mock_git,
        patch("git_llm_commit.llm_commit.OpenAI") as mock_openai,
        patch("git_llm_commit.llm_commit.prompt_user") as mock_prompt,
        patch("builtins.input") as mock_input,
        patch("builtins.print") as mock_print,
    ):
        # Setup mocks
        mock_git_instance = MagicMock()
        mock_git_instance.get_diff.return_value = SAMPLE_DIFF
        mock_git_instance.get_staged_files.return_value = SAMPLE_STAGED_FILES
        mock_git.return_value = mock_git_instance

        mock_openai_instance = MagicMock()
        mock_response = ChatCompletion(
            id="mock-id",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        content=SAMPLE_COMMIT_MESSAGE, role="assistant"
                    ),
                    finish_reason="stop",
                )
            ],
            created=1234567890,
            model="gpt-4-turbo",
            object="chat.completion",
        )
        mock_openai_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_openai_instance

        # First prompt is for risky files, second for commit message
        mock_input.side_effect = ["y"]
        mock_prompt.return_value = "y"

        # Execute
        llm_commit("fake-api-key")

        # Verify
        mock_git_instance.get_staged_files.assert_called_once()
        mock_print.assert_has_calls(
            [
                call("\nPotentially risky files staged:"),
                call("  - src/.env"),
                call("  - config/credentials.json"),
            ],
            any_order=False,
        )
        mock_git_instance.commit.assert_called_once_with(SAMPLE_COMMIT_MESSAGE)


def test_count_diff_lines():
    """Test counting changed lines in git diff"""
    diff = """diff --git a/test.py b/test.py
index 1234567..89abcdef 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
+def new_feature():
-def old_feature():
     return "Hello, World!"
+    print("New line")"""

    count = count_diff_lines(diff)
    assert count == 3  # One addition, one deletion, one more addition


def test_commit_config_defaults():
    """Test CommitConfig initialization with default values"""
    config = CommitConfig()
    assert config.model == "gpt-4-turbo"
    assert config.temperature == 0.7
    assert config.small_change_threshold == 50
    assert config.large_change_threshold == 200
    assert config.small_change_tokens == 100
    assert config.medium_change_tokens == 200
    assert config.large_change_tokens == 400


def test_commit_config_custom():
    """Test CommitConfig initialization with custom values"""
    config = CommitConfig(
        model="gpt-3.5-turbo",
        temperature=0.5,
        small_change_threshold=30,
        large_change_threshold=150,
        small_change_tokens=80,
        medium_change_tokens=150,
        large_change_tokens=300,
    )
    assert config.model == "gpt-3.5-turbo"
    assert config.temperature == 0.5
    assert config.small_change_threshold == 30
    assert config.large_change_threshold == 150
    assert config.small_change_tokens == 80
    assert config.medium_change_tokens == 150
    assert config.large_change_tokens == 300


def test_generate_commit_message_size_based():
    """Test commit message generation with different diff sizes"""
    mock_client = MagicMock()
    config = CommitConfig()

    # Test small change
    small_diff = "+one line change"
    generator = CommitMessageGenerator(mock_client, config)
    generator.generate(small_diff)

    small_call_args = mock_client.chat.completions.create.call_args[1]
    assert small_call_args["max_tokens"] == config.small_change_tokens
    assert "concise" in small_call_args["messages"][1]["content"]

    # Reset mock for medium change test
    mock_client.reset_mock()
    medium_diff = "\n".join([f"+line {i}" for i in range(100)])
    generator.generate(medium_diff)

    medium_call_args = mock_client.chat.completions.create.call_args[1]
    assert medium_call_args["max_tokens"] == config.medium_change_tokens
    assert "moderate" in medium_call_args["messages"][1]["content"]

    # Reset mock for large change test
    mock_client.reset_mock()
    large_diff = "\n".join([f"+line {i}" for i in range(300)])
    generator.generate(large_diff)

    large_call_args = mock_client.chat.completions.create.call_args[1]
    assert large_call_args["max_tokens"] == config.large_change_tokens
    assert "detailed" in large_call_args["messages"][1]["content"]


def test_get_diff_success():
    """Test successful git diff retrieval"""
    git = GitCommandLine()
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.return_value = SAMPLE_DIFF
        result = git.get_diff()
        assert result == SAMPLE_DIFF
        mock_check_output.assert_called_once_with(
            ["git", "diff", "--cached"], universal_newlines=True
        )


def test_get_diff_error():
    """Test git diff error handling"""
    git = GitCommandLine()
    with patch("subprocess.check_output") as mock_check_output:
        mock_check_output.side_effect = subprocess.CalledProcessError(1, "cmd")
        with pytest.raises(RuntimeError, match="Unable to obtain staged diff"):
            git.get_diff()


def test_get_editor_no_stdout():
    """Test git editor retrieval when stdout is None"""
    git = GitCommandLine()
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = None
        mock_popen.return_value = mock_process

        with pytest.raises(RuntimeError, match="Failed to get git editor"):
            git.get_editor()


def test_get_editor_success():
    """Test successful git editor retrieval"""
    git = GitCommandLine()
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout.read.return_value = b"vim\n"
        mock_popen.return_value = mock_process

        editor = git.get_editor()
        assert editor == "vim"
        mock_popen.assert_called_once_with(
            ["git", "var", "GIT_EDITOR"], stdout=subprocess.PIPE
        )


def test_get_editor_error():
    """Test git editor error handling"""
    git = GitCommandLine()
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.side_effect = subprocess.SubprocessError("Command failed")
        with pytest.raises(RuntimeError, match="Error getting git editor"):
            git.get_editor()


def test_commit_execution():
    """Test git commit execution"""
    git = GitCommandLine()
    with patch("subprocess.run") as mock_run:
        git.commit(SAMPLE_COMMIT_MESSAGE)
        mock_run.assert_called_once_with(["git", "commit", "-m", SAMPLE_COMMIT_MESSAGE])


def test_generate_commit_message_with_backticks():
    """Test commit message generation with backticks in response"""
    mock_client = MagicMock()
    mock_response = ChatCompletion(
        id="mock-id",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    content="`" + SAMPLE_COMMIT_MESSAGE + "`", role="assistant"
                ),
                finish_reason="stop",
            )
        ],
        created=1234567890,
        model="gpt-4-turbo",
        object="chat.completion",
    )
    mock_client.chat.completions.create.return_value = mock_response

    config = CommitConfig()
    generator = CommitMessageGenerator(mock_client, config)
    result = generator.generate(SAMPLE_DIFF)
    assert result == SAMPLE_COMMIT_MESSAGE


def test_generate_commit_message():
    """Test successful commit message generation"""
    mock_client = MagicMock()
    mock_response = ChatCompletion(
        id="mock-id",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    content=SAMPLE_COMMIT_MESSAGE, role="assistant"
                ),
                finish_reason="stop",
            )
        ],
        created=1234567890,
        model="gpt-4-turbo",
        object="chat.completion",
    )
    mock_client.chat.completions.create.return_value = mock_response

    config = CommitConfig()
    generator = CommitMessageGenerator(mock_client, config)
    result = generator.generate(SAMPLE_DIFF)
    assert result == SAMPLE_COMMIT_MESSAGE

    # Verify the API was called with correct parameters
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args[1]
    assert call_args["model"] == "gpt-4-turbo"
    assert call_args["temperature"] == 0.7
    assert (
        call_args["max_tokens"] == config.small_change_tokens
    )  # Small diff = 100 tokens
    assert len(call_args["messages"]) == 2
    assert call_args["messages"][0]["role"] == "system"
    assert call_args["messages"][1]["role"] == "user"
    assert "Git diff:" in call_args["messages"][1]["content"]


def test_generate_commit_message_api_error():
    """Test API error handling in commit message generation"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API Error")

    config = CommitConfig()
    generator = CommitMessageGenerator(mock_client, config)
    with pytest.raises(RuntimeError, match="Error calling OpenAI API"):
        generator.generate(SAMPLE_DIFF)


def test_generate_commit_message_empty_response():
    """Test handling of empty API response"""
    mock_client = MagicMock()
    mock_response = ChatCompletion(
        id="mock-id",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(content="", role="assistant"),
                finish_reason="stop",
            )
        ],
        created=1234567890,
        model="gpt-4-turbo",
        object="chat.completion",
    )
    mock_client.chat.completions.create.return_value = mock_response

    config = CommitConfig()
    generator = CommitMessageGenerator(mock_client, config)
    with pytest.raises(RuntimeError, match="Received empty response from OpenAI API"):
        generator.generate(SAMPLE_DIFF)


def test_system_message_content():
    """Test system message content and format"""
    generator = CommitMessageGenerator(MagicMock(), CommitConfig())
    system_message = generator._get_system_message()

    # Check essential components
    assert "You are a commit message generator" in system_message
    assert "Conventional Commits specification" in system_message
    assert "<type>[optional scope]: <description>" in system_message
    assert "[optional body]" in system_message
    assert "[optional footer(s)]" in system_message

    # Verify all commit types are included
    for commit_type in CONVENTIONAL_COMMIT_TYPES:
        assert commit_type in system_message


def test_commit_message_editor(tmp_path):
    """Test commit message editing functionality"""
    editor = CommitMessageEditor()
    test_message = "test: initial commit"
    test_editor = "echo"  # Simple command that will succeed

    # Create a temporary file that actually exists
    test_file = tmp_path / "commit_message.txt"
    test_file.write_text(test_message)

    with (
        patch("tempfile.NamedTemporaryFile") as mock_temp_file,
        patch("subprocess.call") as mock_call,
        patch("builtins.open", create=True) as mock_open,
    ):
        # Configure the mock to return our real temporary file
        mock_named_temp = MagicMock()
        mock_named_temp.name = str(test_file)
        mock_temp_file.return_value.__enter__.return_value = mock_named_temp

        # Mock the file read after editing
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = "modified: test commit"
        mock_open.return_value = mock_file

        result = editor.edit_message(test_message, test_editor)

        # Verify the editor command was called with correct arguments
        mock_call.assert_called_once_with([test_editor, str(test_file)])

        # Verify the result matches the mocked edited content
        assert result == "modified: test commit"


def test_prompt_user(monkeypatch):
    """Test user prompt functionality"""
    test_inputs = ["y", "n", "e", "invalid", "y"]
    input_iterator = iter(test_inputs)

    def mock_input(_):
        return next(input_iterator)

    monkeypatch.setattr("builtins.input", mock_input)

    # Test 'y' response
    assert prompt_user("test message") == "y"

    # Test 'n' response
    assert prompt_user("test message") == "n"

    # Test 'e' response
    assert prompt_user("test message") == "e"

    # Test invalid response followed by valid response
    assert prompt_user("test message") == "invalid"
    assert prompt_user("test message") == "y"


def test_llm_commit_happy_path():
    """Test successful commit workflow with immediate acceptance"""
    with (
        patch("git_llm_commit.llm_commit.GitCommandLine") as mock_git,
        patch("git_llm_commit.llm_commit.OpenAI") as mock_openai,
        patch("git_llm_commit.llm_commit.prompt_user") as mock_prompt,
    ):
        # Setup mocks
        mock_git_instance = MagicMock()
        mock_git_instance.get_diff.return_value = SAMPLE_DIFF
        mock_git.return_value = mock_git_instance

        mock_openai_instance = MagicMock()
        mock_response = ChatCompletion(
            id="mock-id",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        content=SAMPLE_COMMIT_MESSAGE, role="assistant"
                    ),
                    finish_reason="stop",
                )
            ],
            created=1234567890,
            model="gpt-4-turbo",
            object="chat.completion",
        )
        mock_openai_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_openai_instance

        mock_prompt.return_value = "y"

        # Execute
        llm_commit("fake-api-key")

        # Verify
        mock_git_instance.get_diff.assert_called_once()
        mock_git_instance.commit.assert_called_once_with(SAMPLE_COMMIT_MESSAGE)
        mock_prompt.assert_called_once()


def test_llm_commit_empty_diff():
    """Test handling of empty git diff"""
    with (
        patch("git_llm_commit.llm_commit.GitCommandLine") as mock_git,
        patch("builtins.print") as mock_print,
        patch("sys.exit") as mock_exit,
    ):
        # Setup mocks
        mock_git_instance = MagicMock()
        mock_git_instance.get_diff.return_value = "   "  # Empty or whitespace diff
        mock_git.return_value = mock_git_instance

        # Mock sys.exit to prevent actual exit
        mock_exit.side_effect = SystemExit

        # Execute and verify it raises SystemExit
        with pytest.raises(SystemExit):
            llm_commit("fake-api-key")

        # Verify the correct message was printed
        mock_print.assert_called_with(
            "No staged changes found. Please stage your changes and try again."
        )
        mock_exit.assert_called_once_with(0)


def test_llm_commit_abort():
    """Test commit workflow when user aborts"""
    with (
        patch("git_llm_commit.llm_commit.GitCommandLine") as mock_git,
        patch("git_llm_commit.llm_commit.OpenAI") as mock_openai,
        patch("git_llm_commit.llm_commit.prompt_user") as mock_prompt,
        patch("builtins.print") as mock_print,
        patch("sys.exit") as mock_exit,
    ):
        # Setup mocks
        mock_git_instance = MagicMock()
        mock_git_instance.get_diff.return_value = SAMPLE_DIFF
        mock_git.return_value = mock_git_instance

        mock_openai_instance = MagicMock()
        mock_response = ChatCompletion(
            id="mock-id",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        content=SAMPLE_COMMIT_MESSAGE, role="assistant"
                    ),
                    finish_reason="stop",
                )
            ],
            created=1234567890,
            model="gpt-4-turbo",
            object="chat.completion",
        )
        mock_openai_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_openai_instance

        mock_prompt.return_value = "n"
        mock_exit.side_effect = SystemExit

        # Execute and verify it raises SystemExit
        with pytest.raises(SystemExit):
            llm_commit("fake-api-key")

        # Verify
        mock_print.assert_called_with("Commit aborted.")
        mock_exit.assert_called_with(0)
        mock_git_instance.commit.assert_not_called()


def test_llm_commit_edit_flow():
    """Test commit workflow with message editing"""
    with (
        patch("git_llm_commit.llm_commit.GitCommandLine") as mock_git,
        patch("git_llm_commit.llm_commit.OpenAI") as mock_openai,
        patch("git_llm_commit.llm_commit.prompt_user") as mock_prompt,
        patch("git_llm_commit.llm_commit.CommitMessageEditor") as mock_editor,
    ):
        # Setup mocks
        mock_git_instance = MagicMock()
        mock_git_instance.get_diff.return_value = SAMPLE_DIFF
        mock_git_instance.get_editor.return_value = "vim"
        mock_git.return_value = mock_git_instance

        mock_openai_instance = MagicMock()
        mock_response = ChatCompletion(
            id="mock-id",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        content=SAMPLE_COMMIT_MESSAGE, role="assistant"
                    ),
                    finish_reason="stop",
                )
            ],
            created=1234567890,
            model="gpt-4-turbo",
            object="chat.completion",
        )
        mock_openai_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_openai_instance

        mock_editor_instance = MagicMock()
        edited_message = "feat(core): improved greeting function"
        mock_editor_instance.edit_message.return_value = edited_message
        mock_editor.return_value = mock_editor_instance

        # Simulate edit then accept flow
        mock_prompt.side_effect = ["e", "y"]

        # Execute
        llm_commit("fake-api-key")

        # Verify
        mock_git_instance.get_editor.assert_called_once()
        mock_editor_instance.edit_message.assert_called_once_with(
            SAMPLE_COMMIT_MESSAGE, "vim"
        )
        mock_git_instance.commit.assert_called_once_with(edited_message)
        assert mock_prompt.call_count == 2


def test_llm_commit_invalid_input_flow():
    """Test commit workflow with invalid input followed by valid input"""
    with (
        patch("git_llm_commit.llm_commit.GitCommandLine") as mock_git,
        patch("git_llm_commit.llm_commit.OpenAI") as mock_openai,
        patch("git_llm_commit.llm_commit.prompt_user") as mock_prompt,
        patch("builtins.print") as mock_print,
    ):
        # Setup mocks
        mock_git_instance = MagicMock()
        mock_git_instance.get_diff.return_value = SAMPLE_DIFF
        mock_git.return_value = mock_git_instance

        mock_openai_instance = MagicMock()
        mock_response = ChatCompletion(
            id="mock-id",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        content=SAMPLE_COMMIT_MESSAGE, role="assistant"
                    ),
                    finish_reason="stop",
                )
            ],
            created=1234567890,
            model="gpt-4-turbo",
            object="chat.completion",
        )
        mock_openai_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_openai_instance

        # Simulate invalid input followed by valid input
        mock_prompt.side_effect = ["x", "y"]

        # Execute
        llm_commit("fake-api-key")

        # Verify
        assert mock_prompt.call_count == 2
        mock_print.assert_any_call(
            "Please enter 'y' to commit, 'n' to abort, or 'e' to edit the message."
        )
        mock_git_instance.commit.assert_called_once_with(SAMPLE_COMMIT_MESSAGE)


def test_llm_commit_abort_with_risky_files():
    """Test commit abort when risky files are present and user declines"""
    with (
        patch("git_llm_commit.llm_commit.GitCommandLine") as mock_git,
        patch("git_llm_commit.llm_commit.prompt_risky_files") as mock_prompt_risky,
        patch("builtins.print") as mock_print,
        patch("sys.exit") as mock_exit,
    ):
        # Setup mocks
        mock_git_instance = MagicMock()
        mock_git_instance.get_staged_files.return_value = SAMPLE_STAGED_FILES
        mock_git.return_value = mock_git_instance

        # User declines to proceed with risky files
        mock_prompt_risky.return_value = False

        # Mock sys.exit to prevent actual exit
        mock_exit.side_effect = SystemExit

        # Execute and verify it raises SystemExit
        with pytest.raises(SystemExit):
            llm_commit("fake-api-key")

        # Verify
        mock_git_instance.get_staged_files.assert_called_once()
        mock_prompt_risky.assert_called_once()
        mock_print.assert_called_with("Commit aborted.")
        mock_exit.assert_called_with(1)
        mock_git_instance.commit.assert_not_called()


def test_llm_commit_no_prompt_without_risky_files():
    """Test no risky file prompt when no risky files present"""
    with (
        patch("git_llm_commit.llm_commit.GitCommandLine") as mock_git,
        patch("git_llm_commit.llm_commit.prompt_risky_files") as mock_prompt_risky,
        patch("git_llm_commit.llm_commit.OpenAI") as mock_openai,
        patch("git_llm_commit.llm_commit.prompt_user") as mock_prompt,
    ):
        # Setup mocks
        mock_git_instance = MagicMock()
        mock_git_instance.get_staged_files.return_value = [
            "src/app.py",
            "test/test_app.py",
        ]  # No risky files
        mock_git_instance.get_diff.return_value = SAMPLE_DIFF
        mock_git.return_value = mock_git_instance

        mock_openai_instance = MagicMock()
        mock_response = ChatCompletion(
            id="mock-id",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        content=SAMPLE_COMMIT_MESSAGE, role="assistant"
                    ),
                    finish_reason="stop",
                )
            ],
            created=1234567890,
            model="gpt-4-turbo",
            object="chat.completion",
        )
        mock_openai_instance.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_openai_instance

        mock_prompt.return_value = "y"

        # Execute
        llm_commit("fake-api-key")

        # Verify
        mock_git_instance.get_staged_files.assert_called_once()
        mock_prompt_risky.assert_not_called()  # Should not prompt for risky files
        mock_git_instance.commit.assert_called_once_with(SAMPLE_COMMIT_MESSAGE)


def test_llm_commit_runtime_error():
    """Test handling of runtime errors in commit workflow"""
    with (
        patch("git_llm_commit.llm_commit.GitCommandLine") as mock_git,
        patch("builtins.print") as mock_print,
        patch("sys.exit") as mock_exit,
    ):
        mock_git_instance = MagicMock()
        mock_git_instance.get_diff.side_effect = RuntimeError("Git error")
        mock_git.return_value = mock_git_instance

        # Mock sys.exit to prevent actual exit
        mock_exit.side_effect = SystemExit

        # Execute and verify it raises SystemExit
        with pytest.raises(SystemExit):
            llm_commit("fake-api-key")

        # Verify error handling
        mock_print.assert_called_with("Error: Git error", file=sys.stderr)
        mock_exit.assert_called_with(1)
