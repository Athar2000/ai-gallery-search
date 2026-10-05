"""
Splits a free-text search query into a structured date filter and whatever
semantic text is left over, per spec sections 6 and 7:

    "Show my photos from August 2025 with cars"
        -> start_date=2025-08-01, end_date=2025-08-31, semantic_query="Show my photos with cars"

    "15 August 2025"
        -> start_date=end_date=2025-08-15, semantic_query=""

    "beach sunset"
        -> no date found, semantic_query="beach sunset"

Per spec: "Do NOT use vector search for simple date filtering" — this
parser exists so the hybrid search service can apply a plain SQL date
range WHERE clause instead of burning a vector query on pure date lookups.

This module is pure Python (regex + calendar math) with zero external
dependencies, so it's fully unit-testable without a database or any AI
backend.
"""
import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

_MONTHS = {
    name.lower(): i
    for i, name in enumerate(
        ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    )
    if name
}
_MONTH_ABBRS = {name[:3].lower(): num for name, num in _MONTHS.items()}
_ALL_MONTH_NAMES = sorted(set(_MONTHS) | set(_MONTH_ABBRS), key=len, reverse=True)
_MONTH_PATTERN = "|".join(re.escape(m) for m in _ALL_MONTH_NAMES)


def _month_num(name: str) -> int:
    name = name.lower()
    return _MONTHS.get(name) or _MONTH_ABBRS[name[:3]]


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _year_bounds(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


@dataclass
class ParsedQuery:
    start_date: date | None
    end_date: date | None
    semantic_query: str
    matched_phrase: str | None  # the exact substring recognized as a date expression, for debugging/UI display


# Ordered most-specific-first: a later pattern must not accidentally consume
# text a more specific earlier pattern should have matched.
_DAY_MONTH_YEAR = re.compile(rf"\b(\d{{1,2}})\s+({_MONTH_PATTERN})\s+(\d{{4}})\b", re.IGNORECASE)
_MONTH_DAY_YEAR = re.compile(rf"\b({_MONTH_PATTERN})\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.IGNORECASE)
_MONTH_YEAR = re.compile(rf"\b({_MONTH_PATTERN})\s+(\d{{4}})\b", re.IGNORECASE)
_YEAR_ONLY = re.compile(r"\b((?:19|20)\d{2})\b")
_RANGE_SEP = re.compile(r"\s+(?:to|through|-|–|—)\s+", re.IGNORECASE)

_RELATIVE_PHRASES = [
    "today",
    "yesterday",
    "this week",
    "this month",
    "last month",
    "this year",
    "last year",
    "last summer",
]

_CONNECTOR_WORDS = {"from", "in", "on", "during", "dated", "of", "with"}

# Generic gallery-app filler words that carry no real search content on
# their own. Without stripping these, "show my photos from August 2025"
# leaves semantic_query="photos" -- which silently turns a pure date query
# into a (falsely) similarity-filtered one and can drop otherwise-matching
# photos. Found by actually running a query like this end-to-end.
_FILLER_WORDS = {
    "show",
    "photo",
    "photos",
    "picture",
    "pictures",
    "pic",
    "pics",
    "image",
    "images",
    "my",
    "me",
    "a",
    "an",
    "the",
    "and",
}
_FILLER_PATTERN = re.compile(r"\b(?:" + "|".join(_FILLER_WORDS) + r")\b", re.IGNORECASE)


def _strip_connectors(text: str) -> str:
    words = text.split()
    while words and words[0].lower() in _CONNECTOR_WORDS:
        words.pop(0)
    while words and words[-1].lower() in _CONNECTOR_WORDS:
        words.pop()
    return " ".join(words).strip()


def _clean_remainder(text: str) -> str:
    """Removes filler words throughout, then edge-connectors, then
    collapses whitespace. Used for whatever text is left after the date
    expression is cut out of the query."""
    no_filler = _FILLER_PATTERN.sub(" ", text)
    no_filler = re.sub(r"\s+", " ", no_filler).strip()
    return _strip_connectors(no_filler)


def strip_filler_and_connectors(text: str) -> str:
    """Public wrapper around _clean_remainder for other modules (ranking.py
    uses this after cutting a matched person/object name out of the query,
    the same way parse_query uses it after cutting out a date phrase)."""
    return _clean_remainder(text)


def _relative_bounds(phrase: str, today: date) -> tuple[date, date]:
    phrase = phrase.lower()
    if phrase == "today":
        return today, today
    if phrase == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    if phrase == "this week":
        start = today - timedelta(days=today.weekday())  # Monday
        return start, start + timedelta(days=6)
    if phrase == "this month":
        return _month_bounds(today.year, today.month)
    if phrase == "last month":
        first_of_this_month = today.replace(day=1)
        last_month_end = first_of_this_month - timedelta(days=1)
        return _month_bounds(last_month_end.year, last_month_end.month)
    if phrase == "this year":
        return _year_bounds(today.year)
    if phrase == "last year":
        return _year_bounds(today.year - 1)
    if phrase == "last summer":
        # "Summer" = June-August (spec doesn't define hemisphere; this is a
        # documented simplification). If this year's summer has already
        # finished, "last summer" means this year's; otherwise last year's.
        this_year_summer_end = date(today.year, 8, 31)
        summer_year = today.year if today > this_year_summer_end else today.year - 1
        return date(summer_year, 6, 1), date(summer_year, 8, 31)
    raise ValueError(f"Unhandled relative phrase: {phrase}")  # pragma: no cover


def _find_single_date_span(text: str) -> tuple[tuple[date, date], tuple[int, int]] | None:
    """Finds the first (and most specific) date expression in `text`.
    Returns ((start, end), (match_start_idx, match_end_idx)) or None."""
    if m := _DAY_MONTH_YEAR.search(text):
        day, month_name, year = int(m.group(1)), m.group(2), int(m.group(3))
        d = date(year, _month_num(month_name), day)
        return (d, d), m.span()

    if m := _MONTH_DAY_YEAR.search(text):
        month_name, day, year = m.group(1), int(m.group(2)), int(m.group(3))
        d = date(year, _month_num(month_name), day)
        return (d, d), m.span()

    if m := _MONTH_YEAR.search(text):
        month_name, year = m.group(1), int(m.group(2))
        return _month_bounds(year, _month_num(month_name)), m.span()

    for phrase in _RELATIVE_PHRASES:
        if m := re.search(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE):
            return _relative_bounds(phrase, date.today()), m.span()

    if m := _YEAR_ONLY.search(text):
        year = int(m.group(1))
        return _year_bounds(year), m.span()

    return None


def parse_query(raw_query: str) -> ParsedQuery:
    text = raw_query.strip()

    # --- Try a two-sided range first: "January 2024 to March 2024" ---
    range_match = _RANGE_SEP.search(text)
    if range_match:
        before, after = text[: range_match.start()], text[range_match.end() :]
        left = _find_single_date_span(before)
        right = _find_single_date_span(after)
        if left and right:
            (start, _), left_span = left
            (_, end), right_span = right
            # Reconstruct the full matched phrase (left date + separator + right date)
            left_phrase_start = left_span[0]
            right_phrase_end = range_match.end() + right_span[1]
            matched_phrase = text[left_phrase_start:right_phrase_end]
            remainder = (text[:left_phrase_start] + " " + text[right_phrase_end:]).strip()
            return ParsedQuery(start, end, _clean_remainder(remainder), matched_phrase)

    # --- Single date expression ---
    found = _find_single_date_span(text)
    if found:
        (start, end), (span_start, span_end) = found
        matched_phrase = text[span_start:span_end]
        remainder = (text[:span_start] + " " + text[span_end:]).strip()
        return ParsedQuery(start, end, _clean_remainder(remainder), matched_phrase)

    # --- No date at all: the whole thing is a semantic query ---
    return ParsedQuery(None, None, text, None)
