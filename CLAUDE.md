# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Git Commit AI is an AI-powered git commit message generator implemented as a single Python script (`git_commitai.py`, ~1700 lines). It analyzes staged changes and generates meaningful, conventional commit messages using AI APIs. The core philosophy is to be a **perfect drop-in replacement for `git commit`** - any behavioral difference from standard git commit is considered a bug.

## Development Commands

### Testing
```bash
# Run all tests with coverage
pytest --cov=git_commitai --cov-report=html

# Run specific test file
pytest tests/test_commit_message.py

# Run specific test
pytest tests/test_flags/test_amend.py -v

# Run tests matching pattern
pytest -k "test_api" -v

# Run with debug output
pytest -v --tb=short
```

### Code Quality
```bash
# Type checking (REQUIRED before commits)
mypy git_commitai.py

# Format code
black . --line-length 100

# Lint code
flake8 .

# Run all quality checks together
mypy git_commitai.py && black . --line-length 100 && flake8 .
```

### Manual Testing
```bash
# Test with debug output
python3 git_commitai.py --debug 2> debug.log

# Test with dry-run
python3 git_commitai.py --dry-run

# Test specific flags
python3 git_commitai.py --amend --dry-run
python3 git_commitai.py -a -v --debug
```

## Architecture

### Single Script Design
All functionality is contained in `git_commitai.py` - there are no modules or packages. This makes the tool easy to install and distribute as a single executable script.

### Key Components

**Configuration Loading** (`load_gitcommitai_config`, `get_env_config`, `read_gitmessage_template`):
- Loads `.gitcommitai` config files from repo root with optional model specification and custom prompt templates
- Supports `.gitmessage` templates with precedence: repo `.gitmessage` > git config template > `~/.gitmessage`
- Environment variables: `GIT_COMMIT_AI_KEY`, `GIT_COMMIT_AI_URL`, `GIT_COMMIT_AI_MODEL`
- CLI flags override env vars which override config files

**Git Operations** (`run_git`, `get_staged_files`, `get_git_diff`, `check_staged_changes`):
- All git commands go through `run_git()` which uses `subprocess.run()`
- `get_staged_files()` returns file contents for AI context (handles binary files specially)
- `get_git_diff()` gets unified diff (handles `--amend` mode)
- Supports auto-staging with `-a` flag via `stage_all_tracked_files()`

**AI Prompt Building** (`build_ai_prompt`):
- Custom prompts from `.gitcommitai` with placeholders: `{CONTEXT}`, `{DIFF}`, `{FILES}`, `{GITMESSAGE}`
- Default prompt enforces Git best practices: 50 char subject, imperative mood, optional body at 72 chars
- Includes file contents and diffs for full context

**API Communication** (`make_api_request`):
- Uses `urllib.request` (no external HTTP library dependencies)
- Retry logic: 3 attempts with exponential backoff (2s * 1.5^attempt)
- 5-minute timeout for requests
- OpenAI-compatible API format (works with OpenRouter, Anthropic, local LLMs)

**Editor Integration** (`create_commit_message_file`, `open_editor`, `strip_comments_and_save`):
- Creates temporary commit message file with AI-generated content
- Opens git editor (respects `GIT_EDITOR`, `VISUAL`, `EDITOR` env vars)
- Strips comments (lines starting with `#`) before final commit
- Detects empty commits after editing

**Security** (`redact_secrets`):
- Redacts API keys, tokens, passwords in debug output
- Pattern-based matching for various secret formats (Bearer tokens, Basic auth, env vars, etc.)

### Critical Design Decisions

1. **Git Compatibility First**: Every git commit flag should work identically. The `-m` flag is intentionally modified to provide AI context instead of the full message.

2. **No External Dependencies**: Uses only Python stdlib (`urllib`, `subprocess`, `json`, etc.) except for dev/test dependencies. This makes installation trivial.

3. **Type Safety**: Full type hints with mypy checking. CI enforces type checking on all Python versions 3.8-3.12.

4. **Debug Mode**: Global `DEBUG` flag controls `debug_log()` output to stderr with automatic secret redaction.

## Testing Strategy

### Test Organization
- `tests/conftest.py`: Shared fixtures (mock_args, mock_env_config, mock_git_repo, etc.)
- `tests/test_*.py`: Unit tests for specific functions
- `tests/test_flags/*.py`: Tests for individual git commit flags
- Pattern: Test both positive cases and edge cases (empty inputs, errors, boundary conditions)

### Common Fixtures
- `mock_env_config`: Mocks API configuration
- `mock_args`: Mock argparse.Namespace with default values
- `mock_git_repo`: Mocks subprocess.run for git commands
- `mock_staged_changes`: Mocks check for staged files
- `mock_editor_flow`: Mocks editor open/save workflow

### Testing Git Compatibility
When adding support for a new git commit flag:
1. Test actual git commit behavior extensively (edge cases, combinations)
2. Implement to match git exactly
3. Add tests verifying identical behavior (compare return codes, stderr, effects)
4. Update README.md flag support table

## Adding New Features

### Supporting a New Git Flag

1. **Research git behavior** - Study git docs and test edge cases
2. **Add to argparser** - Add argument in `main()` around line 1477
3. **Implement logic** - Usually in `main()` or pass to `run_git()`
4. **Type hints** - Add types to all new/modified functions
5. **Test** - Create `tests/test_flags/test_<flag>.py` comparing to git
6. **Run mypy** - Ensure type safety: `mypy git_commitai.py`
7. **Update docs** - Update man page (`git-commitai.1`) and README table
8. **Examples** - Add usage examples to README

### Custom Prompts and Config

- `.gitcommitai` files are loaded from repo root only (not home directory)
- Model specification is optional first line: `model: gpt-4`
- Prompt template follows with placeholders
- `{DIFF}` and `{FILES}` are always added at the end automatically

## Configuration Precedence

### Model Selection
1. CLI flag `--model` (highest priority)
2. Environment variable `GIT_COMMIT_AI_MODEL`
3. `.gitcommitai` file model specification
4. Default: `qwen/qwen3-coder`

### API Key/URL
1. CLI flags `--api-key`, `--api-url`
2. Environment variables `GIT_COMMIT_AI_KEY`, `GIT_COMMIT_AI_URL`
3. No defaults - user must provide

### Commit Message Templates
1. Repository `.gitmessage` (repo root)
2. Git config `commit.template`
3. Global `~/.gitmessage`

## CI/CD

- **GitHub Actions** (`.github/workflows/test.yml`):
  - Tests on Python 3.8, 3.9, 3.10, 3.11, 3.12
  - mypy type checking (required)
  - pytest with coverage
  - Integration tests on Ubuntu, macOS, Windows

- **Coverage**: Configured in `.coveragerc`, reports uploaded to Coveralls

## Common Gotchas

1. **Type hints are mandatory** - mypy will fail CI if missing or incorrect
2. **Mock subprocess carefully** - Use `mock_git_repo` fixture or patch `subprocess.run` return value
3. **Test amend mode** - Many functions have special `amend=True` parameter that changes git behavior
4. **Debug redaction** - `redact_secrets()` must catch new secret patterns before they leak in debug output
5. **Binary files** - `get_binary_file_info()` handles them specially (shows file info, not contents)
6. **Editor detection** - Uses git's editor preference order: `GIT_EDITOR` > `VISUAL` > `EDITOR` > `vi`

## Key Files

- `git_commitai.py` - Main script (all functionality)
- `git-commitai.1` - Man page (groff format)
- `install.sh` / `install.ps1` - Installation scripts
- `requirements.txt` - Dev/test dependencies only (no runtime deps)
- `pytest.ini` - Test configuration
- `.coveragerc` - Coverage configuration
- `mypy.ini` - Type checking configuration
