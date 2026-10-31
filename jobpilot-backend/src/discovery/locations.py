import re
from dataclasses import dataclass

INDIA_CITIES = {
    "pune", "mumbai", "bengaluru", "bangalore", "hyderabad", "chennai", "gurgaon", "gurugram",
    "noida", "delhi", "new delhi", "kolkata", "ahmedabad", "kochi", "thiruvananthapuram",
    "coimbatore", "jaipur", "indore", "nagpur", "mysore", "chandigarh", "vadodara",
    "navi mumbai", "thane",
}
INDIA_ALIASES = {"india", "in", "ind"} | INDIA_CITIES


@dataclass
class LocationMatch:
    ok: bool
    reason: str


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z]+", s.lower()))


def match_location(
    location: str | None,
    country: str | None,
    profile_locations: list[str],
    include_remote: bool = True,
) -> LocationMatch:
    wanted = {p.lower() for p in profile_locations}
    if any(w in ("india", "in") for w in wanted):
        wanted |= INDIA_ALIASES
    text = (location or "").lower()
    if country and country.lower() in wanted:
        return LocationMatch(True, "country matches")
    if re.search(r"\b\d+\s+locations?\b", text):
        return LocationMatch(True, "multiple locations")
    toks = _tokens(text)
    if toks & wanted or any(" " in w and w in text for w in wanted):
        return LocationMatch(True, "location matches")
    if "remote" in toks and include_remote:
        # remote counts only when no other country is named
        filler = {"remote", "anywhere", "hybrid", "work", "from", "home"}
        named_other = bool(toks - filler) and not (toks & wanted)
        if country is None and not named_other:
            return LocationMatch(True, "remote")
    return LocationMatch(False, "outside your locations")
