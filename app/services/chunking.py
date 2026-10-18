import re

import numpy as np

from app.errors import AppError

DEFAULT_MAX_TOKENS = 256
MAX_INPUT_CHUNKS = 400
MIRROR_SIMILARITY = 0.95
PARAPHRASE_SIMILARITY = 0.88
MIRROR_MIN_JD_COVERAGE = 0.5
MIRROR_MIN_VERBATIM_UNITS = 2
MIRROR_MIN_PARAPHRASE_UNITS = 3
MIRROR_MIN_RESUME_SHARE = 0.5
MIN_MIRROR_UNIT_WORDS = 4
PHRASE_MIN_WORDS = 4
PHRASE_MAX_WORDS = 6
PHRASE_MIN_UNITS = 3

UNIT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
BULLET_TRIM_RE = re.compile(r"^[\s•\-\*\u2022\u25cf\u25cb\u25aa\u25e6]+")
PHRASE_STRIP_RE = re.compile(r"[^a-z0-9+#]+")


def count_tokens(model, text):
    tokenizer = getattr(model, "tokenizer", None)
    if tokenizer is not None:
        try:
            return len(tokenizer.encode(text, add_special_tokens=False))
        except Exception:
            pass
    return max(1, len(text) // 4)


def max_tokens_for(model):
    value = getattr(model, "max_seq_length", None)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_MAX_TOKENS
    if value <= 0:
        return DEFAULT_MAX_TOKENS
    return value


def _sentence_units(text):
    units = []
    for raw_line in text.splitlines():
        line = BULLET_TRIM_RE.sub("", raw_line.strip())
        if not line:
            continue
        for part in UNIT_SPLIT_RE.split(line):
            part = part.strip()
            if part:
                units.append(part)
    return units


def _split_oversized(unit, token_counter, max_tokens):
    pieces = []
    current = []
    current_tokens = 0

    for word in unit.split():
        word_tokens = token_counter(f"{word} ")
        if current and current_tokens + word_tokens > max_tokens:
            pieces.append(" ".join(current))
            current = []
            current_tokens = 0
        current.append(word)
        current_tokens += word_tokens

    if current:
        pieces.append(" ".join(current))
    return pieces


def chunk_text(model, text, max_tokens=None):
    max_tokens = max_tokens or max_tokens_for(model)
    chunks = []
    current = []
    current_tokens = 0

    for unit in _sentence_units(text):
        if count_tokens(model, unit) <= max_tokens:
            pieces = [unit]
        else:
            pieces = _split_oversized(
                unit, lambda t: count_tokens(model, t), max_tokens
            )
            if not pieces:
                continue

        for piece in pieces:
            piece_tokens = count_tokens(model, piece)
            if current and current_tokens + piece_tokens > max_tokens:
                chunks.append(" ".join(current))
                current = []
                current_tokens = 0
            current.append(piece)
            current_tokens += piece_tokens

    if current:
        chunks.append(" ".join(current))

    stripped = text.strip()
    if not chunks and stripped:
        return [stripped]

    if len(chunks) > MAX_INPUT_CHUNKS:
        raise AppError(
            422,
            "invalid_input",
            "This text is too large to analyze. Trim it to the most relevant "
            "sections and try again.",
        )
    return chunks


def embed_chunks(model, chunks):
    if not chunks:
        return None
    embeddings = model.encode(chunks, normalize_embeddings=True)
    embeddings = np.asarray(embeddings, dtype=np.float32)
    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)
    return embeddings


def pooled_vector(embeddings):
    if embeddings is None or len(embeddings) == 0:
        return None
    pooled = embeddings.mean(axis=0)
    norm = float(np.linalg.norm(pooled))
    if norm > 0:
        pooled = pooled / norm
    return pooled


def _meaningful_units(text, min_words=MIN_MIRROR_UNIT_WORDS):
    return [unit for unit in _sentence_units(text) if len(unit.split()) >= min_words][
        :MAX_INPUT_CHUNKS
    ]


def _dedupe_units(units):
    seen = set()
    unique = []
    for unit in units:
        key = unit.lower()
        if key not in seen:
            seen.add(key)
            unique.append(unit)
    return unique


def _merged_units(units):
    return [f"{first} {second}" for first, second in zip(units, units[1:])]


def _normalized_words(text):
    return PHRASE_STRIP_RE.sub(" ", (text or "").lower()).split()


def _phrases(unit):
    words = _normalized_words(unit)
    for size in range(PHRASE_MIN_WORDS, PHRASE_MAX_WORDS + 1):
        for start in range(max(0, len(words) - size + 1)):
            yield " ".join(words[start : start + size])


def _echoed_units(resume_units, jd_text):
    jd_words = _normalized_words(jd_text)
    jd_phrases = set()
    for size in range(PHRASE_MIN_WORDS, PHRASE_MAX_WORDS + 1):
        for start in range(max(0, len(jd_words) - size + 1)):
            jd_phrases.add(" ".join(jd_words[start : start + size]))

    if not jd_phrases:
        return 0

    echoed = 0
    for unit in resume_units:
        if any(phrase in jd_phrases for phrase in _phrases(unit)):
            echoed += 1
    return echoed


def _covered_flags(best_candidates, threshold, unit_count):
    flags = [False] * unit_count
    for index, value in enumerate(best_candidates):
        if value < threshold:
            continue
        if index < unit_count:
            flags[index] = True
        else:
            position = index - unit_count
            flags[position] = True
            flags[position + 1] = True
    return flags


def mirror_analysis(model, resume_text, jd_text, max_tokens=None):
    resume_units = _meaningful_units(resume_text)
    jd_units = _dedupe_units(_meaningful_units(jd_text))

    report = {
        "resume_units": len(resume_units),
        "jd_units": len(jd_units),
        "verbatim_units": 0,
        "verbatim_ratio": 0.0,
        "copied_units": 0,
        "copied_ratio": 0.0,
        "resume_match_ratio": 0.0,
        "echoed_units": 0,
        "mirrored": False,
        "paraphrased": False,
    }

    report["echoed_units"] = _echoed_units(resume_units, jd_text)

    if len(resume_units) < MIRROR_MIN_VERBATIM_UNITS or not jd_units:
        report["paraphrased"] = _phrase_copy(report, len(resume_units))
        return report

    candidates = resume_units + _merged_units(resume_units)
    resume_embeddings = embed_chunks(model, candidates)
    jd_embeddings = embed_chunks(model, jd_units)
    if resume_embeddings is None or jd_embeddings is None:
        return report

    similarities = jd_embeddings @ resume_embeddings.T
    best_jd = similarities.max(axis=1)
    best_candidates = similarities.max(axis=0)

    verbatim_flags = _covered_flags(
        best_candidates, MIRROR_SIMILARITY, len(resume_units)
    )
    matched_flags = _covered_flags(
        best_candidates, PARAPHRASE_SIMILARITY, len(resume_units)
    )

    verbatim_jd = int((best_jd >= MIRROR_SIMILARITY).sum())
    copied_jd = int((best_jd >= PARAPHRASE_SIMILARITY).sum())
    verbatim_resume = sum(verbatim_flags)
    matched_resume = sum(matched_flags)

    report["verbatim_units"] = verbatim_jd
    report["verbatim_ratio"] = verbatim_jd / len(jd_units)
    report["copied_units"] = copied_jd
    report["copied_ratio"] = copied_jd / len(jd_units)
    report["resume_match_ratio"] = matched_resume / len(resume_units)

    report["mirrored"] = (
        report["verbatim_ratio"] > MIRROR_MIN_JD_COVERAGE
        and verbatim_resume >= MIRROR_MIN_VERBATIM_UNITS
    )
    unit_copy = (
        copied_jd >= MIRROR_MIN_PARAPHRASE_UNITS
        and report["copied_ratio"] >= MIRROR_MIN_JD_COVERAGE
        and report["resume_match_ratio"] >= MIRROR_MIN_RESUME_SHARE
    )
    report["paraphrased"] = not report["mirrored"] and (
        unit_copy or _phrase_copy(report, len(resume_units))
    )
    return report


def _phrase_copy(report, resume_unit_count):
    if not resume_unit_count:
        return False
    return (
        report["echoed_units"] >= PHRASE_MIN_UNITS
        and report["echoed_units"] / resume_unit_count >= MIRROR_MIN_RESUME_SHARE
    )


def mean_pooled_similarity(model, text_a, text_b, max_tokens=None):
    chunks_a = chunk_text(model, text_a, max_tokens)
    chunks_b = chunk_text(model, text_b, max_tokens)

    vector_a = pooled_vector(embed_chunks(model, chunks_a))
    vector_b = pooled_vector(embed_chunks(model, chunks_b))

    if vector_a is None or vector_b is None:
        return 0.0, len(chunks_a), len(chunks_b)

    similarity = float(np.dot(vector_a, vector_b))
    similarity = max(0.0, min(1.0, similarity))
    return similarity, len(chunks_a), len(chunks_b)
