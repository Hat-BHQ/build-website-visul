from app.chunking import build_chunks


def test_chunking_deduplicates_and_splits():
    chunks = build_chunks(["1", "1", "2", "3"], size=2)
    assert chunks == [["1", "2"], ["3"]]
