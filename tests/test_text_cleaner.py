from app.utils.text_cleaner import clean_text


def test_clean_text_normalizes_input():
    text = "Python,\nFastAPI!!   SQL\tDocker"
    cleaned = clean_text(text)

    assert cleaned == "python fastapi sql docker"
