"""
Tests for src/version_fetcher.py — VersionFetcher
Live API integration tests (run inside Docker with network access).
"""
import pytest
from src.version_fetcher import VersionFetcher


@pytest.fixture
def fetcher():
    """Fresh VersionFetcher with empty cache."""
    return VersionFetcher()


class TestVersionFetcherLive:
    """Live API tests — these hit real endpoints."""

    @pytest.mark.asyncio
    async def test_paper_versions(self, fetcher):
        """PaperMC API returns a non-empty version list."""
        versions = await fetcher.get_versions("paper", limit=5)
        assert len(versions) > 0
        # Recent versions should start with 1.
        assert versions[0].startswith("1.")

    @pytest.mark.asyncio
    async def test_vanilla_versions(self, fetcher):
        """Mojang API returns vanilla release versions."""
        versions = await fetcher.get_versions("vanilla", limit=5)
        assert len(versions) > 0
        assert versions[0].startswith("1.")

    @pytest.mark.asyncio
    async def test_fabric_versions(self, fetcher):
        """Fabric versions are fetched (uses Mojang under the hood)."""
        versions = await fetcher.get_versions("fabric", limit=5)
        assert len(versions) > 0

    @pytest.mark.asyncio
    async def test_latest_version(self, fetcher):
        """get_latest_version returns a single version string."""
        version = await fetcher.get_latest_version("paper")
        assert isinstance(version, str)
        assert "." in version

    @pytest.mark.asyncio
    async def test_cache_works(self, fetcher):
        """Second call returns cached data without hitting API again."""
        v1 = await fetcher.get_versions("paper", limit=3)
        v2 = await fetcher.get_versions("paper", limit=3)
        assert v1 == v2
        # Verify cache entry exists
        assert "paper" in fetcher._cache

    @pytest.mark.asyncio
    async def test_unknown_platform_returns_empty(self, fetcher):
        """Unknown platform returns empty list."""
        versions = await fetcher.get_versions("unknown_platform", limit=5)
        assert versions == []

    @pytest.mark.asyncio
    async def test_limit_respected(self, fetcher):
        """Requested limit is respected in returned list."""
        versions = await fetcher.get_versions("paper", limit=2)
        assert len(versions) <= 2

    @pytest.mark.asyncio
    async def test_get_all_versions(self, fetcher):
        """get_all_versions returns more versions than limited call."""
        limited = await fetcher.get_versions("vanilla", limit=3)
        all_vers = await fetcher.get_all_versions("vanilla")
        assert len(all_vers) >= len(limited)


class TestVersionFetcherFallback:
    """Tests for fallback behavior."""

    def test_fallback_paper(self):
        fetcher = VersionFetcher()
        result = fetcher._get_fallback_versions("paper", 3)
        assert len(result) == 3
        assert all(isinstance(v, str) for v in result)

    def test_fallback_unknown(self):
        fetcher = VersionFetcher()
        result = fetcher._get_fallback_versions("forge", 5)
        # Forge isn't in fallback map, should return default
        assert isinstance(result, list)

    def test_fallback_no_limit(self):
        fetcher = VersionFetcher()
        result = fetcher._get_fallback_versions("paper", None)
        assert len(result) > 3  # Should return all fallback versions
