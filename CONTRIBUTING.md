# Contributing to Squeezelite Multi-Room Docker

Thank you for your interest in contributing to this project! 🎵

## 🚀 Quick Start for Contributors

1. **Fork the repository** on GitHub
2. **Clone your fork**: `git clone https://github.com/yourusername/squeezelite-docker.git`
3. **Create a feature branch**: `git checkout -b feature/amazing-feature`
4. **Make your changes** and test thoroughly
5. **Commit your changes**: `git commit -m 'Add amazing feature'`
6. **Push to your branch**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

## 🔧 Development Setup

```bash
# Start development environment
./manage.sh dev              # Linux
.\manage.ps1 dev             # Windows

# This enables:
# - Live code reloading
# - Debug mode
# - Development logging
```

## 🧪 Testing

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

## 📝 What We're Looking For

- **🐛 Bug fixes** - Help make it more stable
- **✨ New features** - Audio device support, UI improvements
- **📚 Documentation** - Better setup guides, troubleshooting
- **🖥️ Platform support** - macOS, different Linux distros
- **🔧 Docker improvements** - Better builds, smaller images
- **🎨 UI/UX enhancements** - Better web interface design

## 📋 Coding Guidelines

- **Python**: Follow PEP 8
- **JavaScript**: Use modern ES6+ features
- **Docker**: Multi-stage builds when possible
- **Documentation**: Update README.md for new features
- **Comments**: Explain complex audio/Docker logic

## 🤝 Code of Conduct

Be respectful, helpful, and inclusive. This is a community project for everyone to enjoy better multi-room audio! 

## 💡 Questions?

Open an issue for discussion before major changes. We're happy to help guide contributions!
