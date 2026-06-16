"""Unit tests for the embedding text builder (pure, no DB/SDK)."""

from types import SimpleNamespace

from data.embed_text import build_embedding_text


def _listing(**overrides):
    base = dict(
        title="Bright 2-room in Prenzlauer Berg",
        rooms=2.0,
        size_m2=58,
        furnished=False,
        kiez="Prenzlauer Berg",
        district="Pankow",
        description="Altbau with high ceilings. Two minutes to the U-Bahn.",
        kaltmiete_eur=1050,
        contact_text="please wire the deposit",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_includes_meaning_bearing_fields():
    text = build_embedding_text(_listing())
    assert "Prenzlauer Berg" in text
    assert "Pankow" in text
    assert "58 m²" in text
    assert "2-room" in text
    assert "Altbau" in text


def test_excludes_price_and_contact():
    text = build_embedding_text(_listing())
    assert "1050" not in text
    assert "wire" not in text


def test_whole_room_count_has_no_decimal():
    assert "2-room" in build_embedding_text(_listing(rooms=2.0))
    assert "1.5-room" in build_embedding_text(_listing(rooms=1.5))


def test_furnished_flag():
    assert "unfurnished" in build_embedding_text(_listing(furnished=False))
    assert "furnished apartment" in build_embedding_text(_listing(furnished=True))
