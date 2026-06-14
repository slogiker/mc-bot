# Project Instructions (GEMINI.md)

This file contains foundational mandates, architectural decisions, and technical documentation for the Minecraft Discord Bot project.

## 🔗 Playit.gg API Implementation

Through empirical testing and source code analysis (v1.0.10), we identified critical details for programmatic tunnel creation.

### API Endpoints
- **Legacy Endpoint (Recommended):** `POST https://api.playit.gg/tunnels/create`
  - *Status:* Verified Working.
  - *Payload Type:* Simple/Agent-based.
- **v1 Endpoint:** `POST https://api.playit.gg/v1/tunnels/create`
  - *Status:* Strict validation, requires complex nested schema (ReqTunnelsCreateV1). Use legacy instead unless specific v1 features are needed.

### Working JSON Payload (Legacy)
To create a Minecraft Java tunnel, use the following structure with the legacy endpoint:

```json
{
  "name": "minecraft-java-tunnel",
  "tunnel_type": "minecraft-java",
  "port_type": "both",
  "port_count": 1,
  "origin": {
    "type": "agent",
    "data": {
      "agent_id": "YOUR_AGENT_UUID",
      "local_ip": "127.0.0.1",
      "local_port": 25565
    }
  },
  "enabled": true
}
```

### Authentication
- **Header:** `authorization: Agent-Key <YOUR_SECRET_KEY>`
- **Note:** The `Agent-Key` is required for all agent-specific API calls.

## 🏗️ Architecture Notes

### Multi-Architecture Support
The project supports both `amd64` (standard servers) and `aarch64` (Raspberry Pi/CM4) via architecture auto-detection in the `Dockerfile`.
- Always use `ARCH=$(uname -m)` inside `RUN` commands to select the correct binary.
- Supported Playit binaries: `playit-linux-amd64`, `playit-linux-aarch64`, `playit-linux-armv7`.

### Configuration & Secrets
- **Discord Bot Token:** Stored in `.env` (Standard Docker practice).
- **Playit Secret Key:** Stored in `data/playit_secret.key` (Managed by installer).
- **Persistence:** All runtime data is stored in local volumes (`./mc-server`, `./backups`, `./data`) to ensure safety during container rebuilds.
