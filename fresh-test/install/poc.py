import asyncio
import os
import sys
import time

# -- Setup Environment --
# Add the project root to the Python path to allow imports from 'src'
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.join_guard import JoinGuard
from src.config import config

# --- Mock Objects ---

class MockBot:
    """A mock bot that does nothing but allows attribute access."""
    def __getattribute__(self, name):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return lambda *args, **kwargs: None

class MockMCLinkManager:
    """A mock link manager that simulates a database of linked users."""
    async def get_link_by_mc(self, mc_username: str):
        if mc_username.lower() == "victimplayer":
            # This user is linked, but is NOT a premium account.
            return {"discord_id": 123456789, "is_premium": False}
        return None

async def mock_verify_premium_mc_account(mc_username: str):
    """Mock premium account check. Nobody is premium in this test."""
    return False

async def mock_rcon_cmd(cmd: str):
    """Mock RCON command to avoid real server commands."""
    print(f"[SIMULATED RCON] > {cmd}")
    return "Success", None

# --- Main Simulation ---

async def main():
    """Runs the proof-of-concept simulation for Grace Period Hijacking."""
    print("--- Grace Period Hijacking PoC ---")
    print("This simulation demonstrates how an attacker can impersonate a legitimate (cracked) user.")
    print("-" * 35)

    # 1. Setup the JoinGuard instance with our mocks
    bot = MockBot()
    join_guard = JoinGuard(bot)
    
    # Replace real external dependencies with our mocks
    join_guard.link_manager = MockMCLinkManager()
    join_guard.bot.get_user = lambda id: "MockUser" # Prevent discord lookups
    # Monkey-patch the external verification and RCON calls
    sys.modules['src.join_guard'].verify_premium_mc_account = mock_verify_premium_mc_account
    sys.modules['src.join_guard'].rcon_cmd = mock_rcon_cmd
    # Ensure config is loaded
    pass


    # 2. Simulate the legitimate player "VictimPlayer" quitting the server
    print("\n[STEP 1] Legitimate user 'VictimPlayer' disconnects from the server.")
    join_guard.handle_player_quit("VictimPlayer")
    print(f"  -> 'recently_disconnected' state: {join_guard.recently_disconnected}")
    assert "victimplayer" in join_guard.recently_disconnected

    print("\n... Attacker waits for the victim to leave ...\n")
    await asyncio.sleep(1)

    # 3. Simulate the attacker joining with the victim's username
    print("[STEP 2] Attacker spoofs 'VictimPlayer' username and connects.")
    # The login handler should NOT issue a challenge, but instead grant access.
    await join_guard.handle_player_login("VictimPlayer", "attacker-fake-uuid")
    
    # 4. Verify the outcome
    print("\n[STEP 3] Verifying outcome...")
    if not join_guard.recently_disconnected:
        print("  [SUCCESS] Attacker successfully joined as 'VictimPlayer'.")
        print("  [SUCCESS] The grace period was consumed by the attacker.")
    else:
        print("  [FAIL] Attack was not successful.")
        print(f"  -> 'recently_disconnected' state: {join_guard.recently_disconnected}")

    print("\n--- PoC Finished ---")

if __name__ == "__main__":
    # This setup is necessary because the bot uses asyncio
    # and we want to run our async main function.
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nSimulation stopped by user.")
