# Hermes PetLink

Bridge Hermes agent activity to desktop pets. Monitors Hermes' `state.db` for activity and sends events to AgentPet's HTTP API.

## Architecture

```
Hermes (Linux) → state.db → hermes_pet_monitor.py → HTTP POST → relay_server.py (Windows:7890) → AgentPet API (:47628) → Pet reacts
```

## Components

### `hermes_pet_monitor.py` (Linux)
- Polls `~/.hermes/state.db` every 3 seconds
- Detects state transitions: idle → working → waiting → done
- Sends rich events with message, tool, and file context
- Runs as systemd user service

### `relay_server.py` (Windows)
- HTTP server on port 7890
- Forwards events to AgentPet's API on port 47628
- No process spawning — clean HTTP forwarding
- Runs as Windows Scheduled Task

## Setup

### Linux
```bash
cp hermes-pet-monitor.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now hermes-pet-monitor.service
```

### Windows
```powershell
# Relay server starts automatically via Scheduled Task
# Or run manually:
python relay_server.py
```

## AgentPet States

| State | When |
|-------|------|
| `working` | Hermes is processing a request |
| `waiting` | Hermes has finished, awaiting next input |
| `done` | Idle timeout reached (15s default) |

## Requirements

- Python 3.10+
- Hermes agent installed with state.db
- AgentPet desktop app running
- Network access between Linux and Windows (port 7890)

## License

Self
