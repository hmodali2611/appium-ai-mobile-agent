import json

import pytest
from appium.webdriver.common.appiumby import AppiumBy

from mobile_agent.drivers import ElementNotFound, SimulatedShopLite
from mobile_agent.healing import Healer
from mobile_agent.llm import MockLLM


def test_broken_id_heals_and_is_logged(tmp_path):
    app = SimulatedShopLite(build="v2")  # Sign in id renamed in this build
    report = tmp_path / "heal.jsonl"
    healer = Healer(app, MockLLM(), report)
    app.type_text(healer.find(AppiumBy.ID, "com.shoplite:id/email", "Email field"), "demo@shoplite.test")
    app.type_text(healer.find(AppiumBy.ID, "com.shoplite:id/password", "Password field"), "secret123")
    app.tap(healer.find(AppiumBy.ID, "com.shoplite:id/signin_button", "Sign in button"))

    assert app.screen == "home"
    assert len(healer.events) == 1
    event = json.loads(report.read_text().strip())
    assert event["broken"] == "id=com.shoplite:id/signin_button"
    assert event["healed"] == "id=com.shoplite:id/submit_signin"


def test_working_locator_is_not_healed(tmp_path):
    healer = Healer(SimulatedShopLite(build="v1"), MockLLM(), tmp_path / "r.jsonl")
    healer.find(AppiumBy.ID, "com.shoplite:id/signin_button", "Sign in button")
    assert healer.events == []


def test_unhealable_locator_fails_loudly(tmp_path):
    healer = Healer(SimulatedShopLite(), MockLLM(), tmp_path / "r.jsonl")
    with pytest.raises(ElementNotFound, match="could not be healed"):
        healer.find(AppiumBy.ID, "com.shoplite:id/biometric_toggle", "Face ID toggle")
