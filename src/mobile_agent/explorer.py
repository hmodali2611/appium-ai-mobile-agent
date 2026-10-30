"""
Goal-driven exploratory testing agent for native apps.

    observe screen ─▶ check for crashes, error screens, accessibility gaps ─▶ ask model for next action
          ▲                                                                            │
          └────────────── execute with a stable Appium locator, record the step ◀──────┘

Ends when the success text appears, an error screen or crash is found, the model gives up,
the agent is stuck in a loop, or max_steps is reached. A successful run is turned into a
replayable pytest + Appium regression test.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from .drivers import Driver
from .hierarchy import Element, accessibility_issues, best_locator, parse_page_source
from .llm import LLM, extract_json, get_llm

SYSTEM = """You are an expert mobile QA engineer exploring a native app to reach a goal.
Each turn you get the goal, test data, your previous actions and the current screen elements.
Reply with ONLY JSON, one of:
  {"action": "tap", "index": <n>, "reason": "..."}
  {"action": "type", "index": <n>, "text": "...", "data_key": "<test data key or empty>", "reason": "..."}
  {"action": "back", "reason": "..."}
  {"action": "give_up", "reason": "..."}
Only use element indexes that appear on the current screen. Use test data values for fields."""

ERROR_TEXT = re.compile(r"something went wrong|unexpected error|has stopped|keeps stopping|try again later|error \d{3}", re.I)


@dataclass
class Step:
    n: int
    action: str
    locator: tuple[str, str] | None
    label: str
    value: str = ""
    data_key: str = ""
    reason: str = ""
    human: str = ""  # how a tester would name the element in repro steps


@dataclass
class Finding:
    kind: str  # ERROR_SCREEN | CRASH | ACCESSIBILITY | STUCK
    severity: str
    detail: str
    repro: list[str] = field(default_factory=list)


@dataclass
class ExplorationReport:
    goal: str
    platform: str
    achieved: bool
    stop_reason: str
    steps: list[Step]
    findings: list[Finding]

    def to_markdown(self) -> str:
        lines = [
            f"# Exploration report: {self.goal}",
            "",
            f"- Platform: {self.platform}",
            f"- Goal reached: {'yes' if self.achieved else 'no'} ({self.stop_reason})",
            f"- Steps: {len(self.steps)}",
            "",
            "## Steps",
            "",
            "| # | Action | Element | Locator | Why |",
            "| --- | --- | --- | --- | --- |",
        ]
        for s in self.steps:
            loc = f"`{s.locator[0]}={s.locator[1]}`" if s.locator else "-"
            val = f" '{s.value}'" if s.value and s.action == "type" and s.data_key != "password" else ""
            lines.append(f"| {s.n} | {s.action}{val} | {s.human} | {loc} | {s.reason} |")
        lines += ["", "## Findings", ""]
        if not self.findings:
            lines.append("None.")
        for f in self.findings:
            lines.append(f"### [{f.severity}] {f.kind}: {f.detail}")
            if f.repro:
                lines += ["", "Steps to reproduce:", *[f"{i}. {r}" for i, r in enumerate(f.repro, 1)]]
            lines.append("")
        return "\n".join(lines)


def _label(el: Element) -> str:
    return re.sub(r"\(\d+\)", "", el.describe().split(" ", 1)[1])


def _human(el: Element) -> str:
    return el.text or el.desc or el.hint or el.short_id or el.type


def _screen_key(elements: list[Element]) -> str:
    return hashlib.sha1("|".join(f"{e.type}:{e.short_id}:{e.text}" for e in elements).encode()).hexdigest()[:10]


def explore(
    driver: Driver,
    goal: str,
    data: dict[str, str] | None = None,
    success_text: str | None = None,
    llm: LLM | None = None,
    max_steps: int = 25,
) -> ExplorationReport:
    llm, data = llm or get_llm(), data or {}
    steps: list[Step] = []
    findings: list[Finding] = []
    history: list[str] = []
    seen_a11y: set[str] = set()
    visits: dict[str, int] = {}

    def repro() -> list[str]:
        out = []
        for s in steps:
            if s.action == "type":
                shown = "<password>" if s.data_key == "password" else f"'{s.value}'"
                out.append(f"Enter {shown} in {s.human}")
            elif s.action == "tap":
                out.append(f"Tap {s.human}")
            else:
                out.append(s.action.capitalize())
        return out

    for n in range(1, max_steps + 1):
        if not driver.is_app_running():
            findings.append(Finding("CRASH", "Critical", "the app is no longer running", repro()))
            return ExplorationReport(goal, driver.platform, False, "app crashed", steps, findings)

        elements = parse_page_source(driver.page_source())
        texts = [e.text for e in elements if not e.editable]

        for issue in accessibility_issues(elements):
            if issue not in seen_a11y:
                seen_a11y.add(issue)
                findings.append(Finding("ACCESSIBILITY", "Medium", issue))

        if success_text and any(success_text.lower() in t.lower() for t in texts):
            return ExplorationReport(goal, driver.platform, True, f'saw "{success_text}"', steps, findings)

        errors = [t for t in texts if ERROR_TEXT.search(t)]
        if errors:
            findings.append(Finding("ERROR_SCREEN", "High", f'"{errors[0]}" shown', repro()))
            return ExplorationReport(goal, driver.platform, False, "error screen", steps, findings)

        key = _screen_key(elements)
        visits[key] = visits.get(key, 0) + 1
        if visits[key] > 3:
            findings.append(Finding("STUCK", "Medium", "the same screen came back 4 times without progress", repro()))
            return ExplorationReport(goal, driver.platform, False, "stuck in a loop", steps, findings)

        prompt = "\n".join(
            [
                f"GOAL: {goal}",
                f"TEST DATA: {json.dumps(data)}",
                "HISTORY:",
                *history,
                "SCREEN:",
                *[e.describe() for e in elements],
            ]
        )
        decision = extract_json(llm.complete(SYSTEM, prompt))
        action = decision.get("action")

        if action == "give_up":
            return ExplorationReport(goal, driver.platform, False, f"agent gave up: {decision.get('reason', '')}", steps, findings)
        if action == "back":
            driver.back()
            steps.append(Step(n, "back", None, "-", reason=decision.get("reason", ""), human="Back"))
            history.append("pressed back")
            continue

        el = next((e for e in elements if e.index == decision.get("index")), None)
        if el is None or action not in ("tap", "type"):
            history.append(f"invalid decision ignored: {json.dumps(decision)}")
            continue

        locator = best_locator(el)
        handle = driver.find(*locator)  # exercise the same locator a regression test would use
        if action == "type":
            text = str(decision.get("text", ""))
            driver.type_text(handle, text)
            key_name = decision.get("data_key") or ""
            history.append(f"typed {key_name or text} into {_label(el)}")
            step = Step(n, "type", locator, _label(el), text, key_name, decision.get("reason", ""), _human(el))
        else:
            driver.tap(handle)
            history.append(f'tapped "{_label(el)}"')
            step = Step(n, "tap", locator, _label(el), reason=decision.get("reason", ""), human=_human(el))
        steps.append(step)

    findings.append(Finding("STUCK", "Low", f"goal not reached in {max_steps} steps", repro()))
    return ExplorationReport(goal, driver.platform, False, "max steps reached", steps, findings)


def to_pytest(report: ExplorationReport, success_text: str, caps_file: str) -> str:
    """Turn a successful exploration into a plain Appium regression test anyone can read and run."""
    if not report.achieved:
        raise ValueError("Only successful explorations can be turned into regression tests")
    body = []
    for s in report.steps:
        if s.action == "back":
            body.append("    driver.back()")
            continue
        by, value = s.locator
        by_expr = {
            "accessibility id": "AppiumBy.ACCESSIBILITY_ID",
            "id": "AppiumBy.ID",
            "-android uiautomator": "AppiumBy.ANDROID_UIAUTOMATOR",
            "-ios predicate string": "AppiumBy.IOS_PREDICATE",
        }.get(by, repr(by))
        find = f"wait.until(EC.element_to_be_clickable(({by_expr}, {value!r})))"
        if s.action == "type":
            val = "os.environ['TEST_PASSWORD']" if s.data_key == "password" else repr(s.value)
            body.append(f"    el = {find}\n    el.clear()\n    el.send_keys({val})")
        else:
            body.append(f"    {find}.click()")
    slug = re.sub(r"[^a-z0-9]+", "_", report.goal.lower()).strip("_")[:60]
    steps = "\n".join(body)
    return f'''"""Generated by appium-ai-mobile-agent from an exploration of: {report.goal}"""

import json
import os

import pytest
from appium import webdriver
from appium.options.common import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

pytestmark = pytest.mark.device


@pytest.fixture
def driver():
    caps = json.load(open({caps_file!r}))
    d = webdriver.Remote(os.environ.get("APPIUM_SERVER", "http://127.0.0.1:4723"), options=AppiumOptions().load_capabilities(caps))
    yield d
    d.quit()


def test_{slug}(driver):
    wait = WebDriverWait(driver, 15)
{steps}
    assert wait.until(EC.presence_of_element_located((AppiumBy.XPATH, "//*[contains(@text, {success_text!r}) or contains(@label, {success_text!r})]")))
'''
