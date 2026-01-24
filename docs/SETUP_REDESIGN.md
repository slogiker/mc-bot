# New `/setup` Command - Modal-First Approach

## ✨ What's New?

The `/setup` command has been completely redesigned for a better user experience:

**Before:** Multi-step process with many button clicks  
**After:** Fill one form → Review → One click to confirm → Done!

---

## 🎯 New Flow

### Step 1: User runs `/setup`
```
/setup
```

### Step 2: Modal form appears
A popup form appears with all essential settings:
- **Server Platform** (paper/vanilla/fabric)
- **Minecraft Version** (leave empty for latest)
- **Difficulty** (peaceful/easy/normal/hard)
- **Max Players** (default: 20)
- **Enable Whitelist?** (yes/no)

User fills in all fields (all have smart defaults) and clicks **Submit**.

### Step 3: Beautiful confirmation embed
After submitting, a nicely formatted embed appears showing:

**📋 Basic Settings**
- Platform, version, difficulty, max players, whitelist status

**📦 Installation Process**
- What will happen step-by-step
- Creates channels, downloads server, configures settings

**Four action buttons:**
- ✅ **Confirm & Install** - Start installation
- ⚙️ **Advanced Settings** - Open another modal for RAM, view distance, seed, cracked mode
- 🔄 **Start Over** - Restart from modal form
- ❌ **Cancel** - Abort setup

### Step 4: User clicks "Confirm & Install"
Installation begins automatically:
1. Creates Discord channels (command, log, debug)
2. Creates roles (MC Admin, MC Player)
3. Downloads Minecraft server
4. Accepts EULA
5. Configures server.properties
6. Shows success message

---

## 🎨 Features

### Smart Defaults
- Platform: paper (recommended)
- Version: latest
- Difficulty: normal
- Max Players: 20
- Whitelist: disabled

### Advanced Settings (Optional)
Click "Advanced Settings" button to configure:
- **RAM allocation** (min/max)
- **View distance** (chunks)
- **World seed**
- **Cracked/Offline mode**

### Input Validation
- Platform must be: paper, vanilla, or fabric
- Difficulty must be: peaceful, easy, normal, or hard
- Max players must be 1-100
- RAM must be valid (min ≤ max ≤ 32)
- View distance must be 3-32

### Better Error Messages
If validation fails, user sees clear message:
- "❌ Invalid platform. Use: paper, vanilla, or fabric"
- "❌ Max players must be a number between 1 and 100"

### Restart Capability
User can click "Start Over" to refill the form if they made a mistake.

---

## 📁 Files Changed

### New File
- **`src/setup_views.py`** - All modal and view classes:
  - `SetupConfigModal` - Main setup form
  - `AdvancedSetupModal` - Optional advanced settings
  - `ConfirmationView` - Buttons for confirm/advanced/restart/cancel
  - `SetupManager` - Coordinates the entire flow

### Modified File
- **`cogs/setup.py`** - Simplified to just show modal:
  ```python
  @app_commands.command(name="setup")
  async def setup(self, interaction):
      modal = SetupConfigModal(setup_manager)
      await interaction.response.send_modal(modal)
  ```

---

## 🔄 Comparison

### Old Flow
1. `/setup` → defer
2. Create channels → show success
3. Show platform buttons (Paper/Vanilla/Fabric)
4. User clicks platform
5. Show version buttons (Latest/1.20.4/1.19.4)
6. User clicks version
7. Download server
8. Show difficulty dropdown
9. Show whitelist toggle
10. Show cracked mode toggle
11. User clicks "Continue"
12. If whitelist enabled, ask for usernames
13. Install complete

**Total: 5-7 user interactions**

### New Flow
1. `/setup`
2. Fill modal form (all fields)
3. Click "Submit"
4. Review confirmation
5. Click "Confirm & Install"

**Total: 2 user interactions** (3 if using advanced settings)

---

## 🎯 Benefits

✅ **Faster** - All inputs collected at once  
✅ **Cleaner** - One beautiful confirmation embed  
✅ **User-friendly** - Clear validation messages  
✅ **Flexible** - Advanced settings available but optional  
✅ **Professional** - Polished UI matching Discord's design

---

## 🧪 Testing

To test the new setup:

```bash
# 1. Delete existing server (if any)
rm mc-server/server.jar

# 2. Run the bot
python bot.py

# 3. In Discord, run:
/setup

# 4. Fill the modal with test values:
Platform: paper
Version: (leave empty)
Difficulty: normal
Max Players: 20
Whitelist: no

# 5. Click Submit
# 6. Review the confirmation embed
# 7. Click "Confirm & Install"
# 8. Watch the installation progress
```

---

## 💡 Future Enhancements

Potential improvements:
- Add dropdown for platform/difficulty instead of text input
- Version autocomplete from API
- Preview world seed before confirming
- Save configuration presets
- Import existing server.properties

---

## 🐛 Error Handling

If installation fails at any step:
- Clear error message shown
- Installation stops immediately
- User can run `/setup` again to retry
- Logs contain detailed error info for debugging
