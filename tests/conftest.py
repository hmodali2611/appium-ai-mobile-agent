from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def android_xml() -> str:
    return (FIXTURES / "android_login.xml").read_text()


@pytest.fixture
def ios_xml() -> str:
    return (FIXTURES / "ios_login.xml").read_text()


GOAL_PROMO = "Sign in, add Wireless Earbuds to the cart, open the cart, apply promo code SAVE20 and checkout"
GOAL_PLAIN = "Sign in, add Wireless Earbuds to the cart, open the cart and checkout"
CREDS = {"email": "demo@shoplite.test", "password": "secret123"}
