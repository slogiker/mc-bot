import aiohttp
from src.logger import logger

async def verify_premium_mc_account(username: str) -> bool:
    """
    Verifies if a Minecraft username is a premium account by checking Mojang's API.
    A valid response with an ID implies it's a real, paid account (or a legacy migrated one).
    Returns True if premium, False if not (or on API error).
    
    API Flow:
    GET https://api.mojang.com/users/profiles/minecraft/<username>
    If 200 OK -> Premium
    If 404 Not Found -> Cracked / Available
    If other block -> Fail-open (return True to avoid blocking during Mojang outages)
    """
    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    # If we got a UUID back, they exist on Mojang servers
                    if "id" in data:
                        return True
                elif response.status == 404:
                    # Account does not exist on Mojang
                    return False
                elif response.status == 204:
                     # 204 No Content also implies not found historically in some Mojang endpoints
                     return False
                else:
                    # Rate limit (429) or Mojang server error (500+).
                    # Fail-open: treat as premium so we don't accidentally enforce cracked checks on real players
                    logger.warning(f"Mojang API returned unexpected status {response.status} for {username}. Failing open.")
                    return True
    except Exception as e:
        logger.warning(f"Failed to reach Mojang API for {username}: {e}. Failing open.")
        return True # Fail open on network errors too

    return False
