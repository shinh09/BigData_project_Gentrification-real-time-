# -*- coding: utf-8 -*-
"""
STEP 2 (Single File Version):
STEP 1에서 생성된 links_all_*.csv를 읽어
각 링크 상세 본문 크롤링 → blog_posts_all_*.csv 로 저장
"""

import os
import re
import time
import random
import pandas as pd
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urljoin

from seleniumwire import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

WAIT_SEC = 30
PAUSE = (1.0, 2.0)
PROBE_DEBUG = False


# -------------------------
# 기본 유틸
# -------------------------
def human_pause(a=1.0, b=2.0):
    time.sleep(random.uniform(a, b))


def clean(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def build_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--lang=ko-KR")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1400,900")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(
        options=opts,
        seleniumwire_options={"verify_ssl": True, "disable_encoding": True},
    )


# -------------------------
# URL이 실제 네이버 블로그글인지 판별
# -------------------------
POST_URL_RE = re.compile(
    r"^https?://(?:(?:m\.)?blog\.naver\.com/[^/]+/\d+|blog\.naver\.com/PostView\.naver\?.*?logNo=\d+)",
    re.IGNORECASE,
)

def is_post_url(u: str) -> bool:
    return bool(POST_URL_RE.match(u or ""))


# -------------------------
# PostView iframe 처리
# -------------------------
def goto_post_view(driver, url):
    driver.get(url)
    human_pause(*PAUSE)

    host = urlparse(driver.current_url).netloc.lower()
    if "m.blog.naver.com" in host:
        return True

    try:
        WebDriverWait(driver, WAIT_SEC).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#mainFrame"))
        )
        frame = driver.find_element(By.CSS_SELECTOR, "iframe#mainFrame")
        src = frame.get_attribute("src")
        if src:
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin("https://blog.naver.com", src)
            driver.get(src)
            human_pause(*PAUSE)
            return True
    except Exception:
        pass

    if "PostView" in driver.current_url:
        return True

    return False


# -------------------------
# blogId, logNo 추출
# -------------------------
def extract_ids(u):
    p = urlparse(u)
    author_id = post_id = ""

    if "m.blog.naver.com" in p.netloc:
        parts = [x for x in p.path.split("/") if x]
        if len(parts) >= 2:
            author_id, post_id = parts[0], parts[1]

    elif "blog.naver.com" in p.netloc and "PostView.naver" in p.path:
        q = parse_qs(p.query)
        author_id = (q.get("blogId") or [""])[0]
        post_id   = (q.get("logNo")  or [""])[0]

    return author_id, post_id


# -------------------------
# 가장 먼저 발견되는 텍스트
# -------------------------
def get_first_text(driver, selectors):
    for css in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, css)
            txt = clean(el.text)
            if txt:
                return txt
        except Exception:
            pass
    return ""


# -------------------------
# 본문(root 후보들)
# -------------------------
def find_roots(driver):
    cands = [
        "div.se-main-container",
        "div.se_component_wrap",
        "#postViewArea",
        "div#content-area",
        "div#viewTypeSelector",
        "div#_post_content",
        "div.se_textView",
        "article",
    ]
    els = []
    for css in cands:
        els.extend(driver.find_elements(By.CSS_SELECTOR, css))
    return els or [driver.find_element(By.TAG_NAME, "body")]


# -------------------------
# 해시태그 정규화
# -------------------------
def normalize_hashtag(t: str) -> str:
    t = (t or "").strip()
    if not t:
        return ""
    t = re.sub(r"\s+", "", t)
    if not t.startswith("#"):
        t = "#" + t
    return t


# -------------------------
# 본문 / 태그 / 이미지 / 영상 추출
# -------------------------
def extract_body_tags_imgs_videos(driver):
    bodies, tags, imgs, vids = [], [], [], []

    for root in find_roots(driver):

        # 본문
        try:
            t = clean(root.text)
            if t:
                bodies.append(t)
        except:
            pass

        # 태그
        for css in [
            "span.se_hashtag",
            "a.link_tag",
            ".tag_area a",
            ".post_tag a",
            "a[href*='query=%23']",
        ]:
            try:
                for el in root.find_elements(By.CSS_SELECTOR, css):
                    raw = (el.text or el.get_attribute("innerText") or "").strip()
                    ht = normalize_hashtag(raw)
                    if ht and ht not in tags:
                        tags.append(ht)
            except:
                pass

        # 이미지
        for img in root.find_elements(By.CSS_SELECTOR, "img"):
            src = (
                img.get_attribute("src")
                or img.get_attribute("data-src")
                or img.get_attribute("data-lazy-src")
            )
            if src and src.startswith("http") and src not in imgs:
                imgs.append(src)

        # 영상 iframe
        for ifr in root.find_elements(By.CSS_SELECTOR, "iframe"):
            s = ifr.get_attribute("src") or ""
            if any(k in s for k in ["youtube", "tv.naver", "vimeo"]):
                if s not in vids:
                    vids.append(s)

    body = max(bodies, key=len) if bodies else ""
    return body[:200000], tags, imgs, vids


# -------------------------
# 작성자 이름 추출
# -------------------------
def extract_bloggername(driver, fallback_id=""):
    sels = [
        "#nickNameArea",
        "strong#nickNameArea",
        "a.link.pcol2",
        "span.nick",
        "em.nick",
        "div.bloger > a",
    ]
    for s in sels:
        try:
            el = driver.find_element(By.CSS_SELECTOR, s)
            v = clean(el.text)
            if v:
                return v
        except:
            pass
    return fallback_id or ""


# -------------------------
# 공감/댓글 “기다림”
# -------------------------
def wait_engagement_widgets(driver, timeout=8):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "span.u_likeit_text._count.num")
        )
    except:
        pass


LIKE_SELECTORS = [
    "span.u_likeit_text._count.num",
    "span.u_likeit_list_count._count",
]

COMMENT_SELECTORS = [
    "span.u_cnt._commentCount",
    "#commentCount",
    "span.u_cbox_count",
]


# -------------------------
# 공감/댓글 수에서 숫자만 추출
# -------------------------
def _to_int_or_none(s):
    m = re.search(r"([\d,]+)", s or "")
    return int(m.group(1).replace(",", "")) if m else None


def get_int_by_selectors(driver, selectors):
    for css in selectors:
        els = driver.find_elements(By.CSS_SELECTOR, css)
        for el in els:
            n = _to_int_or_none(el.text)
            if n is not None:
                return n
    return None


# -------------------------
# 개별 포스트 크롤링
# -------------------------
def crawl_one(driver, row):
    administrative_dong = row.get("administrative_dong", "")
    link = row["link"]

    info = {
        "platform": "blog",
        "administrative_dong": administrative_dong,
        "title": row.get("title", ""),
        "link": link,
        "bloggername": "",
        "bloggerlink": "",
        "postdate": "",
        "content_raw": "",
        "hashtags": "",
        "images": "",
        "videos": "",
        "like_count": None,
        "comment_count": None,
        "author_id": "",
        "post_id": "",
        "crawled_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "status": "ok",
    }

    try:
        if not is_post_url(link):
            info["status"] = "skip_non_post_url"
            return info

        if not goto_post_view(driver, link):
            info["status"] = "failed_goto_view"
            return info

        # 아이디, 글번호
        aid, pid = extract_ids(driver.current_url)
        info["author_id"], info["post_id"] = aid, pid
        if aid:
            info["bloggerlink"] = f"https://blog.naver.com/{aid}"

        info["bloggername"] = extract_bloggername(driver, fallback_id=aid)

        # 날짜
        raw_date = get_first_text(driver, ["span.se_publishDate", "span#post_date"])
        m = re.search(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", raw_date or "")
        if m:
            y, mo, d = m.groups()
            info["postdate"] = f"{int(y):04d}{int(mo):02d}{int(d):02d}"

        # 본문
        body, tags, imgs, vids = extract_body_tags_imgs_videos(driver)
        info["content_raw"] = body
        info["hashtags"] = "|".join(dict.fromkeys(tags))
        info["images"] = "|".join(imgs)
        info["videos"] = "|".join(vids)

        wait_engagement_widgets(driver)

        # 공감·댓글수
        info["like_count"] = get_int_by_selectors(driver, LIKE_SELECTORS)
        info["comment_count"] = get_int_by_selectors(driver, COMMENT_SELECTORS)

    except Exception as e:
        info["status"] = f"error:{type(e).__name__}"

    return info


# -------------------------
# 전체 Step2 단일 파일 실행
# -------------------------
def run_step2_single(links_csv_path, save_path):

    assert os.path.exists(links_csv_path), f"링크 CSV가 없음: {links_csv_path}"

    df = pd.read_csv(links_csv_path)
    df.columns = [c.lower() for c in df.columns]

    if "link" not in df.columns:
        raise RuntimeError("CSV에 'link' 컬럼이 없습니다.")

    df = df[df["link"].apply(is_post_url)].drop_duplicates(subset=["link"])
    seeds = df.fillna("").to_dict(orient="records")

    print(f"총 {len(seeds)}건 상세 크롤링 시작")

    driver = build_driver()
    out_rows = []

    try:
        for i, row in enumerate(seeds, 1):
            print(f"[{i}/{len(seeds)}] {row['link']}")
            out_rows.append(crawl_one(driver, row))
    finally:
        driver.quit()

    cols_out = [
        "platform",
        "administrative_dong",
        "title",
        "link",
        "bloggername",
        "bloggerlink",
        "postdate",
        "content_raw",
        "hashtags",
        "images",
        "videos",
        "like_count",
        "comment_count",
        "author_id",
        "post_id",
        "crawled_at",
        "status",
    ]

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    pd.DataFrame(out_rows)[cols_out].to_csv(save_path, index=False, encoding="utf-8-sig")
    print(f"✅ blog_posts_all 저장 완료 → {save_path}")


# -------------------------
# 직접 실행 예시
# -------------------------
def main():
    LINKS = "./data_html/2025/links/links_all_20251122.csv"
    OUT = "./data_html/2025/blog_posts/blog_posts_all_20251122.csv"
    run_step2_single(LINKS, OUT)

if __name__ == "__main__":
    main()
