# -*- coding: utf-8 -*-
"""
STEP 1 (Single File Version): 모든 KEYWORDS 결과를 한 파일로 저장
"""

import os
import re
import time
import random
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import quote

from seleniumwire import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

# =========================
# 🔍 수집 대상 KEYWORDS
# =========================
KEYWORDS = [
    ("성수동 명소", "성수동"),
    ("연남동 명소", "연남동"),
    ("익선동 명소", "익선동"),
    ("을지로 명소", "을지로"),
    ("신사동 명소", "신사동"),
    ("공릉동 명소", "공릉동"),
    ("한남동 명소", "한남동"),
]

WAIT_SEC = 25
PAUSE = (0.8, 1.6)
SCROLL_STEPS = 4


# -------------------------
# 공통 유틸
# -------------------------
def human_pause(a=1.0, b=2.0):
    time.sleep(random.uniform(a, b))


def clean(s):
    return re.sub(r"\s+", " ", (s or "").strip())


# -------------------------
# 🔧 Driver 생성
# -------------------------
def build_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--lang=ko-KR")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1400,900")

    return webdriver.Chrome(
        options=opts,
        seleniumwire_options={"verify_ssl": True, "disable_encoding": True},
    )


# -------------------------
# 검색 URL 생성
# -------------------------
def build_search_url(query, day):
    d = day.strftime("%Y%m%d")
    nso = f"so:dd,p:from{d}to{d}"
    return (
        "https://search.naver.com/search.naver"
        "?ssc=tab.blog.all"
        "&sm=tab_jum"
        f"&query={quote(query)}"
        f"&nso={nso}"
    )


TITLE_SELECTORS = [
    "a.api_txt_lines.total_tit",
    "a.total_tit",
    "a.title_link",
    "div.total_wrap a[href*='blog.naver.com']",
    "a[href*='blog.naver.com']",
]


# -------------------------
# 페이지 로딩 확인
# -------------------------
def ensure_results_ready(driver):
    try:
        WebDriverWait(driver, WAIT_SEC).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        return True
    except Exception:
        return False


def click_next(driver):
    for sel in ["a.btn_next", "a.pg_next", "a.sc_page_next", "a[aria-label='다음']"]:
        btns = driver.find_elements(By.CSS_SELECTOR, sel)
        if btns and btns[0].is_displayed():
            try:
                btns[0].click()
                return True
            except:
                pass
    return False


# -------------------------
# 🔍 특정 “행정동 명소" 하루치 링크 수집
# -------------------------
def list_seeds_for_day(driver, query, day, administrative_dong):
    url = build_search_url(query, day)
    print(f"\n▶ 검색 시작: {administrative_dong} | {url}")

    driver.get(url)

    if not ensure_results_ready(driver):
        print("⚠️ 페이지 로딩 실패")
        return []

    rows, seen = [], set()

    while True:
        # Scroll (Lazy loading)
        for _ in range(SCROLL_STEPS):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight * 0.7);")
            human_pause(*PAUSE)

        anchors = []
        for sel in TITLE_SELECTORS:
            anchors = driver.find_elements(By.CSS_SELECTOR, sel)
            if anchors:
                break

        for a in anchors:
            href = a.get_attribute("href") or ""
            if "blog.naver.com" not in href:
                continue
            if href in seen:
                continue

            seen.add(href)
            title = clean(a.text)

            rows.append({
                "date": day.strftime("%Y-%m-%d"),
                "administrative_dong": administrative_dong,
                "title": title,
                "link": href,
            })

        if not click_next(driver):
            break

    print(f"🔗 {administrative_dong}: {len(rows)}건 수집")
    return rows


# -------------------------
# CSV 저장 (단일 파일)
# -------------------------
def save_single_file(all_rows, target_day):
    if not all_rows:
        print("❌ 전체 KEYWORDS 데이터 없음")
        return

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["link"])

    yyyy = target_day.strftime("%Y")
    day = target_day.strftime("%Y%m%d")

    save_dir = f"./data_html/{yyyy}/links"
    os.makedirs(save_dir, exist_ok=True)
    out_path = f"{save_dir}/links_all_{day}.csv"

    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n✅ 링크 단일 CSV 저장 완료 → {out_path}\n")


# -------------------------
# 🚀 PUBLIC API
# -------------------------
def run_step1(target_day=None):
    if target_day is None:
        target_day = datetime.now() - timedelta(days=1)

    driver = build_driver()
    all_rows = []

    try:
        for query, dong in KEYWORDS:
            rows = list_seeds_for_day(driver, query, target_day, dong)
            all_rows.extend(rows)
    finally:
        driver.quit()

    save_single_file(all_rows, target_day)
