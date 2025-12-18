# Unit Tests for Multi Output Player

This directory contains comprehensive unit tests for the Multi Output Player application.

## Test Structure

```
tests/
├── __init__.py                          # Package marker
├── conftest.py                          # Shared pytest fixtures
├── test_player_config_schema.py         # Tests for Pydantic schemas
├── test_config_manager.py               # Tests for ConfigManager
├── test_audio_manager.py                # Tests for AudioManager
├── test_process_manager.py              # Tests for ProcessManager
└── README.md                            # This file
```

## Running Tests

### Prerequisites

Install the test dependencies:

```bash
pip install -r requirements.txt
```

This will install pytest and pytest-mock along with the application dependencies.

### Run All Tests

```bash
# Run all tests with verbose output
pytest tests/

# Or use the shorter form
pytest
```

### Run Specific Test Files

```bash
# Test only schema validation
pytest tests/test_player_config_schema.py

# Test only ConfigManager
pytest tests/test_config_manager.py

# Test only AudioManager
pytest tests/test_audio_manager.py

# Test only ProcessManager
pytest tests/test_process_manager.py
```

### Run Specific Test Classes or Functions

```bash
# Run a specific test class
pytest tests/test_config_manager.py::TestConfigManagerInit

# Run a specific test function
pytest tests/test_config_manager.py::TestConfigManagerInit::test_init_creates_directory
```

### Common pytest Options

```bash
# Show extra test summary info
pytest -ra

# Stop after first failure
pytest -x

# Stop after N failures
pytest --maxfail=3

# Show local variables in tracebacks
pytest -l

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Quiet mode (less verbose)
pytest -q

# Very verbose (show all test details)
pytest -vv

# Show print statements
pytest -s
```

## Test Coverage

The test suite covers:

### 1. Pydantic Schema Validation (`test_player_config_schema.py`)
- Base player configuration validation
- Squeezelite player configuration
- Sendspin player configuration
- Field validators (name, MAC address, URLs, log levels, etc.)
- Default values and type coercion
- Validation functions and error handling

### 2. ConfigManager (`test_config_manager.py`)
- Configuration file loading and saving
- YAML parsing and error handling
- Player CRUD operations (Create, Read, Update, Delete)
- Configuration validation on load/save
- Player renaming and existence checks
- Error handling for invalid configurations

### 3. AudioManager (`test_audio_manager.py`)
- Audio device detection (hardware and virtual)
- Mixer control enumeration
- Volume get/set operations
- Windows compatibility mode
- Error handling for missing tools (aplay, amixer)
- Virtual device handling

### 4. ProcessManager (`test_process_manager.py`)
- Process lifecycle management (start, stop)
- Process status checking
- Graceful shutdown (SIGTERM) and force kill (SIGKILL)
- Fallback command handling
- Process cleanup and monitoring
- Error handling for process failures

## Mocking Strategy

The tests use extensive mocking to avoid:
- File system I/O (using `tmp_path` fixture and mocked file operations)
- Subprocess calls (mocking `subprocess.run` and `subprocess.Popen`)
- System-specific operations (ALSA tools, process signals)

This ensures tests:
- Run quickly and reliably
- Work on any platform (including Windows)
- Don't require actual audio hardware
- Don't create/modify files outside test directories
- Don't spawn actual processes

## Fixtures

Key fixtures provided in `conftest.py`:

### Configuration Fixtures
- `temp_config_file` - Temporary config file path
- `temp_log_dir` - Temporary log directory
- `sample_squeezelite_config` - Valid Squeezelite configuration
- `sample_sendspin_config` - Valid Sendspin configuration
- `minimal_*_config` - Minimal valid configurations

### Invalid Configuration Fixtures
- `invalid_config_missing_name` - Missing required name
- `invalid_config_invalid_volume` - Volume out of range
- `invalid_config_bad_mac` - Malformed MAC address
- And more...

### Mock Fixtures
- `mock_aplay_output` - Simulated aplay output
- `mock_amixer_*_output` - Simulated amixer outputs
- `mock_process` - Mock running process
- `mock_failed_process` - Mock failed process

## Continuous Integration

These tests are designed to run in CI/CD pipelines. The pytest configuration in `pyproject.toml` includes:
- Strict marker checking
- Maximum failure limits
- Short traceback format
- Summary of all test outcomes

## Contributing

When adding new features:

1. Write tests first (TDD approach)
2. Ensure all tests pass: `pytest`
3. Check code style: `ruff check tests/`
4. Format code: `ruff format tests/`
5. Aim for high test coverage

## Troubleshooting

### Import Errors

If you see import errors, ensure you're running pytest from the project root:

```bash
cd /path/to/squeezelite-docker
pytest tests/
```

The `conftest.py` adds the `app/` directory to Python's path automatically.

### Missing Dependencies

If tests fail due to missing packages:

```bash
pip install -r requirements.txt
```

### Platform-Specific Issues

Tests are designed to be platform-agnostic. If you encounter platform-specific issues:
- Check that mocking is properly configured
- Ensure subprocess calls are mocked
- Verify file paths use `os.path.join()` or `Path`
