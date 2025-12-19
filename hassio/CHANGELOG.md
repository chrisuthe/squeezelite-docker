# Changelog

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
