"""
Runs against a real emulator/device through Appium. Skipped unless APPIUM_SERVER is set.

    appium &                                  # Appium 2 with the uiautomator2 driver
    export APPIUM_SERVER=http://127.0.0.1:4723
    pytest tests_device --caps caps/android-emulator.json

Shows the healer and the explorer working on a real app session.
"""

import json
import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("APPIUM_SERVER"), reason="APPIUM_SERVER not set")

from mobile_agent.drivers import AppiumDevice  # noqa: E402
from mobile_agent.explorer import explore  # noqa: E402

CAPS = os.environ.get("CAPS_FILE", "caps/android-emulator.json")


@pytest.fixture
def device():
    d = AppiumDevice(CAPS, os.environ["APPIUM_SERVER"])
    yield d
    d.quit()


def test_explore_real_app(device):
    goal = os.environ.get("GOAL", "Open the app's main menu and go to settings")
    data = json.loads(os.environ.get("TEST_DATA", "{}"))
    report = explore(device, goal, data, os.environ.get("SUCCESS_TEXT"), max_steps=15)
    os.makedirs("out", exist_ok=True)
    with open("out/device-exploration.md", "w") as f:
        f.write(report.to_markdown())
    assert not [f for f in report.findings if f.kind in ("CRASH", "ERROR_SCREEN")]
