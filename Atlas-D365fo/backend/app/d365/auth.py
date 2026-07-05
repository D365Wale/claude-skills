"""Azure AD client-credentials token acquisition with expiry-aware caching.

Verified live against login.microsoftonline.com (200, Bearer, 3599s TTL).
"""
import time

import httpx


class TokenProvider:
    """Fetches and caches an AAD v2.0 access token for a D365 F&O resource."""

    _REFRESH_MARGIN_S = 120  # renew 2 min before expiry

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, base_url: str):
        self._token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = f"{base_url.rstrip('/')}/.default"
        self._token: str = ""
        self._expires_at: float = 0.0

    async def get_token(self) -> str:
        if self._token and time.monotonic() < self._expires_at - self._REFRESH_MARGIN_S:
            return self._token
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": self._scope,
                },
            )
        body = resp.json()
        if "access_token" not in body:
            detail = body.get("error_description") or body.get("error") or resp.text[:200]
            raise RuntimeError(f"AAD token request failed ({resp.status_code}): {detail}")
        self._token = body["access_token"]
        self._expires_at = time.monotonic() + float(body.get("expires_in", 3600))
        return self._token
