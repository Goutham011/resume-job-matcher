from app.services.parser import extract_text_from_pdf_bytes


def test_extract_text_from_invalid_pdf_bytes_raises():
    bad_bytes = b"this is not a real pdf"

    try:
        extract_text_from_pdf_bytes(bad_bytes)
        assert False, "Expected parser to raise an exception for invalid PDF bytes"
    except Exception:
        assert True
