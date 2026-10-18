import re

MONTH_TOKENS = {
    "jan",
    "january",
    "feb",
    "february",
    "mar",
    "march",
    "apr",
    "april",
    "may",
    "jun",
    "june",
    "jul",
    "july",
    "aug",
    "august",
    "sep",
    "sept",
    "september",
    "oct",
    "october",
    "nov",
    "november",
    "dec",
    "december",
}

DATEISH_EXTRA = {"present", "current", "now", "to", "since", "ongoing"}

LINE_TOLERANCE = 4.0
COLUMN_GAP_MIN = 12.0
COLUMN_GAP_RATIO = 3.5


def word_is_dateish(token):
    cleaned = token.lower().strip(".,;:()")
    if not cleaned:
        return True
    if cleaned.isdigit():
        return True
    if cleaned in MONTH_TOKENS or cleaned in DATEISH_EXTRA:
        return True
    return bool(re.fullmatch(r"\d+(?:st|nd|rd|th)", cleaned))


def _cluster_line(words):
    if not words:
        return []

    ordered = sorted(words, key=lambda w: w["x0"])
    gaps = [
        ordered[index + 1]["x0"] - ordered[index]["x1"]
        for index in range(len(ordered) - 1)
    ]
    positive = sorted(gap for gap in gaps if gap > 0)
    if not positive:
        return [ordered]

    median = positive[len(positive) // 2]
    threshold = max(COLUMN_GAP_MIN, median * COLUMN_GAP_RATIO)

    clusters = [[ordered[0]]]
    for word, gap in zip(ordered[1:], gaps):
        if gap > threshold:
            clusters.append([word])
        else:
            clusters[-1].append(word)
    return clusters


def has_columnar_layout(words, width, min_words=35, min_right_words=25):
    if len(words) < min_words:
        return False

    mixed_rows = 0
    right_word_count = 0

    for line in group_words_into_lines(words):
        clusters = _cluster_line(line["words"])
        if len(clusters) < 2:
            continue

        right_cluster = clusters[-1]
        if right_cluster[0]["x0"] < width * 0.25:
            continue

        substantial = [
            word for word in right_cluster if not word_is_dateish(word["text"])
        ]
        if not substantial:
            continue

        mixed_rows += 1
        right_word_count += len(substantial)

    return mixed_rows >= 8 and right_word_count >= min_right_words


def group_words_into_lines(words, tolerance=LINE_TOLERANCE):
    lines = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(word["top"] - lines[-1]["top"]) <= tolerance:
            lines[-1]["words"].append(word)
            lines[-1]["top"] = min(lines[-1]["top"], word["top"])
        else:
            lines.append({"top": word["top"], "words": [word]})

    for line in lines:
        line["words"].sort(key=lambda w: w["x0"])
    return lines


def lines_to_text(lines):
    return "\n".join(
        " ".join(word["text"] for word in line["words"])
        for line in lines
        if line["words"]
    )


def words_to_text(words):
    return lines_to_text(group_words_into_lines(words))


def columnar_text(words, width):
    rows = []
    for line in group_words_into_lines(words):
        clusters = _cluster_line(line["words"])
        row_text = " | ".join(
            " ".join(word["text"] for word in cluster) for cluster in clusters
        )
        if row_text.strip():
            rows.append(row_text)
    return "\n".join(rows)
