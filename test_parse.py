"""Offline self-checks for parsing/normalisation (no network)."""

import re
import sys

from providers import _clean_km, _clean_price

FIXTURE = """
<div class="iompba0 k1c10j0 card"><a class="x" href="/cars/details/1997-toyota-crown-super-deluxe/SSE-AD-123/?foo=1">
<span class="iompba0 _1lalutrhu a6hzxt1" style="-webkit-line-clamp:2">1997 Toyota Crown Super Deluxe</span>
<span class="iompba0 _1lalutrhu _1tlv1feam a6hzxte a6hzxt0">$15,000</span>
</a><div class="iompba0 iompba3"><div alt="123,456 km" data-icontype="kms-taco"><svg><title>123,456 km</title></svg></div></div></div>
<div class="iompba0 k1c10j0 card"><a class="x" href="/cars/details/2000-toyota-crown-royal/SSE-AD-456/"><span class="iompba0 _1lalutrhu a6hzxt1" style="-webkit-line-clamp:2">2000 Toyota Crown Royal</span><span class="iompba0 _1lalutrhu _1tlv1feam a6hzxte a6hzxt0">$18,000</span></a></div>
"""


def main() -> int:
    assert _clean_price("$15,000") == 15000
    assert _clean_price(None) is None
    assert _clean_km("123,456 km") == 123456
    assert _clean_km("80 km") == 80

    from providers import _parse_carsales_cards

    cards = _parse_carsales_cards(FIXTURE)
    assert len(cards) == 2, cards
    c0 = cards[0]
    assert c0["title"] == "1997 Toyota Crown Super Deluxe"
    assert c0["price"] == 15000
    assert c0["odometer_km"] == 123456
    assert c0["url"] == "https://www.carsales.com.au/cars/details/1997-toyota-crown-super-deluxe/SSE-AD-123/"
    assert c0["source"] == "carsales"
    assert cards[1]["odometer_km"] is None
    print("OK: all self-checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
