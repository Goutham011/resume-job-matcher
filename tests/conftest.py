import os

import pytest

from app.middleware import reset_rate_limits
from app.services.model_manager import model_manager
from tests.fake_model import FakeModel


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture(autouse=True)
def use_fake_model():
    if os.environ.get("RUN_MODEL_TESTS") == "1":
        yield None
        return

    model_manager.set_model(FakeModel())
    try:
        yield model_manager
    finally:
        model_manager.reset()
