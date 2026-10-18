import hashlib
import re

import numpy as np

TOKEN_RE = re.compile(r"[a-z0-9]+")


class FakeModel:
    max_seq_length = 256
    tokenizer = None

    def __init__(self, dim=256):
        self.dim = dim

    def _vector(self, text):
        vector = np.zeros(self.dim, dtype=np.float32)
        tokens = TOKEN_RE.findall(text.lower())
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return vector

    def encode(self, texts, normalize_embeddings=True, **kwargs):
        single = isinstance(texts, str)
        if single:
            texts = [texts]

        matrix = np.stack([self._vector(text) for text in texts])
        if normalize_embeddings:
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            matrix = matrix / norms

        if single:
            return matrix[0]
        return matrix
