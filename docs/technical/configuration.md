# Configuration System

MC-Bot uses a dual-file configuration strategy to separate user-editable settings from persistent system state. Both files are managed via a thread-safe, deadlock-free engine.

## 📁 Configuration Files

### 1. `data/user_config.json` (User Preferences)
Contains settings intended to be modified by server administrators.
- **Java Settings**: RAM allocation (`min`, `max`). Must match `^\d+[MG]$`.
- **Automation**: Daily backup and restart times (`HH:MM`).
- **Backup Retention**: `backup_keep_days` (1–365).
- **Localization**: Timezone (pytz-compatible) and language.
- **Permissions**: Role-based access control mapping role names to allowed commands.

### 2. `data/bot_config.json` (System State)
Managed primarily by the bot itself. It tracks the "machine state" and persistent runtime data.
- **IDs**: Discord Guild ID, Category, and Channel IDs for commands, logs, debug, etc.
- **Roles**: MC Admin and MC Player role IDs.
- **Metadata**: Public IP (captured from Playit), server version, spawn coordinates.
- **Session Data**: Verification states, active grace windows, and economy balances.

## 🔒 Concurrency, Atomicity & Deadlock Protection

### Atomic Context Managers (v3.1.1)
Config management uses atomic context managers to prevent race conditions during concurrent updates (e.g., when two players trigger economy changes or verify simultaneously):

```python
with config.update_user_config() as data:
    data['some_setting'] = 'new_value'
    # File is locked, data is re-read from disk, then written back.
```

### Deadlock-Free Architecture
A critical fix in v3.1.1 addressed a re-entrant lock failure. 
- **The Bug**: `load()` would attempt to acquire a lock even if it was called from within an `update_*` context that already held the lock.
- **The Solution**: All internal I/O is now split into non-locking methods (`_load`, `_save`). Public methods handle the `FileLock`, ensuring no nested lock attempts occur.

### File Locking
All disk I/O is protected by `filelock` (`data/*.json.lock`). This ensures data consistency across the Bot, the LogWatcher, and any external scripts that might touch the configuration.

## 🛠️ Role-Based Permissions
Permissions are handled via the `permissions` key in `user_config.json`.
- **Resolution**: At startup, `config.resolve_role_permissions(guild)` maps role names to IDs.
- **Hierarchy**: The bot first checks by ID (v3), then falls back to checking the role name directly.
- **Special**: `@everyone` can be used to grant public access to commands like `/status` or `/help`.
