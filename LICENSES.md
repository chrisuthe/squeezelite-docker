# Third-Party Licenses

This project includes the following third-party components:

## Audio Players

### Squeezelite

- **License**: GNU General Public License v3.0 or later (GPL-3.0+)
- **Copyright**: 2012-2015 Adrian Smith, 2015-2025 Ralph Irving
- **Source**: https://github.com/ralph-irving/squeezelite
- **Description**: Lightweight headless Squeezebox emulator for Lyrion Media Server

Squeezelite is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

### Snapcast (snapclient)

- **License**: GNU General Public License v3.0 or later (GPL-3.0+)
- **Copyright**: 2014-2025 Johannes Pohl
- **Source**: https://github.com/badaix/snapcast
- **Description**: Synchronous multiroom audio player

Snapcast is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

### Sendspin

- **License**: Apache License 2.0
- **Source**: https://github.com/music-assistant/server (Music Assistant)
- **Specification**: https://github.com/Sendspin/spec
- **Website**: https://www.sendspin-audio.com/
- **Description**: Open source multimedia streaming and synchronizing protocol

Sendspin is licensed under the Apache License, Version 2.0. You may obtain
a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

---

## Python Dependencies

See `requirements.txt` for the full list. Key dependencies include:

| Package | License |
|---------|---------|
| Flask | BSD-3-Clause |
| Flask-SocketIO | MIT |
| PyYAML | MIT |
| Pydantic | MIT |
| sounddevice | MIT |
| NumPy | BSD-3-Clause |

---

## License Compatibility

This Docker image bundles GPL-3.0+ and Apache-2.0 licensed components.
These licenses are compatible when distributed together. The GPL-3.0+
components (Squeezelite, Snapcast) retain their copyleft requirements.

For source code availability:
- Squeezelite: https://github.com/ralph-irving/squeezelite
- Snapcast: https://github.com/badaix/snapcast
- Sendspin: https://github.com/music-assistant/server

---

## Disclaimer

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED. See individual license texts for complete terms and conditions.
