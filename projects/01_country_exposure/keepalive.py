# keepalive.py
# Purpose: Keep the CBAM Streamlit dashboard awake by using a headless Chromium browser.

import sys
from playwright.sync_api import sync_playwright

APP_URL = "https://milcahjoseph-cbam-dashboard.streamlit.app"

WAKE_BUTTON_TEXT = "get this app back up"


def keep_awake() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Visiting {APP_URL}")
        page.goto(APP_URL, wait_until="load", timeout=60000)

        page.wait_for_timeout(15000)

        wake_button = page.get_by_text(WAKE_BUTTON_TEXT, exact=False)
        if wake_button.count() > 0:
            print("App was asleep. Clicking the wake-up button.")
            wake_button.first.click()
            page.wait_for_timeout(30000)
        else:
            print("App is already awake. No action needed.")

        browser.close()
        print("Keep-alive visit complete.")

if __name__ == "__main__":
    try:
        keep_awake()
    except Exception as error:
        print(f"Keep-alive failed: {error}")
        sys.exit(1)
