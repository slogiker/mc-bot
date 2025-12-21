# Dry-Run Mode Documentation

## Overview

The bot supports a `--dry-run` flag for testing and previewing changes without making actual modifications. This is useful for development and first-time setup.

## Running the Bot in Dry-Run Mode

```bash
python bot.py --dry-run
```

You'll see:
```
🌵 STARTING IN DRY-RUN MODE (PREVIEW ONLY) 🌵
```

## Commands in Dry-Run Mode

### `/setup` Command

When you run `/setup` in dry-run mode:

**✅ Shows:**
- What channels would be created
- What roles would be created  
- What config.json updates would happen
- What already exists

**❌ Does NOT:**
- Create actual channels
- Create actual roles
- Modify config.json

**Example Output:**

```
🌵 Dry-Run: Discord Server Setup Preview

This is a preview of what would be created. No changes will be made.

📁 Category
➕ Would create category 'Minecraft Server'

💬 Channels
✓ Exists: #command
➕ Would create #log channel
➕ Would create #debug channel

👥 Roles
✓ Exists: @MC Admin
➕ Would create 'MC Player' role

📝 config.json Updates
• command_channel_id: 1234567890
• log_channel_id: <new channel ID>
• debug_channel_id: <new channel ID>

🌵 DRY-RUN MODE: To actually create these, restart bot without --dry-run flag
```

## Combined Modes

Combine with test mode for full simulation:

```bash
python bot.py --test --dry-run
```

- `--test`: Uses mock Minecraft server (no real server commands)
- `--dry-run`: Previews Discord changes without applying them

## When to Use

**Use dry-run when:**
- 🔍 First time setting up to see what will happen
- ✅ Testing commands on a production server
- 🧪 Developing/debugging new features
- 📚 Learning how the bot works

**Use normal mode when:**
- 🚀 Ready to actually set up the bot
- ✏️ Making real changes to Discord structure
- 🎮 Running the bot in production

## Dry-Run Installation Script

For local (non-Docker) installation, there's also a dry-run installation script:

```bash
chmod +x scripts/install-dry-run.sh
./scripts/install-dry-run.sh
```

This simulates the entire installation process:
- Python virtual environment setup
- Java verification
- Credential collection
- Dependency installation

**Features:**
- Color-coded output (blue headers, green success, yellow warnings)
- Shows exactly what would be written to `.env` and `config.json`
- Safe to run - makes no actual changes
- Great for testing before running actual install

## Technical Details

**Code Check:**
```python
from src.config import config

if config.DRY_RUN_MODE:
    # Show preview
    logger.info("🌵 Would perform action X")
else:
    # Make real changes
    perform_action()
```

**Implemented in:**
- `bot.py`: Argument parser
- `src/config.py`: DRY_RUN_MODE flag
- `cogs/setup.py`: Preview logic for /setup command
