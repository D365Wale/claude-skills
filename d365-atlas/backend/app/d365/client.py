"""D365 F&O HTTP client: metadata download + custom service invocation.

Endpoints (verified against MS Learn docs):
  GET  {base}/data/$metadata                       — full EDMX
  GET  {base}/Metadata/DataEntities                — JSON entity list
  POST {base}/api/services/{group}/{service}/{op}  — custom service call
"""
import httpx

from app.d365.auth import TokenProvider


class D365Client:
    def __init__(self, base_url: str, token_provider: TokenProvider):
        self._base = base_url.rstrip("/")
        self._tokens = token_provider

    async def _headers(self) -> dict:
        return {"Authorization": f"Bearer {await self._tokens.get_token()}"}

    async def fetch_metadata_xml(self) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(
                f"{self._base}/data/$metadata", headers=await self._headers()
            )
            resp.raise_for_status()
            return resp.text

    async def fetch_data_entities(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                f"{self._base}/Metadata/DataEntities",
                headers={**await self._headers(), "Accept": "application/json"},
            )
            resp.raise_for_status()
            return resp.json().get("value", [])

    async def call_service(
        self, group: str, service: str, operation: str, payload: dict
    ) -> dict:
        url = f"{self._base}/api/services/{group}/{service}/{operation}"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=await self._headers())
            resp.raise_for_status()
            return resp.json()
