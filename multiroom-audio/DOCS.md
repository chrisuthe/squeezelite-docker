# Multi-Room Audio Controller

Manage multiple audio players from one interface. Create whole-home audio with
USB DACs connected to your Home Assistant server.

## Overview

This add-on enables you to run multiple audio players (Squeezelite, Sendspin,
Snapcast) on your Home Assistant server, each outputting to different audio
devices. Perfect for creating synchronized multi-room audio zones.

## Supported Player Types

| Player | Protocol | Server | Use Case |
|--------|----------|--------|----------|
| **Squeezelite** | SlimProto | LMS / Music Assistant | Traditional LMS setups |
| **Sendspin** | Native | Music Assistant | Native MA integration |
| **Snapcast** | Snapcast | Snapcast Server | Synchronized multiroom |

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "Multi-Room Audio Controller" add-on
3. Configure the add-on options (see below)
4. Start the add-on
5. Access the web interface via the sidebar or ingress

## Configuration

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `log_level` | string | `info` | Logging verbosity (debug, info, warning, error) |
| `default_server_ip` | string | `""` | Default server IP for new players |

### Example Configuration

```yaml
log_level: info
default_server_ip: "192.168.1.100"
```

## Audio Device Setup

### Accessing USB DACs

USB audio devices connected to your Home Assistant server are automatically
detected via PulseAudio. The add-on uses Home Assistant's audio system
(`hassio_audio`) for audio output.

### Device Selection

When creating a player:

1. Open the add-on web interface
2. Click "Add Player"
3. Select your audio device from the dropdown
4. Device names appear as PulseAudio sink names

### Troubleshooting Audio

If devices aren't appearing:

1. Check that USB devices are properly connected
2. Verify devices appear in HA's audio settings
3. Restart the add-on to refresh device detection
4. Check add-on logs for audio errors

## Usage

### Creating Players

1. Access the web interface (via HA sidebar or ingress)
2. Click "Add Player"
3. Configure:
   - **Name**: Descriptive name (e.g., "Kitchen Speakers")
   - **Type**: Squeezelite, Sendspin, or Snapcast
   - **Device**: Select audio output device
   - **Server IP**: For Squeezelite/Snapcast (optional)
4. Click "Create"

### Managing Players

- **Start/Stop**: Toggle player state
- **Volume**: Adjust via slider
- **Edit**: Modify player settings
- **Delete**: Remove player

### Integration with Music Assistant

Sendspin players automatically appear in Music Assistant as available targets.
Squeezelite players appear if using MA's Slimproto integration.

## Network Requirements

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 8080 | TCP | Inbound | Web interface |
| 3483 | TCP/UDP | Outbound | Squeezelite → LMS |
| 1704 | TCP | Outbound | Snapcast client |
| 1705 | TCP | Outbound | Snapcast control |

## Known Limitations

1. **PulseAudio Only**: HAOS uses PulseAudio; direct ALSA access isn't available
2. **Device Names**: Device names differ from standalone Docker (PA vs ALSA)
3. **Permissions**: Requires `full_access` for proper audio device access

## Support

- [GitHub Issues](https://github.com/chrisuthe/squeezelite-docker/issues)
- [Documentation](https://github.com/chrisuthe/squeezelite-docker)

## About

This add-on was created using AI-assisted development (Claude by Anthropic).
See the project README for more details.
