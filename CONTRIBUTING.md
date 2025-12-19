# Contributing to Multi-Room Audio Docker

Thank you for your interest in contributing to this project!

## Quick Start for Contributors

1. **Fork the repository** on GitHub
2. **Clone your fork**: `git clone https://github.com/yourusername/squeezelite-docker.git`
3. **Create a feature branch**: `git checkout -b feature/amazing-feature`
4. **Make your changes** and test thoroughly
5. **Run linting**: `ruff check . && ruff format .`
6. **Run tests**: `pytest tests/ -v`
7. **Commit your changes**: `git commit -m 'Add amazing feature'`
8. **Push to your branch**: `git push origin feature/amazing-feature`
9. **Open a Pull Request**

## Development Setup

### Standalone Docker Development

```bash
# Start development environment
./manage.sh dev              # Linux
.\manage.ps1 dev             # Windows

# This enables:
# - Live code reloading
# - Debug mode
# - Development logging
```

### HAOS Add-on Development

```bash
# Build the add-on locally
cd hassio
docker build \
  --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11 \
  -t multiroom-audio-addon:local .

# Test locally (without full HAOS integration)
docker run --rm -it -p 8080:8080 -e AUDIO_BACKEND=alsa multiroom-audio-addon:local
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_squeezelite_provider.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Manual Testing

Before submitting a PR, please test:

```bash
# Test basic functionality
./manage.sh build && ./manage.sh start

# Test no-audio mode
./manage.sh no-audio

# Test API endpoints
curl http://localhost:8080/api/players
curl http://localhost:8080/api/devices
```

### Linting

This project uses Ruff for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

## Project Architecture

Understanding the architecture helps when contributing:

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Providers | `app/providers/` | Player backend implementations |
| Managers | `app/managers/` | Business logic (audio, config, process) |
| Schemas | `app/schemas/` | Pydantic validation models |
| Environment | `app/environment.py` | Docker/HAOS detection |

### Adding a New Provider

To add support for a new audio player backend:

1. Create `app/providers/newplayer.py` implementing `PlayerProvider`
2. Register in `app/providers/__init__.py`
3. Register in `app/app.py` provider registry
4. Add Pydantic schema in `app/schemas/player_config.py`
5. Update `app/health_check.py` to check for the binary
6. Update Dockerfiles to install the binary
7. Add tests in `tests/test_newplayer_provider.py`

See [ONBOARDING.md](ONBOARDING.md#adding-a-new-provider) for detailed instructions.

## What We're Looking For

- **Bug fixes** - Help make it more stable
- **New providers** - Support for additional audio players (Airplay, Spotify Connect, etc.)
- **New features** - Audio device support, UI improvements
- **Documentation** - Better setup guides, troubleshooting
- **HAOS improvements** - Better Home Assistant integration
- **Platform support** - macOS, different Linux distros
- **Docker improvements** - Better builds, smaller images
- **UI/UX enhancements** - Better web interface design
- **Test coverage** - More comprehensive test suite

## Coding Guidelines

### Python
- Follow PEP 8 (enforced by Ruff)
- Use type hints for function signatures
- Document complex logic with docstrings
- Keep functions focused and small

### JavaScript
- Use modern ES6+ features
- No external frameworks (vanilla JS only)

### Docker
- Multi-stage builds when possible
- Minimize layer count
- Use specific version tags for base images

### Documentation
- Update relevant docs for new features
- Keep ONBOARDING.md current for new engineers
- Document provider-specific quirks

## Environment Detection

When adding features that behave differently in Docker vs HAOS:

```python
from environment import is_hassio, get_audio_backend

if is_hassio():
    # HAOS-specific behavior (PulseAudio)
    pass
else:
    # Standalone Docker behavior (ALSA)
    pass
```

## Code of Conduct

Be respectful, helpful, and inclusive. This is a community project for everyone to enjoy better multi-room audio!

## Questions?

Open an issue for discussion before major changes. We're happy to help guide contributions!

## AI Disclosure

This project is developed with the assistance of AI coding tools. Contributions from both human and AI-assisted development are welcome, provided they meet quality standards and pass all tests.
