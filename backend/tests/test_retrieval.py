"""Tests for retrieve(): query embedding + row mapping (fake session/embedder).

Filter *semantics* are covered by test_filters; here we verify retrieve embeds the
raw query text and maps DB rows into RetrievalResult in order. Runs locally (needs
SQLAlchemy); the live pgvector query is exercised at integration time.
"""

from data.models import Listing
from search.criteria import SearchCriteria
from search.retrieval import RetrievalResult, retrieve


class FakeSession:
    def __init__(self, rows):
        self._rows = rows
        self.executed = None

    def execute(self, stmt):
        self.executed = stmt
        return list(self._rows)


def test_embeds_query_and_maps_rows_in_order():
    calls = []

    def fake_embed(text):
        calls.append(text)
        return [0.0] * 768

    l1, l2 = Listing(title="A"), Listing(title="B")
    session = FakeSession([(l1, 0.1), (l2, 0.3)])

    out = retrieve(
        session,
        SearchCriteria(max_warm_rent=1500),
        "quiet flat near Alexanderplatz",
        limit=5,
        embedder=fake_embed,
    )

    assert calls == ["quiet flat near Alexanderplatz"]  # raw query embedded
    assert all(isinstance(r, RetrievalResult) for r in out)
    assert [r.listing for r in out] == [l1, l2]
    assert [r.distance for r in out] == [0.1, 0.3]
