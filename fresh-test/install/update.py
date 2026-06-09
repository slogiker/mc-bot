import subprocess
import sys
import os

def run_cmd(cmd, shell=True, check=True):
    print(f"\n=> Running: {cmd}")
    return subprocess.run(cmd, shell=shell, check=check, text=True, capture_output=False)

def check_git():
    print("Fetching latest from git...")
    subprocess.run("git fetch", shell=True, check=False)
    
    try:
        local = subprocess.check_output("git rev-parse @", shell=True).strip()
    except subprocess.CalledProcessError:
        print("Not a git repository or no commits yet.")
        return False

    try:
        remote = subprocess.check_output("git rev-parse @{u}", shell=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        remote = None
    
    if not remote:
        print("No upstream found. Assuming up to date or detached head.")
        return False
    
    if local != remote:
        try:
            base = subprocess.check_output("git merge-base @ @{u}", shell=True).strip()
            if local == base:
                print("Local branch is behind the remote.")
                return True
            elif remote == base:
                print("Local is ahead. No update from remote needed.")
                return False
            else:
                print("Branches have diverged.")
                return True # Probably need an update
        except subprocess.CalledProcessError:
            print("Could not determine merge base.")
            return True
    else:
        print("Repository is up to date.")
        return False

def main():
    print("=== MC-bot Update & Rebuild Script ===")
    needs_update = check_git()
    
    if needs_update:
        print("\nNew updates found on GitHub! Pulling latest changes...")
        try:
            run_cmd("git pull")
        except subprocess.CalledProcessError:
            print("Failed to pull changes. Please resolve any conflicts and try again.")
            sys.exit(1)
        
        print("\nRebuilding Docker image from scratch (ignoring cache)...")
        try:
            run_cmd("docker compose down")
            run_cmd("docker compose build --no-cache")
            run_cmd("docker compose up -d")
            print("\nUpdate and rebuild complete! The bot should be starting now.")
        except subprocess.CalledProcessError as e:
            print(f"Docker command failed: {e}")
            sys.exit(1)
    else:
        print("\nNo updates found on GitHub. Your bot is already on the latest version.")
        ans = input("Do you want to force a full rebuild anyway? (y/N): ")
        if ans.lower().startswith('y'):
            print("\nRebuilding Docker image from scratch (ignoring cache)...")
            try:
                run_cmd("docker compose down")
                run_cmd("docker compose build --no-cache")
                run_cmd("docker compose up -d")
                print("\nRebuild complete!")
            except subprocess.CalledProcessError as e:
                print(f"Docker command failed: {e}")
                sys.exit(1)
        else:
            print("Skipping rebuild.")

if __name__ == "__main__":
    main()
