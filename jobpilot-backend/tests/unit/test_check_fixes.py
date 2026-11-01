from src.discovery.locations import match_location
from src.discovery.readers.generic import next_listing_url


def test_unknown_location_is_kept() -> None:
    assert match_location(None, None, ["India"]).ok
    assert match_location("  ", None, ["India"]).ok
    assert not match_location("Berlin, Germany", None, ["India"]).ok


def test_landing_page_follows_suggestion_then_search_link() -> None:
    results = "https://x.com/careers/jobs/results"
    links = [("About us", "https://x.com/about"), ("Search jobs", "https://x.com/s"),
             ("Results", results)]
    assert next_listing_url(results, links, set()) == results
    assert next_listing_url("https://evil.example/", links, set()) == "https://x.com/s"
    assert next_listing_url(None, links, {"https://x.com/s", results}) is None
