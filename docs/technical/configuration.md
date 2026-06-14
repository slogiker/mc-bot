# Configuration System

MC-Bot uses a dual-file configuration strategy to separate user-editable settings from persistent system state.

## 📁 Configuration Files

### 1. `data/user_config.json` (User Preferences)
Contains settings intended to be modified by server administrators.
- **Java Settings**: RAM allocation (`min`, `max`).
- **Automation**: Daily backup and restart times.
- **Localization**: Timezone and language preferences.
- **Permissions**: Role-based access control for bot commands.

### 2. `data/bot_config.json` (System State)
Managed primarily by the bot itself. Do not edit manually unless necessary.
- **IDs**: Discord Guild ID, Command Channel ID, Console Channel ID.
- **Metadata**: Server IP, current version, last backup status.
- **Session Data**: Verification states and transient metadata.

## 🔒 Concurrency & Safety (v3.1.1)

### Deadlock-Free Architecture
In v3.1.1, the configuration engine (`src/config.py`) was refactored to prevent re-entrant lock failures. 
- **Internal Methods**: Operations like `_load()` and `_save()` perform raw I/O without locking.
- **Public API**: Methods like `load_bot_config()` and the `update_user_config()` context manager handle the `filelock` acquisition.
- **Result**: You can safely call `load()` from within an `update` context without triggering a deadlock.

### File Locking
All I/O is protected by `filelock` (`data/*.json.lock`). This ensures that even if multiple processes (e.g., the Bot and the LogWatcher) attempt to update the configuration simultaneously, the data remains consistent and corruption-free.

## 🛠️ Modifying Permissions
Permissions are handled via the `permissions` key in `user_config.json`.
- **Key**: Command name (e.g., `backup`).
- **Value**: List of role IDs or names allowed to run the command.
- **Special**: `@everyone` can be used to allow access to all users.
