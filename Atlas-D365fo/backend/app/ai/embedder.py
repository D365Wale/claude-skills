"""Embeddings with a zero-dependency fallback.

JinaEmbedder  — jina-embeddings-v3 (1024-dim) when JINA_API_KEY is set.
                Uses the task distinction that matters for retrieval quality:
                retrieval.passage at index time, retrieval.query at search time.
LocalHashEmbedder — deterministic character-trigram hashing (256-dim,
                L2-normalized). No network, no keys, no model download.
                Strong enough for entity-name retrieval (D365 names are
                lexically informative: LedgerJournalHeader, CustomersV3).
"""
import hashlib
import math

import httpx


class LocalHashEmbedder:
    dim = 256

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        t = f"  {text.lower()}  "
        for i in range(len(t) - 2):
            gram = t[i : i + 3]
            h = int.from_bytes(hashlib.blake2b(gram.encode(), digest_size=4).digest(), "big")
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    async def embed(self, texts: list[str], task: str = "retrieval.passage") -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class JinaEmbedder:
    dim = 1024

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def embed(self, texts: list[str], task: str = "retrieval.passage") -> list[list[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.jina.ai/v1/embeddings",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": "jina-embeddings-v3",
                    "task": task,
                    "dimensions": self.dim,
                    "input": texts,
                },
            )
            resp.raise_for_status()
            return [item["embedding"] for item in resp.json()["data"]]


def make_embedder(jina_api_key: str = ""):
    return JinaEmbedder(jina_api_key) if jina_api_key else LocalHashEmbedder()
