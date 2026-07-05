"""Vector storage with a zero-dependency fallback.

MemoryStore   — pure-Python cosine search. Fine to ~50K docs (a full D365
                metadata crawl is ~1-2K docs), zero setup.
PgVectorStore — pgvector-backed when DATABASE_URL is set (asyncpg required).
                Same interface; ivfflat index recommended on t2.micro.
"""
import json
import math
from dataclasses import dataclass


@dataclass
class Hit:
    doc_id: str
    score: float
    payload: dict


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


class MemoryStore:
    def __init__(self):
        self._rows: dict[str, tuple[list[float], dict]] = {}

    async def upsert(self, doc_id: str, vector: list[float], payload: dict) -> None:
        self._rows[doc_id] = (vector, payload)

    async def search(self, vector: list[float], top_k: int = 5) -> list[Hit]:
        scored = [
            Hit(doc_id=doc_id, score=_cosine(vector, vec), payload=payload)
            for doc_id, (vec, payload) in self._rows.items()
        ]
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    async def count(self) -> int:
        return len(self._rows)


class PgVectorStore:
    """pgvector implementation. Requires: CREATE EXTENSION vector;

    Table is created on first use:
      atlas_documents(id text pk, embedding vector(dim), payload jsonb)
    """

    def __init__(self, database_url: str, dim: int):
        self._url = database_url
        self._dim = dim
        self._pool = None

    async def _get_pool(self):
        if self._pool is None:
            import asyncpg  # optional dependency, imported lazily

            self._pool = await asyncpg.create_pool(self._url, min_size=1, max_size=4)
            async with self._pool.acquire() as conn:
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                await conn.execute(
                    f"""CREATE TABLE IF NOT EXISTS atlas_documents (
                        id text PRIMARY KEY,
                        embedding vector({self._dim}),
                        payload jsonb
                    )"""
                )
        return self._pool

    @staticmethod
    def _vec_literal(vector: list[float]) -> str:
        return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"

    async def upsert(self, doc_id: str, vector: list[float], payload: dict) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO atlas_documents (id, embedding, payload)
                   VALUES ($1, $2::vector, $3::jsonb)
                   ON CONFLICT (id) DO UPDATE
                   SET embedding = EXCLUDED.embedding, payload = EXCLUDED.payload""",
                doc_id,
                self._vec_literal(vector),
                json.dumps(payload),
            )

    async def search(self, vector: list[float], top_k: int = 5) -> list[Hit]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, payload, 1 - (embedding <=> $1::vector) AS score
                   FROM atlas_documents
                   ORDER BY embedding <=> $1::vector
                   LIMIT $2""",
                self._vec_literal(vector),
                top_k,
            )
        return [
            Hit(doc_id=r["id"], score=float(r["score"]), payload=json.loads(r["payload"]))
            for r in rows
        ]

    async def count(self) -> int:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT count(*) FROM atlas_documents")


def make_store(database_url: str = "", dim: int = 256):
    return PgVectorStore(database_url, dim) if database_url else MemoryStore()
