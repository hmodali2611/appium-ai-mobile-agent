"""
Real-device tests against Appium's public ApiDemos app on an Android emulator.
Run in CI by the android-emulator job; locally:

    appium &
    APPIUM_SERVER=http://127.0.0.1:4723 pytest tests_device -v
"""

import subprocess
import sys

from appium.webdriver.common.appiumby import AppiumBy

from mobile_agent.explorer import explore, to_pytest
from mobile_agent.healing import Healer
from mobile_agent.hierarchy import parse_page_source

GOAL = "Open Views and then Buttons"
SUCCESS = "Small"


def test_page_source_parses_on_a_real_device(device, out_dir):
    source = device.page_source()
    (out_dir / "apidemos-home.xml").write_text(source)
    labels = [e.text for e in parse_page_source(source)]
    assert "Views" in labels and "Accessibility" in labels


def test_broken_locator_heals_on_a_real_device(device, out_dir):
    healer = Healer(device, report=out_dir / "healing-report.jsonl")
    # This id does not exist in ApiDemos: it simulates a locator broken by an app update.
    views = healer.find(AppiumBy.ID, "io.appium.android.apis:id/views_menu", "Views item in the main list")
    views.click()
    assert healer.events and healer.events[0].healed == "accessibility id=Views"
    assert device.find(AppiumBy.ACCESSIBILITY_ID, "Buttons")


def test_exploration_reaches_goal_and_generated_test_replays(device, caps_file, out_dir):
    report = explore(device, GOAL, {}, SUCCESS, max_steps=8)
    (out_dir / "exploration.md").write_text(report.to_markdown())
    assert report.achieved, report.stop_reason

    generated = out_dir / "test_generated_apidemos.py"
    generated.write_text(to_pytest(report, SUCCESS, caps_file))
    device.quit()  # free the session so the generated test can start its own

    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(generated)],
                            capture_output=True, text=True)
    (out_dir / "generated-test-run.txt").write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout[-2000:]
