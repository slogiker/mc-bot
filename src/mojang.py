import aiohttp
from src.logger import logger

async def verify_premium_mc_account(username: str, session: aiohttp.ClientSession = None) -> bool:
    """
    Verifies if a Minecraft username is a premium account by checking Mojang's API.
    A valid response with an ID implies it's a real, paid account.
    Returns True if premium, False if not (or on API error).
    """
    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    
    # Use provided session or create a temporary one (shared is preferred)
    if session is None:
        async with aiohttp.ClientSession() as temp_session:
            return await _verify_with_session(url, username, temp_session)
    else:
        return await _verify_with_session(url, username, session)

async def _verify_with_session(url: str, username: str, session: aiohttp.ClientSession) -> bool:
    try:
        # Reduced timeout (2s) for faster JoinGuard response
        async with session.get(url, timeout=2) as response:
            if response.status == 200:
                data = await response.json()
                return "id" in data
            elif response.status in (204, 404):
                return False
            else:
                logger.warning(f"Mojang API status {response.status} for {username}. Failing closed.")
                return False
    except Exception as e:
        logger.warning(f"Failed to reach Mojang API for {username}: {e}. Failing closed.")
        return False
