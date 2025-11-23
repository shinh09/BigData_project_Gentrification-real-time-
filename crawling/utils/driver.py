# utils/driver.py
from seleniumwire import webdriver
import undetected_chromedriver as uc

def build_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--lang=ko-KR")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/537.36"
    )
    return webdriver.Chrome(
        options=opts,
        seleniumwire_options={"verify_ssl": True, "disable_encoding": True}
    )
