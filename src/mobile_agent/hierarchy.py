"""
Turn an Appium page source (Android UiAutomator2 or iOS XCUITest XML) into a short list of
elements an LLM can reason about, and build stable locators for them.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from appium.webdriver.common.appiumby import AppiumBy

INPUT_TYPES = ("EditText", "TextField", "SecureTextField", "SearchField", "TextView-editable")
BUTTON_TYPES = ("Button", "ImageButton", "Cell", "Switch", "CheckBox")


@dataclass
class Element:
    index: int
    platform: str  # android | ios
    type: str  # short class name: Button, EditText, XCUIElementTypeButton -> Button
    id: str  # resource-id (Android) or accessibility identifier "name" (iOS)
    text: str  # visible text / label
    desc: str  # content-desc (Android) or label (iOS): what screen readers announce
    hint: str
    clickable: bool
    editable: bool
    bounds: str

    @property
    def short_id(self) -> str:
        return self.id.split("/")[-1] if self.id else ""

    def describe(self) -> str:
        parts = [f"[{self.index}] {self.type}"]
        if self.text:
            parts.append(f'text="{self.text}"')
        if self.desc and self.desc != self.text:
            parts.append(f'a11y="{self.desc}"')
        if self.hint:
            parts.append(f'hint="{self.hint}"')
        if self.short_id:
            parts.append(f"id={self.short_id}")
        if self.editable:
            parts.append("editable")
        elif self.clickable:
            parts.append("tappable")
        return " ".join(parts)


def _short(cls: str) -> str:
    return cls.split(".")[-1].replace("XCUIElementType", "")


def parse_page_source(xml: str) -> list[Element]:
    root = ET.fromstring(xml.encode() if isinstance(xml, str) else xml)
    platform = "ios" if root.tag == "AppiumAUT" or root.tag.startswith("XCUIElementType") else "android"
    out: list[Element] = []
    for node in root.iter():
        a = node.attrib
        if platform == "android":
            if "class" not in a or a.get("displayed", "true") == "false":
                continue
            t = _short(a["class"])
            if t in ("FrameLayout", "LinearLayout", "RelativeLayout", "ViewGroup", "hierarchy"):
                continue
            text, desc, rid = a.get("text", ""), a.get("content-desc", ""), a.get("resource-id", "")
            editable = t == "EditText"
            clickable = a.get("clickable") == "true"
            hint = a.get("hint", "")
            bounds = a.get("bounds", "")
        else:
            t = _short(a.get("type", node.tag))
            if t in ("Application", "Window", "Other") or a.get("visible", "true") == "false":
                continue
            rid, desc = a.get("name", ""), a.get("label", "")
            editable = t in ("TextField", "SecureTextField", "SearchField")
            # iOS shows placeholder text as the value of an empty field
            text = "" if editable else (desc or a.get("value", "") or "")
            hint = a.get("value", "") if editable else ""
            clickable = t in BUTTON_TYPES or editable
            bounds = f'[{a.get("x")},{a.get("y")}][{a.get("width")}x{a.get("height")}]'
        if not (text or desc or rid or clickable or editable):
            continue
        out.append(Element(len(out), platform, t, rid, text, desc, hint, clickable, editable, bounds))
    return out


def best_locator(el: Element) -> tuple[str, str]:
    """
    Most stable locator first: accessibility id, then resource id / iOS name,
    then visible text. Mirrors what experienced mobile automation engineers pick by hand.
    """
    if el.platform == "android":
        if el.desc:
            return AppiumBy.ACCESSIBILITY_ID, el.desc
        if el.id:
            return AppiumBy.ID, el.id
        if el.text:
            return AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{el.text}")'
    else:
        if el.id:
            return AppiumBy.ACCESSIBILITY_ID, el.id
        if el.desc:
            return AppiumBy.IOS_PREDICATE, f"label == '{el.desc}'"
    raise ValueError(f"No stable locator for element {el.describe()}")


def find_in(elements: list[Element], by: str, value: str) -> Element | None:
    """Resolve a locator against a parsed hierarchy (used by the simulated driver and for healing checks)."""
    for el in elements:
        if by == AppiumBy.ACCESSIBILITY_ID and value in (el.desc, el.id if el.platform == "ios" else None):
            return el
        if by == AppiumBy.ID and value in (el.id, el.short_id):
            return el
        if by == AppiumBy.ANDROID_UIAUTOMATOR:
            m = re.search(r'text\("(.+?)"\)', value)
            if m and el.text == m.group(1):
                return el
        if by == AppiumBy.IOS_PREDICATE:
            m = re.search(r"label == '(.+?)'", value)
            if m and el.desc == m.group(1):
                return el
    return None


def accessibility_issues(elements: list[Element]) -> list[str]:
    """Tappable controls with no text or accessibility label: unusable with VoiceOver / TalkBack."""
    issues = []
    for el in elements:
        if (el.clickable and not el.editable) and not (el.text or el.desc):
            where = f" (id={el.short_id})" if el.short_id else f" at {el.bounds}"
            issues.append(f"{el.type}{where} has no accessibility label")
    return issues
