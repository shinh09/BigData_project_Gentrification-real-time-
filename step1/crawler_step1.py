# step1/crawler_step1.py
import os
import pandas as pd
from datetime import datetime

from urllib.parse import quote
from selenium.webdriver.common.by import By
from utils.driver import build_driver
from utils.common import clean, human_pause, sanitize_for_fname, ensure_dir
from step1.selectors_step1 import TITLE_SELECTORS


WAIT_SEC = 20
PAUSE = (0.8, 1.6)
SCROLL_STEPS = 3


def build_search_url(keyword, day):
    f = day.strftime("%Y%m%d")
    nso = f"so:dd,p:from{f}to{f}"
    return f"https://search.naver.com/search.naver?where=blog&query={quote(keyword)}&nso={nso}"


def collect_links_for_day(keyword, day, save_dir):
    ensure_dir(save_dir)

    url = build_search_url(keyword, day)
    print(f"\n📅 Step1: {day.strftime('%Y-%m-%d')} 링크 수집")
    print("URL:", url)

    driver = build_driver()
    driver.get(url)

    # lazy-load용 스크롤
    for _ in range(SCROLL_STEPS):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        human_pause(*PAUSE)

    rows, seen = [], set()

    for sel in TITLE_SELECTORS:
        anchors = driver.find_elements(By.CSS_SELECTOR, sel)
        if anchors:
            break

    for a in anchors:
        link = a.get_attribute("href") or ""
        if "blog.naver.com" not in link:
            continue
        if link in seen:
            continue
        seen.add(link)

        title = clean(a.text)
        rows.append({
            "date": day.strftime("%Y-%m-%d"),
            "title": title,
            "link": link,
        })

    driver.quit()

    fname = f"links_{sanitize_for_fname(keyword)}_{day.strftime('%Y%m%d')}.csv"
    save_path = os.path.join(save_dir, fname)

    pd.DataFrame(rows).to_csv(save_path, index=False, encoding="utf-8-sig")
    print(f"✅ Step1 저장 완료 → {save_path}")
    return save_path
