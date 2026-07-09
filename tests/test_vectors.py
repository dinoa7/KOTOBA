from app.vectors import VectorStore


def test_top_k_ranks_by_cosine_similarity():
    store = VectorStore()
    store.upsert(1, [1.0, 0.0])
    store.upsert(2, [0.0, 1.0])
    store.upsert(3, [0.9, 0.1])

    results = store.top_k([1.0, 0.0], k=2)

    assert [card_id for card_id, _ in results] == [1, 3]
    assert results[0][1] == 1.0


def test_top_k_empty_store_returns_empty():
    store = VectorStore()
    assert store.top_k([1.0, 0.0], k=5) == []


def test_upsert_overwrites_existing_id():
    store = VectorStore()
    store.upsert(1, [1.0, 0.0])
    store.upsert(1, [0.0, 1.0])

    assert len(store.ids) == 1
    results = store.top_k([0.0, 1.0], k=1)
    assert results[0][1] == 1.0


def test_all_pairs_top_excludes_self_pairs_and_sorts_descending():
    store = VectorStore()
    store.upsert(1, [1.0, 0.0])
    store.upsert(2, [0.99, 0.01])
    store.upsert(3, [0.0, 1.0])

    pairs = store.all_pairs_top(5)

    ids_in_pairs = [(a, b) for a, b, _ in pairs]
    assert all(a != b for a, b in ids_in_pairs)
    assert pairs[0][:2] == (1, 2)
    similarities = [sim for _, _, sim in pairs]
    assert similarities == sorted(similarities, reverse=True)
