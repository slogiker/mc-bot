# i18n Implementation Plan (Multi-Language Support)

## Approach
To support multiple languages across the bot, we will introduce a localization system using JSON locale files. The bot will load these files on startup and use a translation function to resolve strings based on a globally configured language preference.

## Available Languages (Priority Order)
1. English (`en`) - Default fallback
2. German (`de`)
3. Spanish (`es`)
4. Chinese (`zh`)
5. Russian (`ru`)
*(Additional widely spoken languages such as French, Portuguese, Arabic, Hindi, and Japanese will be added as community translations become available).*

## Implementation Details

### 1. File Structure
Create a new `locales/` directory at the project root containing language files:
```
locales/
├── en.json
├── de.json
├── es.json
├── zh.json
└── ru.json
```

### 2. Translation Manager (`src/i18n.py`)
Create a singleton `Translator` class that:
- Loads all `.json` files from the `locales/` directory into memory during initialization.
- Exposes a `get(key, **kwargs)` method to fetch strings.
- Supports dot-notation for nested keys (e.g., `commands.status.online`).
- Falls back to `en` if a key is missing in the chosen language.
- Supports variable interpolation (e.g., `"Welcome {player}!"`).

### 3. Configuration
Add a `language` property to `data/user_config.json` (defaulting to `"en"`). Add a language selection dropdown to the `/settings` Discord UI to allow server owners to easily switch languages.

### 4. Code Refactoring (The heavy lift)
Systematically go through all `cogs/` and `src/views/` files to replace hardcoded strings with `i18n.get()` calls.
*Example:* 
```python
# Before
await interaction.response.send_message("Server is starting...")

# After
await interaction.response.send_message(i18n.get("responses.server_starting"))
```

### 5. Dynamic Loading
Ensure that when a user changes the language in `/settings`, the `Translator` updates its active language immediately without requiring a bot restart.
