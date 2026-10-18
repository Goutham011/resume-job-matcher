import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

LINK_RE = re.compile(r"(linkedin\.com|https?://|www\.)", re.IGNORECASE)

PHONE_CANDIDATE_RE = re.compile(r"[+(]?\d[\d\s().\-]{6,}\d")

DATE_RANGE_VETO_RE = re.compile(
    r"\b(?:19|20)\d{2}\s*(?:--|-|–|—|to)\s*"
    r"(?:(?:19|20)\d{2}|present|current|now|today|ongoing)\b",
    re.IGNORECASE,
)

PHONE_CONTEXT_VETO_RE = re.compile(
    r"(?i)\b(?:budget|budgets|salary|salaries|compensation|payroll|badge|badges|"
    r"employee|employees|reference|references|ref|refs|req|requisition|invoice|"
    r"invoices|account|accounts|routing|zip|postal|id|ids|ticket|tickets|case|"
    r"claim|claims|loan|mortgage|serial|part|parts|sku|upc|ein|ssn|policy|"
    r"policies|branch|version|revision|hours|units|amount|amounts|total|totals|"
    r"cost|costs|revenue|profit|population|capacity|sq|sqft)\b"
)

PHONE_CUE_RE = re.compile(
    r"(?i)\b(?:phone|tel|telephone|mobile|cell|contact|whatsapp)\b"
)

MIN_PHONE_DIGITS = 10
RELAXED_PHONE_DIGITS = 9
PHONE_CONTEXT_WINDOW = 30


def _valid_phone_candidate(candidate, text, start):
    digit_count = sum(character.isdigit() for character in candidate)
    if digit_count < RELAXED_PHONE_DIGITS:
        return False

    has_intl_marker = candidate.lstrip().startswith("+") or "(" in candidate
    if digit_count < MIN_PHONE_DIGITS and not has_intl_marker:
        return False

    groups = [len(group) for group in re.findall(r"\d+", candidate)]
    context = text[
        max(0, start - PHONE_CONTEXT_WINDOW) : start
        + len(candidate)
        + PHONE_CONTEXT_WINDOW
    ]

    if len(groups) == 1:
        if not has_intl_marker and not PHONE_CUE_RE.search(context):
            return False
    else:
        long_groups = [group for group in groups if group >= 6]
        if len(long_groups) >= 2:
            return False

    return not PHONE_CONTEXT_VETO_RE.search(context)


def find_phones(text):
    if not text:
        return []

    scrubbed = DATE_RANGE_VETO_RE.sub(" ", text)
    phones = []
    for match in PHONE_CANDIDATE_RE.finditer(scrubbed):
        candidate = match.group(0)
        if _valid_phone_candidate(candidate, scrubbed, match.start()):
            phones.append(candidate.strip())
    return phones


def looks_like_phone(text):
    return bool(find_phones(text))
