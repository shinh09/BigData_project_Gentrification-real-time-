# -*- coding: utf-8 -*-
"""
STEP 1: 전날 하루치 네이버 블로그 검색 결과(제목/링크) 수집

- 대상: KEYWORDS 리스트의 (검색쿼리, 행정동명)
- 날짜: 오늘 기준 '전날' 하루
- 저장 위치:
    ./data_html/{동네}_명소/{YYYY}/links/links_{동네}_명소_{YYYYMMDD}.csv
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
# 🔍 수집할 KEYWORDS
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

WAIT_SEC     = 25
PAUSE        = (0.8, 1.6)
SCROLL_STEPS = 4

def human_pause(a=1.0, b=2.0):
    time.sleep(random.uniform(a, b))

def clean(s):
    return re.sub(r"\s+", " ", (s or "").strip())

def sanitize_for_fname(s: str) -> str:
    s = s.strip().replace(" ", "_")
    s = re.sub(r"[^\w\-\.가-힣]+", "", s)
    return s

# -------------------------
# 🔧 Driver 생성
# -------------------------
def build_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--lang=ko-KR")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(
        options=opts,
        seleniumwire_options={"verify_ssl": True, "disable_encoding": True},
    )

# -------------------------
# 🔍 네이버 검색 URL 생성 (하루 단위, 블로그 탭 강제)
#  - 네가 직접 확인한 패턴:
#    https://search.naver.com/search.naver?ssc=tab.blog.all&sm=tab_jum&query=성수동+명소
#  - 여기에 nso(날짜)만 붙여서 사용
# -------------------------
def build_search_url(q, day):
    f = day.strftime("%Y%m%d")
    # nso는 원래처럼 so:dd,p:fromYYYYMMDDtoYYYYMMDD
    nso = f"so:dd,p:from{f}to{f}"

    return (
        "https://search.naver.com/search.naver"
        "?ssc=tab.blog.all"
        "&sm=tab_jum"
        f"&query={quote(q)}"
        f"&nso={nso}"
    )

# -------------------------
# 📌 Debug 저장
# -------------------------
def dump_debug(driver, label, save_dir):
    os.makedirs(save_dir, exist_ok=True)
    html_path = os.path.join(save_dir, f"DEBUG_{label}.html")
    png_path  = os.path.join(save_dir, f"DEBUG_{label}.png")
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
    except Exception:
        pass
    try:
        driver.save_screenshot(png_path)
    except Exception:
        pass
    print(f"   ↳ 디버그 저장: {html_path}, {png_path}")

# -------------------------
# CSS 셀렉터 후보군 (블로그 결과용)
# -------------------------
TITLE_SELECTORS = [
    "a.api_txt_lines.total_tit",   # 예전/현재 블로그 제목 링크
    "a.total_tit",
    "a.title_link",
    "div.total_wrap a[href*='blog.naver.com']",
    "a[href*='blog.naver.com']",
]

def ensure_results_ready(driver):
    try:
        # 페이지 전체 로딩 완료까지 기다리기
        WebDriverWait(driver, WAIT_SEC).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # lazy load 유도(스크롤 위아래 조금씩)
        for _ in range(2):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight*0.5);")
            time.sleep(0.8)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.4)

        # 블로그 결과 영역이 실제로 나타날 때까지 대기
        def ok(d):
            for s in TITLE_SELECTORS:
                if d.find_elements(By.CSS_SELECTOR, s):
                    return True
            # 블로그 결과가 아예 없을 때도 빠져나오도록
            return "검색결과가 없습니다" in d.page_source

        WebDriverWait(driver, WAIT_SEC).until(ok)
        return True
    except Exception:
        return False

def click_next(driver):
    # 블로그 검색 페이지의 "다음" 버튼들 후보
    for sel in ["a.btn_next", "a.pg_next", "a.sc_page_next", "a[aria-label='다음']"]:
        btns = driver.find_elements(By.CSS_SELECTOR, sel)
        if btns and btns[0].is_displayed():
            try:
                btns[0].click()
                return True
            except Exception:
                pass
    return False

# -------------------------
# 🔍 하루치 검색 결과 수집
# -------------------------
def list_seeds_for_day(driver, query, day, save_dir, dong_slug):
    url = build_search_url(query, day)
    print(f"\n📅 [{dong_slug}] {day:%Y-%m-%d} 링크 수집 시작: {url}")

    driver.get(url)

    # 실제로 어디로 들어갔는지 확인 (통합인지 / 블로그인지 체크용)
    print("   👉 실제 접속된 URL:", driver.current_url)

    if not ensure_results_ready(driver):
        print("⚠️ 초기 로딩 실패")
        dump_debug(driver, f"{dong_slug}_{day:%Y%m%d}_init_fail", save_dir)
        return []

    seeds, seen = [], set()
    page_idx = 1

    while True:
        # 스크롤 → lazy load
        for _ in range(SCROLL_STEPS):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight*0.85);")
            human_pause(*PAUSE)

        anchors = []
        for sel in TITLE_SELECTORS:
            anchors = driver.find_elements(By.CSS_SELECTOR, sel)
            if anchors:
                break

        if not anchors:
            print(f"⚠️ [{dong_slug}] p{page_idx} 제목 셀렉터 없음")
            dump_debug(driver, f"{dong_slug}_{day:%Y%m%d}_p{page_idx}_no_titles", save_dir)

        for a in anchors:
            href = a.get_attribute("href") or ""
            if not href:
                continue
            if ("blog.naver.com" not in href) and ("m.blog.naver.com" not in href):
                continue
            if href in seen:
                continue

            seen.add(href)
            title = clean(a.text) or clean(a.get_attribute("title") or "")
            seeds.append(
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "title": title,
                    "link": href,
                }
            )

        if not click_next(driver):
            break
        page_idx += 1
        human_pause(*PAUSE)

    print(f"🔗 [{dong_slug}] 수집 링크: {len(seeds)}건")
    return seeds

# -------------------------
# 💾 하루치 CSV 저장
# -------------------------
def save_csv(rows, dong_slug, day, save_dir):
    if not rows:
        print(f"📦 [{dong_slug}] {day:%Y%m%d}: 저장할 데이터 없음")
        return

    df = pd.DataFrame(rows, columns=["date", "title", "link"])
    df = df.drop_duplicates(subset=["link"]).reset_index(drop=True)

    os.makedirs(save_dir, exist_ok=True)
    out_path = os.path.join(save_dir, f"links_{dong_slug}_{day:%Y%m%d}.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"✅ [{dong_slug}] CSV 저장 완료 → {out_path}")

# -------------------------
# 🚀 PUBLIC API: 전날 하루치 전체 KEYWORDS 실행
# -------------------------
def run_step1(target_day=None):
    """
    target_day가 None이면 '오늘 기준 전날'로 설정.
    """
    if target_day is None:
        today = datetime.now()
        target_day = today - timedelta(days=1)

    driver = build_driver()
    try:
        for query, dong in KEYWORDS:
            dong_slug = f"{dong}_명소"
            year_str = target_day.strftime("%Y")
            save_dir = f"./data_html/{dong_slug}/{year_str}/links"

            rows = list_seeds_for_day(
                driver=driver,
                query=query,
                day=target_day,
                save_dir=save_dir,
                dong_slug=dong_slug,
            )
            save_csv(rows, dong_slug, target_day, save_dir)
    finally:
        driver.quit()

# -------------------------
# 🧪 직접 실행용
# -------------------------
def main():
    run_step1()

if __name__ == "__main__":
    main()
