# -*- coding: utf-8 -*-
"""
⏱ 매일 00시 이후 실행 → '전날 하루치'만 크롤링
✔ 대상 키워드 7종 자동 실행
✔ Step1(링크), Step2(본문) 둘 다 수행
✔ 행정동별로 별도 폴더 저장
"""

import os, re, time, random
import pandas as pd
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlparse, parse_qs, urljoin

from seleniumwire import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -----------------------------
# 🔧 공통 유틸
# -----------------------------
def human_pause(a=1.0, b=2.0):
    time.sleep(random.uniform(a, b))

def clean(s):
    import re
    return re.sub(r"\s+", " ", (s or "").strip())

def sanitize_for_fname(s: str) -> str:
    s = s.strip().replace(" ", "_")
    s = re.sub(r"[^\w\-\.가-힣]+", "", s)
    return s

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
    return webdriver.Chrome(options=opts, seleniumwire_options={"verify_ssl": True})

# -----------------------------
# Step1: 하루치 검색 결과 수집
# -----------------------------
TITLE_SELECTORS = [
    "a.api_txt_lines.total_tit",
    "a.total_tit",
    "a.title_link",
    "div.total_wrap a[href*='blog.naver.com']",
    "a[href*='blog.naver.com']",
]

def build_search_url(q, day):
    f = day.strftime("%Y%m%d")
    nso = f"so:dd,p:from{f}to{f}"

    return (
        "https://search.naver.com/search.naver"
        f"?where=blog&sm=tab_opt&ssc=tab.blog.all"
        f"&query={quote(q)}&nso={nso}"
    )

def ensure_results_ready(driver, WAIT_SEC=20):
    try:
        WebDriverWait(driver, WAIT_SEC).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # lazy-load
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight*0.7);")
            time.sleep(0.8)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.3)

        # title selector ready
        WebDriverWait(driver, WAIT_SEC).until(
            lambda d: any(d.find_elements(By.CSS_SELECTOR, s) for s in TITLE_SELECTORS)
        )
        return True
    except:
        return False

def click_next(driver):
    sels = ["a.btn_next", "a.pg_next", "a.sc_page_next", "a[aria-label='다음']"]
    for s in sels:
        btns = driver.find_elements(By.CSS_SELECTOR, s)
        if btns:
            try:
                btns[0].click()
                return True
            except:
                pass
    return False

def crawl_day_links(driver, keyword, target_day):
    url = build_search_url(keyword, target_day)
    print(f"\n📅 [{keyword}] {target_day:%Y-%m-%d} 링크 수집 시작")
    driver.get(url)

    if not ensure_results_ready(driver):
        print("❌ 검색 결과 로딩 실패")
        return []

    seen = set()
    seeds = []
    page_idx = 1

    while True:
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight*0.8);")
            human_pause(0.5, 1.0)

        anchors = []
        for sel in TITLE_SELECTORS:
            anchors = driver.find_elements(By.CSS_SELECTOR, sel)
            if anchors:
                break

        for a in anchors:
            href = a.get_attribute("href") or ""
            if ("blog.naver.com" not in href) and ("m.blog.naver.com" not in href):
                continue
            if href in seen:
                continue
            seen.add(href)

            title = clean(a.text) or clean(a.get_attribute("title") or "")
            seeds.append({
                "date": target_day.strftime("%Y-%m-%d"),
                "title": title,
                "link": href
            })

        if not click_next(driver):
            break
        page_idx += 1
        human_pause(0.5, 1.0)

    print(f"🔗 총 {len(seeds)}건 수집 완료")
    return seeds


# ============================================================
# Step2 ─ 블로그 본문 전체 크롤링
# ============================================================

POST_URL_RE = re.compile(
    r"^https?://(?:(?:m\.)?blog\.naver\.com/[^/]+/\d+"
    r"|blog\.naver\.com/PostView\.naver\?.*?logNo=\d+)"
)


def is_post_url(u):
    return bool(POST_URL_RE.match(u or ""))


def goto_post_view(driver, url):
    driver.get(url)
    human_pause(1.0, 1.8)

    host = urlparse(driver.current_url).netloc.lower()
    if "m.blog.naver.com" in host:
        return True

    # iframe 스킨 처리
    try:
        frame = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#mainFrame"))
        )
        src = frame.get_attribute("src")
        if src.startswith("//"):
            src = "https:" + src
        driver.get(src)
        human_pause(1.0, 1.8)
    except:
        pass

    return True


LIKE_SELECTORS = [
    "span.u_likeit_text._count.num",
    "em.u_cnt._count",
]

COMMENT_SELECTORS = [
    "span.u_cnt._commentCount",
    "span#commentCount",
]


def extract_like_comment(driver):
    def _to_int(s):
        m = re.search(r"([\d,]+)", s or "")
        return int(m.group(1).replace(",", "")) if m else None

    def find_int(selectors):
        for sel in selectors:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for e in els:
                v = _to_int(e.text)
                if v is not None:
                    return v
        return None

    return find_int(LIKE_SELECTORS), find_int(COMMENT_SELECTORS)



def extract_body_html(driver):
    html = driver.page_source
    soup = BeautifulSoup(html, "lxml")

    body_html = ""

    # se-main-container 기준
    main = soup.select_one("div.se-main-container")
    if main:
        body_html = str(main)
    else:
        # fallback
        article = soup.select_one("article")
        body_html = str(article) if article else html

    return body_html[:200000]


def extract_tags_imgs_videos(driver):
    soup = BeautifulSoup(driver.page_source, "lxml")

    # hashtags
    tags = [t.text.strip() for t in soup.select("span.se_hashtag, a.link_tag") if t.text.strip()]

    # images
    imgs = [img.get("src") for img in soup.select("img") if img.get("src", "").startswith("http")]

    # videos (iframe)
    vids = [ifr.get("src") for ifr in soup.select("iframe") if ifr.get("src")]

    return tags, imgs, vids




def crawl_post(driver, row, dong):
    info = {
        "platform": "blog",
        "administrative_dong": dong,
        "title_raw": row.get("title_raw", ""),
        "title": row.get("title", ""),
        "description_raw": row.get("description_raw", ""),
        "link": row["link"],
        "bloggername": "",
        "bloggerlink": "",
        "postdate": "",
        "content_raw": "",
        "hashtags_raw": "",
        "images_raw": "",
        "videos_raw": "",
        "like_count": None,
        "comment_count": None,
        "author_id": "",
        "post_id": "",
        "crawled_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "status": "ok",
    }

    if not is_post_url(info["link"]):
        info["status"] = "skip"
        return info

    try:
        goto_post_view(driver, info["link"])

        # ID 추출
        aid, pid = extract_ids(driver.current_url)
        info["author_id"], info["post_id"] = aid, pid
        info["bloggerlink"] = f"https://blog.naver.com/{aid}"
        info["bloggername"] = aid

        # 본문 HTML
        info["content_raw"] = extract_body_html(driver)

        # 태그/이미지/동영상
        tags, imgs, vids = extract_tags_imgs_videos(driver)
        info["hashtags_raw"] = "|".join(tags)
        info["images_raw"] = "|".join(imgs)
        info["videos_raw"] = "|".join(vids)

        # 좋아요/댓글
        lc, cc = extract_like_comment(driver)
        info["like_count"] = lc
        info["comment_count"] = cc

        # 작성일
        date_el = driver.find_elements(By.CSS_SELECTOR, "span.se_publishDate, span#post_date")
        if date_el:
            raw = date_el[0].text
            m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", raw)
            if m:
                y, mo, d = map(int, m.groups())
                info["postdate"] = f"{y:04d}{mo:02d}{d:02d}"

    except Exception as e:
        info["status"] = f"error:{type(e).__name__}"

    return info




# ============================================================
# 🔥 하루치 전체 실행
# ============================================================

KEYWORDS = [
    ("성수동 명소", "성수동"),
    ("연남동 명소", "연남동"),
    ("익선동 명소", "익선동"),
    ("을지로 명소", "을지로"),
    ("신사동 명소", "신사동"),
    ("공릉동 명소", "공릉동"),
    ("한남동 명소", "한남동"),
]


def run_daily():
    today = datetime.today()
    target_day = today - timedelta(days=1)

    print(f"\n==============================")
    print(f"📌 전날({target_day:%Y-%m-%d}) 하루치 크롤링 시작")
    print(f"==============================\n")

    for query, dong in KEYWORDS:
        print(f"\n\n===== 🔍 {query} / 행정동={dong} =====")

        base_dir = f"./data_html/{sanitize_for_fname(query)}/{target_day:%Y}/"
        DIR_LINKS = os.path.join(base_dir, "day_links")
        DIR_POSTS = os.path.join(base_dir, "day_posts")
        os.makedirs(DIR_LINKS, exist_ok=True)
        os.makedirs(DIR_POSTS, exist_ok=True)

        # Step1 ─ 링크 수집
        driver = build_driver()
        links = crawl_day_links(driver, query, target_day)
        driver.quit()

        step1_path = os.path.join(DIR_LINKS, f"links_{sanitize_for_fname(query)}_{target_day:%Y%m%d}.csv")
        pd.DataFrame(links).to_csv(step1_path, index=False, encoding="utf-8-sig")
        print(f"📁 Step1 저장 완료 → {step1_path}")

        # Step2 ─ 본문 크롤링
        valid_links = [r for r in links if is_post_url(r["link"])]
        print(f"🔍 Step2 시작 — {len(valid_links)}개 본문 처리")

        driver = build_driver()
        out_rows = []
        for i, r in enumerate(valid_links, 1):
            print(f"   → ({i}/{len(valid_links)}) {r['link']}")
            out_rows.append(crawl_post(driver, r, dong))
        driver.quit()

        step2_path = os.path.join(DIR_POSTS, f"posts_{sanitize_for_fname(query)}_{target_day:%Y%m%d}.csv")
        pd.DataFrame(out_rows).to_csv(step2_path, index=False, encoding="utf-8-sig")
        print(f"📁 Step2 저장 완료 → {step2_path}")



if __name__ == "__main__":
    run_daily()