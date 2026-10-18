import logging
import os
import threading

logger = logging.getLogger("resume_job_matcher.model")

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


class ModelUnavailableError(RuntimeError):
    pass


class ModelManager:
    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self):
        return self._model is not None

    def set_model(self, model):
        with self._lock:
            self._model = model

    def reset(self):
        with self._lock:
            self._model = None

    def get_model(self):
        model = self._model
        if model is not None:
            return model
        return self._load()

    def _load(self):
        with self._lock:
            if self._model is not None:
                return self._model

            try:
                from sentence_transformers import SentenceTransformer

                model_name = os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL)
                revision = os.environ.get("EMBEDDING_MODEL_REVISION", DEFAULT_REVISION)
                logger.info(
                    "Loading embedding model %s (revision %s)", model_name, revision
                )
                model = SentenceTransformer(model_name, revision=revision)
            except Exception as exc:
                logger.exception("Embedding model failed to load")
                raise ModelUnavailableError(
                    "The matching model is unavailable right now. "
                    "Please try again in a moment."
                ) from exc

            self._model = model
            return model


model_manager = ModelManager()
