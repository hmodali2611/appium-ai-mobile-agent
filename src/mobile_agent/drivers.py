"""
A small driver interface the agents use, with two implementations:

- AppiumDevice: a real Android emulator/device or iOS simulator through an Appium 2 server.
- SimulatedShopLite: an in-process Android app (page sources in the same XML format
  UiAutomator2 returns) so the agents can be developed and tested in CI without a device.
"""

from __future__ import annotations

import json
from typing import Protocol

from .hierarchy import Element, find_in, parse_page_source


class ElementNotFound(Exception):
    pass


class Driver(Protocol):
    platform: str

    def page_source(self) -> str: ...
    def find(self, by: str, value: str) -> object: ...
    def tap(self, handle: object) -> None: ...
    def type_text(self, handle: object, text: str) -> None: ...
    def back(self) -> None: ...
    def screenshot(self, path: str) -> None: ...
    def is_app_running(self) -> bool: ...
    def quit(self) -> None: ...


class AppiumDevice:
    """Thin adapter over the official Appium Python client."""

    def __init__(self, caps_file: str, server: str = "http://127.0.0.1:4723"):
        from appium import webdriver
        from appium.options.android import UiAutomator2Options
        from appium.options.ios import XCUITestOptions

        caps = json.load(open(caps_file))
        self.platform = caps["platformName"].lower()
        options = (XCUITestOptions() if self.platform == "ios" else UiAutomator2Options()).load_capabilities(caps)
        self.driver = webdriver.Remote(server, options=options)
        self.bundle = caps.get("appium:bundleId") or caps.get("appium:appPackage")

    def page_source(self) -> str:
        return self.driver.page_source

    def find(self, by: str, value: str):
        from selenium.common.exceptions import NoSuchElementException

        try:
            return self.driver.find_element(by, value)
        except NoSuchElementException as e:
            raise ElementNotFound(f"{by}={value}") from e

    def tap(self, handle) -> None:
        handle.click()

    def type_text(self, handle, text: str) -> None:
        handle.clear()
        handle.send_keys(text)

    def back(self) -> None:
        self.driver.back()

    def screenshot(self, path: str) -> None:
        self.driver.save_screenshot(path)

    def is_app_running(self) -> bool:
        if not self.bundle:
            return True
        return self.driver.query_app_state(self.bundle) == 4  # 4 = running in foreground

    def quit(self) -> None:
        self.driver.quit()


# ---------------------------------------------------------------------------------------------
# Simulated app
# ---------------------------------------------------------------------------------------------

def _node(cls: str, idx: int, rid: str = "", text: str = "", desc: str = "", hint: str = "", clickable: bool = False) -> str:
    esc = lambda s: s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")  # noqa: E731
    return (
        f'<android.widget.{cls} index="{idx}" package="com.shoplite" class="android.widget.{cls}" '
        f'text="{esc(text)}" hint="{esc(hint)}" resource-id="{"com.shoplite:id/" + rid if rid else ""}" '
        f'content-desc="{esc(desc)}" clickable="{str(clickable).lower()}" enabled="true" displayed="true" '
        f'bounds="[0,{idx * 120}][1080,{idx * 120 + 110}]" />'
    )


class SimulatedShopLite:
    """
    A tiny shopping app with known, realistic defects to give the agents something to find:

    - build="v2" renames the Sign in button id (signin_button -> submit_signin), breaking old locators.
    - The cart icon on the home screen has no accessibility label (TalkBack/VoiceOver defect).
    - Checking out with a promo code applied shows "Something went wrong" (functional defect).
    """

    platform = "android"
    USERS = {"demo@shoplite.test": "secret123"}

    def __init__(self, build: str = "v2"):
        self.build = build
        self.screen = "login"
        self.fields: dict[str, str] = {}
        self.cart = 0
        self.promo = ""
        self.message = ""
        self.history: list[str] = []
        self.running = True

    # --- rendering ----------------------------------------------------------------------------
    def _nodes(self) -> list[str]:
        n: list[str] = []
        add = lambda *a, **k: n.append(_node(*a, idx=len(n), **k))  # noqa: E731
        if self.screen == "login":
            add("TextView", rid="title", text="ShopLite")
            add("EditText", rid="email", text=self.fields.get("email", ""), hint="Email", clickable=True)
            add("EditText", rid="password", text="•" * len(self.fields.get("password", "")), hint="Password", clickable=True)
            add("Button", rid="signin_button" if self.build == "v1" else "submit_signin", text="Sign in", clickable=True)
            if self.message:
                add("TextView", rid="error", text=self.message)
        elif self.screen == "home":
            add("TextView", rid="welcome", text="Welcome, shopper")
            add("ImageButton", rid="cart_icon", clickable=True)  # defect: no content-desc
            add("TextView", rid="product_name", text="Wireless Earbuds")
            add("TextView", rid="product_price", text="$49.00")
            add("Button", rid="add_to_cart", text="Add to cart", desc="Add Wireless Earbuds to cart", clickable=True)
            add("Button", rid="open_cart", text=f"Cart ({self.cart})", clickable=True)
        elif self.screen == "cart":
            add("TextView", rid="cart_title", text="Your cart")
            add("TextView", rid="line_item", text=f"Wireless Earbuds x{self.cart}" if self.cart else "Your cart is empty")
            add("EditText", rid="promo_code", text=self.fields.get("promo", ""), hint="Promo code", clickable=True)
            add("Button", rid="apply_promo", text="Apply", clickable=True)
            total = 49.0 * self.cart * (0.8 if self.promo else 1)
            add("TextView", rid="total", text=f"Total ${total:.2f}")
            if self.message:
                add("TextView", rid="promo_message", text=self.message)
            add("Button", rid="checkout", text="Checkout", clickable=True)
        elif self.screen == "confirmation":
            add("TextView", rid="confirmation", text="Order placed! Thank you.")
            add("Button", rid="continue_shopping", text="Continue shopping", clickable=True)
        elif self.screen == "error":
            add("TextView", rid="error_title", text="Something went wrong. Please try again.")
            add("Button", rid="retry", text="Retry", clickable=True)
        return n

    def page_source(self) -> str:
        body = "\n    ".join(self._nodes())
        return (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n"
            '<hierarchy index="0" class="hierarchy" rotation="0" width="1080" height="2340">\n'
            '  <android.widget.FrameLayout index="0" package="com.shoplite" class="android.widget.FrameLayout" '
            'text="" resource-id="" content-desc="" clickable="false" displayed="true" bounds="[0,0][1080,2340]">\n'
            f"    {body}\n  </android.widget.FrameLayout>\n</hierarchy>"
        )

    def elements(self) -> list[Element]:
        return parse_page_source(self.page_source())

    # --- actions ------------------------------------------------------------------------------
    def find(self, by: str, value: str) -> Element:
        el = find_in(self.elements(), by, value)
        if el is None:
            raise ElementNotFound(f"{by}={value}")
        return el

    def type_text(self, el: Element, text: str) -> None:
        if not el.editable:
            raise ValueError(f"{el.describe()} is not editable")
        key = el.short_id.replace("promo_code", "promo")
        self.fields[key] = text
        self.history.append(f"type {key}")

    def tap(self, el: Element) -> None:
        sid = el.short_id
        self.history.append(f"tap {sid or el.text}")
        self.message = ""
        if sid in ("signin_button", "submit_signin"):
            if self.USERS.get(self.fields.get("email", "")) == self.fields.get("password"):
                self.screen = "home"
            else:
                self.message = "Invalid email or password"
        elif sid == "add_to_cart":
            self.cart += 1
        elif sid in ("open_cart", "cart_icon"):
            self.screen = "cart"
        elif sid == "apply_promo":
            code = self.fields.get("promo", "").upper()
            if code == "SAVE20":
                self.promo = code
                self.message = "SAVE20 applied: 20% off"
            else:
                self.message = "This code is not valid"
        elif sid == "checkout":
            if self.cart == 0:
                self.message = "Your cart is empty"
            elif self.promo:
                self.screen = "error"  # seeded defect
            else:
                self.screen = "confirmation"
        elif sid == "continue_shopping":
            self.screen, self.cart, self.promo = "home", 0, ""
        elif sid == "retry":
            self.screen = "cart"

    def back(self) -> None:
        self.screen = {"cart": "home", "error": "cart", "confirmation": "home"}.get(self.screen, self.screen)

    def screenshot(self, path: str) -> None:
        with open(path, "w") as f:
            f.write(self.page_source())

    def is_app_running(self) -> bool:
        return self.running

    def quit(self) -> None:
        self.running = False
