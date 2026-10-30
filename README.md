# Appium AI Mobile Agent

AI agents for **native Android and iOS testing** with Appium:

1. **Self-healing locators.** When an app update renames an element id, the test finds the element again from a plain description ("Sign in button"), keeps running, and logs the broken locator so it gets fixed.
2. **Exploratory testing agent.** Give it a goal and test data. It works through the app screen by screen like a tester would, reports crashes, error screens and accessibility gaps with steps to reproduce, and turns a successful run into a plain Appium regression test.

```text
$ mobile-agent explore --goal "Sign in, add Wireless Earbuds to the cart, open the cart, apply promo code SAVE20 and checkout" \
    --data '{"email":"demo@shoplite.test","password":"secret123","promo":"SAVE20"}' --success-text "Order placed"

Goal reached: False (error screen) in 8 steps
  [Medium] ACCESSIBILITY: ImageButton (id=cart_icon) has no accessibility label
  [High] ERROR_SCREEN: "Something went wrong. Please try again." shown
```

The agent found that checkout fails whenever a promo code is applied, and wrote the repro steps:
[`examples/promo-checkout-defect.md`](examples/promo-checkout-defect.md). Without the promo code the same flow passes, and the agent generates [`examples/test_generated_flow.py`](examples/test_generated_flow.py).

## How the exploratory agent works

```text
page source ─▶ compact element list ─▶ checks: crash? error text? unlabeled controls? goal reached?
     ▲                                                  │
     │                                                  ▼
 execute with a stable Appium locator  ◀── model picks the next action (tap / type / back / give up)
     │
     └─▶ step recorded: action, element, locator, reason
```

- **The model sees elements, not XML.** Each screen becomes lines like `[4] Button text="Add to cart" a11y="Add Wireless Earbuds to cart" tappable`. Same format for Android (UiAutomator2) and iOS (XCUITest).
- **Locators are chosen in code, not by the model:** accessibility id first, then resource id / iOS name, then visible text. The model only says *which* element; the agent decides *how* to find it, so generated tests use the same locators a senior engineer would.
- **Guard rails:** invalid indexes are ignored, repeated screens end the run as `STUCK`, and `max_steps` caps cost.
- **Passwords never leak.** Repro steps show `<password>` and generated tests read `TEST_PASSWORD` from the environment.

## How self-healing works

```python
from appium.webdriver.common.appiumby import AppiumBy
from mobile_agent.drivers import AppiumDevice
from mobile_agent.healing import Healer

device = AppiumDevice("caps/android-emulator.json")
healer = Healer(device)
healer.find(AppiumBy.ID, "com.shoplite:id/signin_button", "Sign in button on the login screen").click()
```

1. Try the original locator.
2. If it is gone, send the current screen's elements and the description to the model.
3. Build a stable locator for the element it picks, verify it resolves, and continue.
4. Append the heal to `reports/healing-report.jsonl` (`broken` → `healed`), so the test code gets fixed instead of silently drifting.

`mobile-agent heal-demo` shows this on the simulated app, whose v2 build renamed `signin_button` to `submit_signin`.

## Run it without a device

The tests use `SimulatedShopLite`, a small in-process Android app whose page sources match what UiAutomator2 returns. It has three seeded defects: a renamed button id, a cart icon with no accessibility label, and a checkout failure when a promo code is applied.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                 # 16 tests, offline, mock model
mobile-agent heal-demo
```

Use a real model with `LLM_PROVIDER=anthropic` (or `openai`) and an API key; see `.env.example`.

## Run it on a real emulator or device

```bash
npm install -g appium
appium driver install uiautomator2        # Android
appium driver install xcuitest            # iOS (macOS + Xcode)
appium &

# edit caps/android-emulator.json (or caps/ios-simulator.json) to point at your app
mobile-agent explore --app device --caps caps/android-emulator.json \
  --goal "Sign in and open order history" --data '{"email": "...", "password": "..."}' --success-text "Order history"

APPIUM_SERVER=http://127.0.0.1:4723 pytest tests_device      # device tests are skipped otherwise
```

CI runs the offline suite on every push. A second workflow, **Real Android emulator** (`.github/workflows/real-device.yml`), boots an Android 11 emulator on GitHub Actions, installs Appium's public [ApiDemos](https://github.com/appium/android-apidemos) app and runs `tests_device`: page-source parsing, a broken locator healing on the real app, and an exploration whose generated regression test is then replayed on the device. Reports are uploaded as build artifacts and copied into [`examples/real-device/`](examples/real-device/).

## Project layout

| Path | What it is |
| --- | --- |
| `src/mobile_agent/hierarchy.py` | Parses Android and iOS page sources, builds stable locators, finds unlabeled controls |
| `src/mobile_agent/healing.py` | Self-healing `find()` with heal log |
| `src/mobile_agent/explorer.py` | Goal-driven exploratory agent, report, and regression-test generator |
| `src/mobile_agent/drivers.py` | Real Appium adapter and the simulated app |
| `src/mobile_agent/llm.py` | Anthropic / OpenAI providers and the offline mock |
| `caps/` | Capabilities for an Android emulator and an iOS simulator |
| `tests/` | Offline tests: parsing (Android and iOS), healing, exploration, CLI |
| `tests_device/` | Real-device tests (need an Appium server) |
| `examples/` | Sample exploration reports and a generated regression test |

## Tech

Python · Appium 2 (UiAutomator2, XCUITest) · Appium Python Client · LLM APIs (Anthropic, OpenAI) · pytest · GitHub Actions

## License

MIT
