"""
Self-healing locators for native apps.

    healer = Healer(driver)
    healer.find(AppiumBy.ID, "com.shoplite:id/signin_button", "Sign in button on the login screen").click()

If the locator still works, it is used as-is. If not, the current page source is sent to the
model with a human description of the element; the model picks the element, a stable new
locator is built for it, and the heal is logged so the test code gets fixed.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .drivers import Driver, ElementNotFound
from .hierarchy import best_locator, parse_page_source
from .llm import LLM, extract_json, get_llm


@dataclass
class HealEvent:
    description: str
    broken: str
    healed: str
    platform: str
    timestamp: float


class Healer:
    def __init__(self, driver: Driver, llm: LLM | None = None, report: str | Path = "reports/healing-report.jsonl"):
        self.driver, self.llm, self.report = driver, llm or get_llm(), Path(report)
        self.events: list[HealEvent] = []

    def find(self, by: str, value: str, description: str):
        try:
            return self.driver.find(by, value)
        except ElementNotFound:
            pass

        elements = parse_page_source(self.driver.page_source())
        prompt = "\n".join(
            [
                "TASK: HEAL",
                f"This locator no longer matches: {by}={value}",
                f"DESCRIPTION: {description}",
                'Pick the element that matches the description. Reply ONLY with {"index": <n>} or {"index": -1}.',
                "ELEMENTS:",
                *[e.describe() for e in elements],
            ]
        )
        index = extract_json(self.llm.complete("You repair broken mobile UI test locators.", prompt)).get("index", -1)
        match = next((e for e in elements if e.index == index), None)
        if match is None:
            raise ElementNotFound(f"{by}={value} ({description}) is broken and could not be healed")

        new_by, new_value = best_locator(match)
        handle = self.driver.find(new_by, new_value)  # verify the healed locator really resolves
        event = HealEvent(description, f"{by}={value}", f"{new_by}={new_value}", match.platform, time.time())
        self.events.append(event)
        self.report.parent.mkdir(parents=True, exist_ok=True)
        with self.report.open("a") as f:
            f.write(json.dumps(asdict(event)) + "\n")
        return handle
