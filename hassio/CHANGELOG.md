# Changelog

## [1.1.0] - Snapcast & HAOS Support

### Added
- Snapcast player provider for synchronized multiroom audio
- Home Assistant OS add-on support with PulseAudio integration
- Environment detection module for automatic Docker/HAOS adaptation
- Host ID auto-generation for Snapcast players
- Latency compensation configuration for Snapcast

### Changed
- Audio backend automatically switches between ALSA (Docker) and PulseAudio (HAOS)
- Updated documentation for all three player backends
- Improved provider architecture with consistent interfaces

### Notes
- Squeezelite and Snapcast use ALSA devices (`hw:X,Y`) in standalone Docker
- All providers use PulseAudio when running as HAOS add-on
- Sendspin continues to use PortAudio device indices

---

## [1.0.0] - Initial Release

### Added
- Multi-room audio player management via web interface
- Squeezelite player support (LMS/SlimProto protocol)
- Sendspin player support (Music Assistant native)
- Snapcast player support (synchronized multiroom)
- PulseAudio integration for HAOS audio system
- Ingress support for seamless HA sidebar integration
- Real-time player status via WebSocket
- Individual volume control per player
- Audio device auto-detection
- Persistent configuration across restarts

### Notes
- This is an experimental add-on
- Requires `full_access` permission for audio device access
- Uses Home Assistant's PulseAudio system (hassio_audio)
