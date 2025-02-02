import subprocess
import pytest
from unittest.mock import patch, MagicMock
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from git_llm_commit.llm_commit import (
    GitCommandLine,
    CommitMessageGenerator,
    CommitConfig,
    CommitMessageEditor,
    prompt_user,
    CONVENTIONAL_COMMIT_TYPES,
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


def test_commit_config_defaults():
    """Test CommitConfig initialization with default values"""
    config = CommitConfig()
    assert config.model == "gpt-4-turbo"
    assert config.temperature == 0.7
    assert config.max_tokens == 300


def test_commit_config_custom():
    """Test CommitConfig initialization with custom values"""
    config = CommitConfig(model="gpt-3.5-turbo", temperature=0.5, max_tokens=200)
    assert config.model == "gpt-3.5-turbo"
    assert config.temperature == 0.5
    assert config.max_tokens == 200


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
    assert call_args["max_tokens"] == 300
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
