import json
import os
import tempfile
from pathlib import Path

import pytest

SERVER = os.environ.get("APPIUM_SERVER")
CAPS = os.environ.get("CAPS_FILE", "caps/android-apidemos.json")
OUT = Path(os.environ.get("REPORT_DIR", "out/real-device"))


def pytest_collection_modifyitems(config, items):
    if SERVER:
        return
    skip = pytest.mark.skip(reason="APPIUM_SERVER not set: real-device tests need an Appium server and an emulator")
    for item in items:
        item.add_marker(skip)


@pytest.fixture
def caps_file() -> str:
    """Caps with the APK path made absolute, so Appium finds it from any working directory."""
    caps = json.load(open(CAPS))
    if caps.get("appium:app") and not os.path.isabs(caps["appium:app"]):
        caps["appium:app"] = os.path.abspath(caps["appium:app"])
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    json.dump(caps, f)
    f.close()
    return f.name


@pytest.fixture
def device(caps_file):
    from mobile_agent.drivers import AppiumDevice

    d = AppiumDevice(caps_file, SERVER)
    yield d
    d.quit()


@pytest.fixture
def out_dir() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    return OUT
