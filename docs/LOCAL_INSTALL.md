# Installation Scripts - Quick Reference

## Two Versions Available

### 1. `install-dry-run.sh` - Preview Mode
**Purpose**: See what will happen without making changes

**Use when:**
- First time exploring the installation process
- Testing different configurations
- Verifying system compatibility
- Learning what the installer does

**What it does:**
- ✅ Creates `.env` file (real)
- ❌ Does NOT create venv
- ❌ Does NOT install dependencies
- ❌ Does NOT update config.json
- ❌ Does NOT create server directory
- ✅ Shows exactly what would happen

**Run it:**
```bash
./install-dry-run.sh
```

---

### 2. `install.sh` - Production Installation  
**Purpose**: Perform complete bot installation

**Use when:**
- Ready to install for real
- Setting up a new bot instance
- Fresh installation needed

**What it does:**
- ✅ Creates venv
- ✅ Installs all dependencies
- ✅ Creates `.env` file (chmod 600)
- ✅ Updates config.json
- ✅ Creates server directory
- ✅ Verifies Java installation

**Run it:**
```bash
./install.sh
```

---

## Quick Start Guide

**Step 1**: Preview what will happen
```bash
./install-dry-run.sh
```

**Step 2**: If everything looks good, run real installation
```bash
./install.sh
```

**Step 3**: Activate venv and start bot
```bash
source venv/bin/activate
python bot.py --test
```

**Step 4**: In Discord, run `/setup` to configure channels

---

## Both Scripts Collect

- Server IP (default: 127.0.0.1)
- Discord Bot Token (required)
- RCON Password (auto-generated if empty)
- Minecraft Server Directory (default: ./mc-server)

---

## Files Created

| File | Dry-Run | Production |
|------|---------|------------|
| `.env` | ✅ | ✅ |
| `venv/` | ❌ | ✅ |
| `config.json` (updated) | ❌ | ✅ |
| `mc-server/` | ❌ | ✅ |

---

## Next Steps After Installation

1. **Start the bot**: `python bot.py` or `python bot.py --test`
2. **Configure Discord**: Run `/setup` command
3. **Install MC Server**: Follow Discord prompts
4. **Configure RCON**: Add to `server.properties`:
   ```properties
   enable-rcon=true
   rcon.port=25575
   rcon.password=<your-generated-password>
   ```
