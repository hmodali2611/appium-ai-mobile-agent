import ast
import json

from conftest import CREDS, GOAL_PLAIN, GOAL_PROMO
from mobile_agent.drivers import SimulatedShopLite
from mobile_agent.explorer import explore, to_pytest


def test_agent_finds_checkout_defect_with_repro_steps():
    report = explore(SimulatedShopLite(), GOAL_PROMO, {**CREDS, "promo": "SAVE20"}, "Order placed")
    assert not report.achieved and report.stop_reason == "error screen"
    defect = next(f for f in report.findings if f.kind == "ERROR_SCREEN")
    assert defect.severity == "High"
    assert defect.repro[-3:] == ["Enter 'SAVE20' in Promo code", "Tap Apply", "Tap Checkout"]
    assert "Enter <password> in Password" in defect.repro  # secrets never end up in bug reports


def test_agent_reports_missing_accessibility_label():
    report = explore(SimulatedShopLite(), GOAL_PLAIN, CREDS, "Order placed")
    assert ["ImageButton (id=cart_icon) has no accessibility label"] == [
        f.detail for f in report.findings if f.kind == "ACCESSIBILITY"
    ]


def test_successful_run_becomes_a_regression_test():
    report = explore(SimulatedShopLite(), GOAL_PLAIN, CREDS, "Order placed")
    assert report.achieved and len(report.steps) == 6
    code = to_pytest(report, "Order placed", "caps/android-emulator.json")
    ast.parse(code)
    assert "os.environ['TEST_PASSWORD']" in code and "secret123" not in code
    assert "AppiumBy.ACCESSIBILITY_ID, 'Add Wireless Earbuds to cart'" in code


def test_wrong_credentials_end_in_a_stuck_finding_not_an_endless_loop():
    report = explore(SimulatedShopLite(), GOAL_PLAIN, {"email": "demo@shoplite.test", "password": "nope"}, "Order placed")
    assert not report.achieved
    assert report.stop_reason in ("stuck in a loop", "max steps reached") or report.stop_reason.startswith("agent gave up")


class ScriptedLLM:
    """Returns a bad decision first, then gives up: the agent must ignore the bad one safely."""

    name = "scripted"

    def __init__(self):
        self.replies = [{"action": "tap", "index": 99}, {"action": "give_up", "reason": "test"}]

    def complete(self, system, user):
        return json.dumps(self.replies.pop(0))


def test_invalid_model_decisions_are_ignored():
    report = explore(SimulatedShopLite(), GOAL_PLAIN, CREDS, "Order placed", llm=ScriptedLLM())
    assert report.steps == [] and report.stop_reason == "agent gave up: test"


def test_generated_test_checks_success_text_case_insensitively():
    report = explore(SimulatedShopLite(), GOAL_PLAIN, CREDS, "Order placed")
    code = to_pytest(report, "Order placed", "caps/android-emulator.json")
    assert "'order placed' in d.page_source.lower()" in code
