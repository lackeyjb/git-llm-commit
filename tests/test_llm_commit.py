import subprocess
import pytest
from unittest.mock import patch, MagicMock
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from git_llm_commit.llm_commit import get_staged_diff, generate_commit_message

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

def test_get_staged_diff_success():
    with patch('subprocess.check_output') as mock_check_output:
        mock_check_output.return_value = SAMPLE_DIFF
        result = get_staged_diff()
        assert result == SAMPLE_DIFF
        mock_check_output.assert_called_once_with(
            ["git", "diff", "--cached"],
            universal_newlines=True
        )

def test_get_staged_diff_error():
    with patch('subprocess.check_output') as mock_check_output:
        mock_check_output.side_effect = subprocess.CalledProcessError(1, 'cmd')
        with pytest.raises(SystemExit) as exc_info:
            get_staged_diff()
        assert exc_info.value.code == 1

def test_generate_commit_message():
    # Create a mock OpenAI client
    mock_client = MagicMock()
    
    # Create a mock response that matches the OpenAI API structure
    mock_response = ChatCompletion(
        id="mock-id",
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(
                    content=SAMPLE_COMMIT_MESSAGE,
                    role="assistant"
                ),
                finish_reason="stop"
            )
        ],
        created=1234567890,
        model="gpt-4-turbo",
        object="chat.completion"
    )
    
    mock_client.chat.completions.create.return_value = mock_response

    result = generate_commit_message(SAMPLE_DIFF, mock_client)
    assert result == SAMPLE_COMMIT_MESSAGE

    # Verify the API was called with correct parameters
    mock_client.chat.completions.create.assert_called_once()
    call_args = mock_client.chat.completions.create.call_args[1]
    assert call_args['model'] == "gpt-4-turbo"
    assert call_args['temperature'] == 0.7
    assert call_args['max_tokens'] == 300
    assert len(call_args['messages']) == 2
    assert call_args['messages'][0]['role'] == "system"
    assert call_args['messages'][1]['role'] == "user"

def test_generate_commit_message_api_error():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API Error")
    
    with pytest.raises(SystemExit) as exc_info:
        generate_commit_message(SAMPLE_DIFF, mock_client)
    assert exc_info.value.code == 1
