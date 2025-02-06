# git-llm-commit

[![codecov](https://codecov.io/github/syntax-sherlock/git-llm-commit/graph/badge.svg?token=YZECGT1JIF)](https://codecov.io/github/syntax-sherlock/git-llm-commit)

Generate Conventional Commit messages from your staged changes using an LLM.

## Description

`git-llm-commit` is a command-line tool that analyzes your staged git changes and generates a commit message following the [Conventional Commits](https://www.conventionalcommits.org/) specification using various LLM models, including OpenAI's GPT-4 and OpenRouter.

## Installation

1. Ensure you have Python 3.x installed
2. Install the package:
   ```bash
   pip install git-llm-commit
   ```

## Setup

1. Get an API key from your preferred LLM provider (e.g., OpenAI, OpenRouter)
2. Set your API key in your environment:

   ```bash
   export OPENAI_API_KEY='your-api-key'
   ```

   Or create a `.env` file in your project root with:

   ```
   OPENAI_API_KEY=your-api-key
   ```

3. (Optional) Customize the LLM's creativity:

   ```bash
   export LLM_COMMIT_TEMPERATURE='0.5'  # More deterministic (0.0-1.0, default: 0.7)
   ```

   Or in your `.env` file:

   ```
   LLM_COMMIT_TEMPERATURE=0.5
   ```

4. (Optional) Use OpenRouter:

   - Get an OpenRouter API key from [OpenRouter's platform](https://openrouter.ai/)
   - Set your OpenRouter API key in your environment:

     ```bash
     export OPENROUTER_API_KEY='your-openrouter-api-key'
     ```

     Or in your `.env` file:

     ```
     OPENROUTER_API_KEY=your-openrouter-api-key
     ```

5. (Optional) Choose a custom model:

   - Set the model name in your environment:

     ```bash
     export LLM_COMMIT_MODEL='custom-model'
     ```

     Or in your `.env` file:

     ```
     LLM_COMMIT_MODEL=custom-model
     ```

## Usage

1. Stage your changes as usual:

   ```bash
   git add .
   ```

2. Instead of `git commit`, run:

   ```bash
   git llm-commit
   ```

3. Review the generated commit message and:
   - Press `y` to accept and commit
   - Press `n` to abort
   - Press `e` to edit the message before committing

## Features

- Generates commit messages following Conventional Commits format
- Uses various LLM models to analyze diffs and create meaningful commit messages
- Adapts commit message detail based on change size:
  - Small changes (≤50 lines): Concise, single-line messages
  - Medium changes (51-200 lines): Moderate detail with brief body
  - Large changes (>200 lines): Detailed messages with full body and footers
- Supports interactive editing of generated messages
- Integrates with your default git editor
- Respects conventional commit types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert
- Detects potentially risky files (like .env, credentials, secrets) and prompts for confirmation before committing
- Prioritizes OpenRouter API key if available, otherwise falls back to OpenAI API key
- Allows users to choose the model they would like to use

## Security Features

### Risky File Detection

The tool automatically scans staged files for potentially sensitive content like:

- `.env` files
- Files containing "secret" or "credentials" in the name
- Key files
- Secret/credential configuration files (yml, yaml, json, toml)

If such files are detected, you'll be prompted for confirmation before proceeding with the commit. This helps prevent accidental commits of sensitive information to your repository.

## Requirements

- Python 3.x
- Git
- API key from your preferred LLM provider (e.g., OpenAI, OpenRouter)

## License

[MIT License](LICENSE)
