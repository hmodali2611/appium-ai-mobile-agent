from appium.webdriver.common.appiumby import AppiumBy

from mobile_agent.hierarchy import accessibility_issues, best_locator, find_in, parse_page_source


def test_parses_android_uiautomator2_source(android_xml):
    els = parse_page_source(android_xml)
    assert [e.type for e in els] == ["TextView", "EditText", "EditText", "Button"]
    email = els[1]
    assert email.platform == "android" and email.editable and email.hint == "Email"
    assert email.describe() == '[1] EditText hint="Email" id=email editable'


def test_parses_ios_xcuitest_source(ios_xml):
    els = parse_page_source(ios_xml)
    assert els[0].platform == "ios"
    types = [e.type for e in els]
    assert "TextField" in types and "SecureTextField" in types and types.count("Button") == 2
    email = next(e for e in els if e.type == "TextField")
    assert email.editable and email.hint == "Email" and email.text == ""


def test_best_locator_prefers_accessibility_then_id_then_text(android_xml, ios_xml):
    a = parse_page_source(android_xml)
    assert best_locator(a[3]) == (AppiumBy.ID, "com.shoplite:id/submit_signin")
    i = parse_page_source(ios_xml)
    sign_in = next(e for e in i if e.desc == "Sign in")
    assert best_locator(sign_in) == (AppiumBy.ACCESSIBILITY_ID, "signInButton")


def test_find_in_resolves_locators(android_xml):
    els = parse_page_source(android_xml)
    assert find_in(els, AppiumBy.ID, "com.shoplite:id/email").hint == "Email"
    assert find_in(els, AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Sign in")').type == "Button"
    assert find_in(els, AppiumBy.ID, "com.shoplite:id/missing") is None


def test_flags_unlabeled_buttons_for_voiceover(ios_xml):
    assert accessibility_issues(parse_page_source(ios_xml)) == ["Button at [340,40][44x44] has no accessibility label"]
