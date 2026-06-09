import os
import sys
import time
import subprocess
import getpass
import urllib.request
import urllib.error
import json

# ANSI Codes for matching the real installer's look
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m' # No Color

def info(msg):
    print(f"{BLUE}[INFO] {msg}{NC}")

def success(msg):
    print(f"{GREEN}[SUCCESS] {msg}{NC}")

def warn(msg):
    print(f"{YELLOW}[WARN] {msg}{NC}")

def error(msg):
    print(f"{RED}[ERROR] {msg}{NC}")

def simulated_delay(seconds=1):
    time.sleep(seconds)

def validate_token(token):
    """Validates the Discord token by hitting the Discord API"""
    req = urllib.request.Request(
        "https://discord.com/api/v10/users/@me",
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": "DiscordBot (https://github.com/slogiker/mc-bot, 2.6.0)"
        }
    )
    try:
        urllib.request.urlopen(req)
        return True, "Valid token"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "Invalid token provided. Discord rejected it with 401 Unauthorized."
        return False, f"Discord API returned {e.code}"
    except Exception as e:
        return False, f"Could not verify token: {e}"

def main():
    # Make sure colorama is init/supported on Windows (if python version is old)
    os.system('') 
    
    print(f"{CYAN}---------------------------------------------{NC}")
    print(f"{CYAN}   Minecraft Discord Bot - Setup Simulator   {NC}")
    print(f"{CYAN}---------------------------------------------{NC}")
    print("")

    simulated_delay(0.5)
    
    # 1. Dependency checks (mimicking install.sh)
    print(f"{BLUE}[1/4] Checking dependencies...{NC}")
    simulated_delay(1)
    
    print(f"{BLUE}Checking for Git...{NC}")
    simulated_delay(0.5)
    success("Git is installed.")
    
    print(f"{BLUE}Checking for Docker...{NC}")
    simulated_delay(0.8)
    success("Docker is installed and running.")

    print(f"{BLUE}Checking for utility packages (curl, wget, jq, unzip, tar)...{NC}")
    simulated_delay(1)
    success("All utility packages are installed.")
    
    # 2. Configure Environment
    print("")
    print(f"{BLUE}[2/4] Configuring Environment...{NC}")
    simulated_delay(0.5)
    warn(".env file missing or skipped in simulation mode.")
    
    print("")
    print(f"Enter your {CYAN}Discord Bot Token{NC}:")
    print("(Get it from https://discord.com/developers/applications)")
    print("(This token is NOT saved to disk in Simulation Mode)")
    
    try:
        # Hide input if possible, but standard input is fine too
        token = input(f"> ").strip()
    except KeyboardInterrupt:
        print("")
        warn("Setup cancelled.")
        return

    if not token:
        error("Bot token cannot be empty!")
        return

    print(f"{BLUE}Validating token with Discord API...{NC}")
    is_valid, err_msg = validate_token(token)
    
    if not is_valid:
        error(f"Token validation failed: {err_msg}")
        print(f"{RED}Simulation cancelled because the token is incorrect.{NC}")
        return
        
    success("Token is valid.")

    print("")
    print(f"Do you want to configure {CYAN}Playit.gg{NC} for public access?")
    print("(Requires a specific Secret Key from playit.gg -> Add Agent -> Linux/Docker)")
    try:
        playit = input(f"> [y/N] ")
        if playit.lower().startswith('y'):
            print(f"Enter your {CYAN}Playit Secret Key{NC}:")
            input(f"> ")
            success("Playit configuration noted (simulated).")
    except KeyboardInterrupt:
         pass

    print("")
    success("Auto-generating RCON password...")
    simulated_delay(0.5)
    success("Configuration ready (In-Memory).")
    
    # 3. Create Directories
    print("")
    print(f"{BLUE}[3/4] Creating directories...{NC}")
    simulated_delay(0.5)
    success("Directories ready (simulated).")
    
    # 4. Starting Services
    print("")
    print(f"{BLUE}[4/4] Starting Services...{NC}")
    print(f"{CYAN}Allows testing Discord commands. No server will actually run.{NC}")
    simulated_delay(1)
    
    # Set environment variable for the subprocess
    env = os.environ.copy()
    env["BOT_TOKEN"] = token
    
    try:
        # Launch bot.py with --simulate flag
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bot_script = os.path.join(project_root, "bot.py")
        
        # Use sys.executable to ensure we use the same python interpreter
        cmd = [sys.executable, bot_script, "--simulate"]
        
        print("\nStarting bot process...")
        subprocess.run(cmd, env=env, cwd=project_root)
        
    except KeyboardInterrupt:
        print("")
        info("Simulation stopped.")
    except Exception as e:
        error(f"Failed to launch simulation: {e}")

if __name__ == "__main__":
    main()
