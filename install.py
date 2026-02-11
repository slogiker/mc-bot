import os
import sys
import platform
import subprocess

def main():
    system = platform.system()
    print(f"[INFO] Detected OS: {system}")

    scripts_dir = os.path.join(os.path.dirname(__file__), 'scripts')
    
    if system == "Windows":
        script_path = os.path.join(scripts_dir, 'install-windows.ps1')
        print(f"[INFO] Launching Windows installer: {script_path}")
        try:
            # Check if PowerShell is available
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path], check=True)
        except FileNotFoundError:
            print("[ERROR] PowerShell not found. Please install PowerShell or run setup manually.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Installation failed with error code {e.returncode}.")
            
    elif system == "Linux" or system == "Darwin": # Darwin is macOS
        script_path = os.path.join(scripts_dir, 'install-linux.sh')
        print(f"[INFO] Launching Linux/macOS installer: {script_path}")
        try:
            # Ensure executable permission
            os.chmod(script_path, 0o755)
            subprocess.run(["bash", script_path], check=True)
        except FileNotFoundError:
            print("[ERROR] Bash not found. Please install Bash or run setup manually.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Installation failed with error code {e.returncode}.")
            
    else:
        print(f"[ERROR] Unsupported Operating System: {system}")
        print("Please check the 'scripts/' folder for manual installation options.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Setup cancelled by user.")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
