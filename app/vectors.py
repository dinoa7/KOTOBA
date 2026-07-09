"""In-memory vector store backed by a .npz file on disk.

Brute-force cosine similarity in numpy. At personal-deck scale (hundreds to
low thousands of cards) this is instant; a vector database would be
resume-driven overengineering at this size.
"""

import numpy as np

from app.config import VECTORS_PATH


class VectorStore:
    def __init__(self) -> None:
        self.ids: np.ndarray = np.array([], dtype=np.int64)
        self.matrix: np.ndarray = np.zeros((0, 0), dtype=np.float32)
        self._load()

    def _load(self) -> None:
        if VECTORS_PATH.exists():
            data = np.load(VECTORS_PATH)
            self.ids = data["ids"]
            self.matrix = data["matrix"]

    def save(self) -> None:
        np.savez(VECTORS_PATH, ids=self.ids, matrix=self.matrix)

    def upsert(self, card_id: int, vector: list[float]) -> None:
        vec = np.array(vector, dtype=np.float32)
        existing = np.where(self.ids == card_id)[0]
        if len(existing):
            self.matrix[existing[0]] = vec
        else:
            if self.matrix.size == 0:
                self.matrix = vec.reshape(1, -1)
            else:
                self.matrix = np.vstack([self.matrix, vec])
            self.ids = np.append(self.ids, card_id)

    def top_k(self, query_vector: list[float], k: int) -> list[tuple[int, float]]:
        """Returns [(card_id, cosine_similarity), ...] sorted descending."""
        if len(self.ids) == 0:
            return []
        q = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        mat_norms = np.linalg.norm(self.matrix, axis=1)
        mat_norms[mat_norms == 0] = 1e-9
        sims = (self.matrix @ q) / (mat_norms * q_norm)
        k = min(k, len(sims))
        top_idx = np.argpartition(-sims, k - 1)[:k]
        top_idx = top_idx[np.argsort(-sims[top_idx])]
        return [(int(self.ids[i]), float(sims[i])) for i in top_idx]

    def all_pairs_top(self, n: int) -> list[tuple[int, int, float]]:
        """Returns the top-n most-similar (id_a, id_b, similarity) pairs, a != b."""
        if len(self.ids) < 2:
            return []
        norms = np.linalg.norm(self.matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1e-9
        normed = self.matrix / norms
        sim_matrix = normed @ normed.T
        pairs = []
        m = len(self.ids)
        for i in range(m):
            for j in range(i + 1, m):
                pairs.append((int(self.ids[i]), int(self.ids[j]), float(sim_matrix[i, j])))
        pairs.sort(key=lambda p: -p[2])
        return pairs[:n]


_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
