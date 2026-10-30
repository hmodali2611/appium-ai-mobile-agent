"""
mobile-agent explore --app sim --goal "..." --data '{"email": "...", "password": "..."}' --success-text "Order placed"
mobile-agent explore --app device --caps caps/android-emulator.json --goal "..." --success-text "..."
mobile-agent heal-demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from appium.webdriver.common.appiumby import AppiumBy

from .drivers import AppiumDevice, SimulatedShopLite
from .explorer import explore, to_pytest
from .healing import Healer


def cmd_explore(args) -> int:
    driver = SimulatedShopLite(args.build) if args.app == "sim" else AppiumDevice(args.caps, args.server)
    try:
        report = explore(driver, args.goal, json.loads(args.data), args.success_text, max_steps=args.max_steps)
    finally:
        if args.app != "sim":
            driver.quit()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "exploration.md").write_text(report.to_markdown())
    print(f"Goal reached: {report.achieved} ({report.stop_reason}) in {len(report.steps)} steps")
    for f in report.findings:
        print(f"  [{f.severity}] {f.kind}: {f.detail}")
    if report.achieved and args.success_text:
        test_file = args.out / "test_generated_flow.py"
        test_file.write_text(to_pytest(report, args.success_text, args.caps))
        print(f"Regression test written to {test_file}")
    print(f"Report: {args.out / 'exploration.md'}")
    return 0 if report.achieved else 1


def cmd_heal_demo(args) -> int:
    """The v2 build renamed the Sign in button id. The old locator heals instead of failing the run."""
    app = SimulatedShopLite(build="v2")
    healer = Healer(app, report=args.out / "healing-report.jsonl")
    app.type_text(healer.find(AppiumBy.ID, "com.shoplite:id/email", "Email field"), "demo@shoplite.test")
    app.type_text(healer.find(AppiumBy.ID, "com.shoplite:id/password", "Password field"), "secret123")
    app.tap(healer.find(AppiumBy.ID, "com.shoplite:id/signin_button", "Sign in button on the login screen"))
    print(f"Screen after sign in: {app.screen}")
    for e in healer.events:
        print(f"Healed: {e.broken}  ->  {e.healed}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mobile-agent", description="AI agents for native mobile testing")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("explore", help="Goal-driven exploratory test")
    e.add_argument("--app", choices=["sim", "device"], default="sim")
    e.add_argument("--build", default="v2", help="simulated app build (sim only)")
    e.add_argument("--caps", default="caps/android-emulator.json")
    e.add_argument("--server", default="http://127.0.0.1:4723")
    e.add_argument("--goal", required=True)
    e.add_argument("--data", default="{}", help="JSON test data, e.g. credentials and promo codes")
    e.add_argument("--success-text")
    e.add_argument("--max-steps", type=int, default=25)
    e.add_argument("--out", type=Path, default=Path("out"))
    e.set_defaults(fn=cmd_explore)

    h = sub.add_parser("heal-demo", help="Show a broken locator healing on the simulated app")
    h.add_argument("--out", type=Path, default=Path("reports"))
    h.set_defaults(fn=cmd_heal_demo)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
