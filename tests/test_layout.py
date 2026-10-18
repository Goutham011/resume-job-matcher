from app.services.layout import (
    columnar_text,
    has_columnar_layout,
)


def _word(text, x0, top, x1=None, bottom=None):
    return {
        "text": text,
        "x0": x0,
        "x1": x1 if x1 is not None else x0 + 30,
        "top": top,
        "bottom": bottom if bottom is not None else top + 10,
    }


def test_right_aligned_dates_do_not_trigger_column_detection():
    words = []
    for row in range(20):
        top = 100 + row * 14
        for index, token in enumerate(
            ["built", "scalable", "backend", "services", "daily"]
        ):
            words.append(_word(token, 50 + index * 40, top))
        words.append(_word("2021", 540, top))

    assert not has_columnar_layout(words, 612)


def test_two_text_columns_trigger_column_detection():
    words = []
    for row in range(14):
        top = 100 + row * 18
        for index, token in enumerate(
            ["built", "scalable", "backend", "systems", "reliably"]
        ):
            words.append(_word(token, 50 + index * 40, top))
        for index, token in enumerate(
            ["python", "fastapi", "docker", "kubernetes", "observability"]
        ):
            words.append(_word(token, 350 + index * 45, top))

    assert has_columnar_layout(words, 612)


def test_two_column_row_clustering_preserves_reading_order():
    words = []
    for row in range(4):
        top = 100 + row * 20
        words.append(_word("left", 50, top))
        words.append(_word(f"l{row}", 100, top))
        words.append(_word("right", 350, top))
        words.append(_word(f"r{row}", 400, top))

    text = columnar_text(words, 612)

    assert text.index("left l0") < text.index("right r0")
    assert text.index("right r0") < text.index("left l1")
    assert text.index("left l3") < text.index("right r3")
    assert "left l0 | right r0" in text
