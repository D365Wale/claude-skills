import math

import pytest

from app.ai.embedder import LocalHashEmbedder


@pytest.mark.asyncio
async def test_deterministic_and_normalized():
    emb = LocalHashEmbedder()
    v1, v2 = await emb.embed(["LedgerJournalHeader", "LedgerJournalHeader"])
    assert v1 == v2
    assert math.isclose(sum(x * x for x in v1), 1.0, rel_tol=1e-6)


@pytest.mark.asyncio
async def test_related_terms_score_higher_than_unrelated():
    emb = LocalHashEmbedder()
    vecs = await emb.embed(["journal entries posting", "LedgerJournalHeader", "CustomerV3"])

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cos(vecs[0], vecs[1]) > cos(vecs[0], vecs[2])
