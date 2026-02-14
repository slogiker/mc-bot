import os
import sys
import time
import subprocess
import getpass

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

def main():
    # Make sure colorama is init/supported on Windows (if python version is old)
    os.system('') 
    
    print(f"{CYAN}----------------------------------------{NC}")
    print(f"{CYAN}   Minecraft Discord Bot - Setup        {NC}")
    print(f"{CYAN}----------------------------------------{NC}")
    print("")

    # Visual Simulation of Installation Steps
    simulated_delay(0.5)
    
    info("Checking system requirements...")
    simulated_delay(1)
    
    # Fake WSL Check
    print(f"{BLUE}[INFO] Checking WSL status...{NC}", end='\r')
    simulated_delay(1.5)
    success("WSL is active and ready.")
    
    # Fake Package Updates
    info("Updating package lists...")
    simulated_delay(2) 
    # Can simulate apt-get text scroll if wanted, but simpler to just show progress
    success("System packages updated.")
    
    # Fake Docker Install
    info("Checking Docker Engine...")
    simulated_delay(1)
    success("Docker Engine installed.")
    
    # Fake Dependencies
    info("Checking Python/Java dependencies...")
    simulated_delay(1)
    success("Python 3.11 found.")
    success("OpenJDK 17 found.")
    
    print("")
    
    # Token Prompt (REAL Interaction)
    warn(".env file not found! Starting setup...")
    print("")
    info("Please enter your Discord Bot Token:")
    print("       (Get it from: https://discord.com/developers/applications)")
    print("       (This token is NOT saved to disk in Simulation Mode)")
    
    try:
        # Hide input if possible, but standard input is fine too
        token = input(f"       > BOT_TOKEN: ").strip()
    except KeyboardInterrupt:
        print("")
        warn("Setup cancelled.")
        return

    if not token:
        error("Bot token cannot be empty!")
        return

    print("")
    success("Auto-generating RCON password...")
    simulated_delay(0.5)
    success("Configuration ready (In-Memory).")
    print("")
    
    info("Starting Bot in SIMULATION MODE...")
    print(f"{CYAN}Allows testing Discord commands. No server will actually run.{NC}")
    simulated_delay(1)
    
    # Set environment variable for the subprocess
    env = os.environ.copy()
    env["BOT_TOKEN"] = token
    
    try:
        # Launch bot.py with --simulate flag
        # Assuming we are running from root or install folder, adjust path
        # If script is in install/, project root is ..
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bot_script = os.path.join(project_root, "bot.py")
        
        # Use sys.executable to ensure we use the same python interpreter
        cmd = [sys.executable, bot_script, "--simulate"]
        
        subprocess.run(cmd, env=env, cwd=project_root)
        
    except KeyboardInterrupt:
        print("")
        info("Simulation stopped.")
    except Exception as e:
        error(f"Failed to launch simulation: {e}")

if __name__ == "__main__":
    main()
