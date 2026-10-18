from app.services.contacts import find_phones, looks_like_phone


def test_standard_phone_formats_are_detected():
    assert looks_like_phone("+1 555 123 4567")
    assert looks_like_phone("(555) 123-4567")
    assert looks_like_phone("555.123.4567")
    assert looks_like_phone("555-123-4567")
    assert looks_like_phone("+4915123456789")


def test_salary_and_id_numbers_are_not_phones():
    assert not looks_like_phone("Salary range 120000 140000 per year")
    assert not looks_like_phone("Badge ID 1234567890")
    assert not looks_like_phone("Reference #2021001234")
    assert not looks_like_phone("Employee number 9988776655")
    assert not looks_like_phone("Account 1234 5678 9012 3456")
    assert not looks_like_phone("Zip code 94105")


def test_bare_digits_need_a_phone_cue():
    assert not looks_like_phone("Call center volume reached 5551234567")
    assert looks_like_phone("Phone: 5551234567")
    assert looks_like_phone("Mobile 5551234567")


def test_date_ranges_are_not_phones():
    assert not looks_like_phone("2021 - 2022")
    assert not looks_like_phone("May 2021 - Present")
    assert not looks_like_phone("Jan 2020 to Dec 2023")


def test_find_phones_returns_matches():
    phones = find_phones("Reach me at +1 555 123 4567 or (555) 987-6543.")

    assert len(phones) == 2
