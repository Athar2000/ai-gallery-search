"""
Pure unit tests for app.services.query_parser — no database, no embedder,
no network. These directly cover the test cases spec section 28 calls out:
exact date, month, year, date range, and "the rest is semantic text".
"""
from datetime import date, timedelta

from app.services.query_parser import parse_query


def test_exact_date():
    p = parse_query("15 August 2025")
    assert (p.start_date, p.end_date) == (date(2025, 8, 15), date(2025, 8, 15))
    assert p.semantic_query == ""


def test_us_style_exact_date():
    p = parse_query("August 15, 2025")
    assert (p.start_date, p.end_date) == (date(2025, 8, 15), date(2025, 8, 15))


def test_month_and_year():
    p = parse_query("August 2025")
    assert (p.start_date, p.end_date) == (date(2025, 8, 1), date(2025, 8, 31))
    assert p.semantic_query == ""


def test_month_abbreviation():
    p = parse_query("Aug 2025")
    assert (p.start_date, p.end_date) == (date(2025, 8, 1), date(2025, 8, 31))


def test_year_only():
    p = parse_query("2025")
    assert (p.start_date, p.end_date) == (date(2025, 1, 1), date(2025, 12, 31))


def test_date_range_month_year_to_month_year():
    p = parse_query("January 2024 to March 2024")
    assert (p.start_date, p.end_date) == (date(2024, 1, 1), date(2024, 3, 31))
    assert p.semantic_query == ""


def test_date_range_with_dash_separator():
    p = parse_query("January 2024 - March 2024")
    assert (p.start_date, p.end_date) == (date(2024, 1, 1), date(2024, 3, 31))


def test_pure_semantic_query_has_no_date():
    p = parse_query("beach sunset")
    assert p.start_date is None and p.end_date is None
    assert p.semantic_query == "beach sunset"


def test_combined_metadata_and_semantic_query():
    p = parse_query("Show my photos from August 2025 with cars")
    assert (p.start_date, p.end_date) == (date(2025, 8, 1), date(2025, 8, 31))
    assert "cars" in p.semantic_query
    assert "August 2025" not in p.semantic_query


def test_date_with_leading_and_trailing_connectors_is_stripped():
    p = parse_query("photos from Lucknow in December 2025")
    assert (p.start_date, p.end_date) == (date(2025, 12, 1), date(2025, 12, 31))
    # "photos"/"from" are filler/connector words with no search content of
    # their own -- stripped so the semantic query is just the meaningful part.
    assert p.semantic_query == "Lucknow"


def test_today():
    p = parse_query("today")
    today = date.today()
    assert (p.start_date, p.end_date) == (today, today)


def test_yesterday():
    p = parse_query("yesterday")
    y = date.today() - timedelta(days=1)
    assert (p.start_date, p.end_date) == (y, y)


def test_this_week_spans_seven_days_including_today():
    p = parse_query("photos from this week")
    assert p.start_date <= date.today() <= p.end_date
    assert (p.end_date - p.start_date).days == 6


def test_this_month():
    p = parse_query("this month")
    today = date.today()
    assert p.start_date.year == today.year and p.start_date.month == today.month
    assert p.start_date.day == 1


def test_last_year():
    p = parse_query("last year")
    assert p.start_date == date(date.today().year - 1, 1, 1)
    assert p.end_date == date(date.today().year - 1, 12, 31)


def test_last_summer_is_june_through_august():
    p = parse_query("photos from my trip last summer")
    assert p.start_date.month == 6 and p.start_date.day == 1
    assert p.end_date.month == 8 and p.end_date.day == 31
    assert p.semantic_query == "trip"


def test_no_query_text_at_all_is_pure_semantic_empty():
    p = parse_query("")
    assert p.start_date is None
    assert p.semantic_query == ""


def test_filler_only_remainder_after_date_becomes_pure_date_query():
    """
    Regression test: "photos from August 2025" must not leave "photos" as
    a leftover semantic query -- that would silently turn a pure date
    lookup into a similarity-filtered one and could drop real matches
    (found by running this exact query against the live API).
    """
    p = parse_query("photos from August 2025")
    assert (p.start_date, p.end_date) == (date(2025, 8, 1), date(2025, 8, 31))
    assert p.semantic_query == ""


def test_show_my_photos_prefix_is_stripped_from_semantic_remainder():
    p = parse_query("Show my photos from August 2025 with cars")
    assert p.semantic_query == "cars"


def test_articles_dont_leak_into_semantic_remainder_after_a_date_match():
    """
    Regression test: found by running 'photos with a bus' (plus a date)
    against the live search API -- after the date phrase is stripped, a
    bare leftover "a" silently turned what should've been a clean filter
    query into a (falsely) similarity-filtered one that then matched
    nothing. Multi-entity extraction ("Athar", "car") itself happens in
    ranking.py, not here -- see test_person_search.py / test_object_search.py
    for those end-to-end cases.
    """
    p = parse_query("photos with a bus from August 2025")
    assert p.semantic_query == "bus"
