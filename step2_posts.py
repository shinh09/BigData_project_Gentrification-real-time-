# -*- coding: utf-8 -*-
"""
STEP 2: STEP 1의 links_*.csv를 읽어 각 링크 상세 크롤링 → 최종 CSV

- PUBLIC API:
    run_step2(links_csv_path, save_path, administrative_dong)

- 컬럼:
    platform, administrative_dong, title, link, bloggername, bloggerlink,
    postdate, content_raw, hashtags, images, videos,
    like_count, comment_count, author_id, post_id, crawled_at, status
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

WAIT_SEC    = 30
PAUSE       = (1.0, 2.0)
PROBE_DEBUG = False   # True → 공감/댓글 셀렉터 탐지 로그 출력

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

# ---------------- 링크 정규화: "글 URL"만 허용 ----------------
POST_URL_RE = re.compile(
    r"^https?://(?:(?:m\.)?blog\.naver\.com/[^/]+/\d+|blog\.naver\.com/PostView\.naver\?.*?logNo=\d+)",
    re.IGNORECASE,
)

def is_post_url(u: str) -> bool:
    return bool(POST_URL_RE.match(u or ""))

# ---------------- 기본 유틸 ----------------
def goto_post_view(driver, url):
    """blog.naver.com → iframe#mainFrame src로 재진입 / m.blog.naver.com은 그대로"""
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

def extract_ids(u):
    """author_id(blogId) / post_id(logNo) 추출"""
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

def find_roots(driver):
    cands = [
        "div.se-main-container",
        "div.se_component_wrap",
        "#postViewArea",
        "#postListBody",
        "div#content-area",
        "div#viewTypeSelector",
        "div#_post_content",
        "div.se_textView",
        "article",
    ]
    els = []
    for css in cands:
        els.extend(driver.find_elements(By.CSS_SELECTOR, css))
    if els:
        return els
    return [driver.find_element(By.TAG_NAME, "body")]

def normalize_hashtag(t: str) -> str:
    t = (t or "").strip()
    if not t:
        return ""
    t = re.sub(r"\s+", "", t)
    if not t.startswith("#"):
        t = "#" + t
    return t

def extract_body_tags_imgs_videos(driver):
    """본문/해시태그/이미지/영상 추출 (+ tagList_* 케이스 커버)"""
    bodies, tags, imgs, vids = [], [], [], []

    for root in find_roots(driver):
        try:
            t = clean(root.text)
            if t:
                bodies.append(t)
        except Exception:
            pass

        for css in [
            "span.se_hashtag",
            "a.link_tag",
            "a[href*='query=%23']",
            ".se_component a",
            "i.pcol2b",
            "a.pcol2b",
            ".tag_area a",
            ".post_tag a",
        ]:
            try:
                for el in root.find_elements(By.CSS_SELECTOR, css):
                    raw = (el.get_attribute("innerText") or el.text or "").strip()
                    ht = normalize_hashtag(raw)
                    if ht and ht not in tags:
                        tags.append(ht)
            except Exception:
                pass

        for img in root.find_elements(By.CSS_SELECTOR, "img"):
            src = (
                img.get_attribute("src")
                or img.get_attribute("data-src")
                or img.get_attribute("data-lazy-src")
            )
            if src and src.startswith("http") and src not in imgs:
                imgs.append(src)

        for ifr in root.find_elements(By.CSS_SELECTOR, "iframe"):
            s = ifr.get_attribute("src") or ""
            if any(
                k in s
                for k in [
                    "youtube.com",
                    "tv.naver.com",
                    "serviceapi.rmcnmv.naver.com",
                    "player.vimeo.com",
                ]
            ):
                if s not in vids:
                    vids.append(s)

    try:
        for box in driver.find_elements(By.CSS_SELECTOR, "div[id^='tagList_']"):
            for el in box.find_elements(
                By.CSS_SELECTOR,
                "a.item.pcol2.itemTagfont._setTop span.ell, a.item span.ell, a span.ell",
            ):
                raw = (el.text or el.get_attribute("innerText") or "").strip()
                ht = normalize_hashtag(raw)
                if ht and ht not in tags:
                    tags.append(ht)
            for a in box.find_elements(
                By.CSS_SELECTOR, "a.item.pcol2.itemTagfont._setTop, a.item"
            ):
                raw = (a.text or a.get_attribute("innerText") or "").strip()
                ht = normalize_hashtag(raw)
                if ht and ht not in tags:
                    tags.append(ht)
    except Exception:
        pass

    body = max(bodies, key=len) if bodies else ""
    return body[:200000], tags, imgs, vids

def extract_bloggername(driver, fallback_author_id=""):
    sels = [
        "#nickNameArea",
        "strong#nickNameArea",
        "a.link.pcol2",
        "a.link_name",
        "a#gnb_name",
        "span.nick",
        "span.nick_name",
        "em.nick",
        "div.se_profile a",
        "div.bloger > a",
    ]
    for s in sels:
        try:
            el = driver.find_element(By.CSS_SELECTOR, s)
            txt = clean(el.text)
            if txt:
                return txt
        except Exception:
            continue
    return fallback_author_id or ""

def wait_engagement_widgets(driver, timeout=8):
    driver.execute_script("window.scrollBy(0, document.body.scrollHeight * 0.33);")
    time.sleep(0.6)
    driver.execute_script("window.scrollBy(0, document.body.scrollHeight * 0.66);")
    time.sleep(0.6)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: (
                d.find_elements(By.CSS_SELECTOR, "span.u_likeit_text._count.num")
                or d.find_elements(By.CSS_SELECTOR, "span.u_likeit_list_count._count")
                or d.find_elements(By.CSS_SELECTOR, "span.u_cnt._commentCount")
                or d.find_elements(
                    By.CSS_SELECTOR,
                    "[id*='CommentCount'], #commentCount, #naverCommentCount",
                )
                or d.find_elements(
                    By.CSS_SELECTOR, "#floating_bottom_commentCount"
                )
            )
        )
    except Exception:
        pass

def _to_int_or_none(s):
    m = re.search(r"([\d,]+)", s or "")
    return int(m.group(1).replace(",", "")) if m else None

def get_int_by_selectors(driver, selectors):
    for css in selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, css)
            for el in els:
                val = _to_int_or_none(el.text)
                if val is not None:
                    return val
        except Exception:
            continue
    return None

def get_count_by_keyword_fallback(driver, keyword_list=("공감", "댓글")):
    try:
        nodes = driver.find_elements(By.XPATH, "//*")
        for node in nodes:
            txt = (node.text or "").strip()
            if not txt:
                continue
            if any(k in txt for k in keyword_list):
                n = _to_int_or_none(txt)
                if n is not None:
                    return n
                try:
                    for s in node.find_elements(By.XPATH, "./following-sibling::*")[:3]:
                        n2 = _to_int_or_none(s.text)
                        if n2 is not None:
                            return n2
                except Exception:
                    pass
    except Exception:
        pass
    return None

LIKE_SELECTORS = [
    "span.u_likeit_text._count.num",
    "span.u_likeit_list_count._count",
    "button.u_likeit_list_btn span.u_cnt",
    "span._count._sympathyCount",
    "em.u_cnt._count",
]

COMMENT_SELECTORS = [
    "span.u_cnt._commentCount",
    "a#CommentCount",
    "a#naverCommentCount",
    "#commentCount",
    "span#commentCount",
    "a[href*='comment'] span.num",
    "span.u_cbox_count",
    "em.u_cbox_count",
    "#floating_bottom_commentCount",
    "em#floating_bottom_commentCount",
]

def probe_counts_debug(driver):
    print("== Like probes ==")
    for s in LIKE_SELECTORS:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, s)
            print(f"{s} -> {len(els)}", [e.text for e in els[:3]])
        except Exception as e:
            print(f"{s} -> err:{e.__class__.__name__}")
    print("== Comment probes ==")
    for s in COMMENT_SELECTORS:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, s)
            print(f"{s} -> {len(els)}", [e.text for e in els[:3]])
        except Exception as e:
            print(f"{s} -> err:{e.__class__.__name__}")

# ---------- “댓글 0개 UI” 감지 ----------
ZERO_COMMENT_HINT_SELECTORS = [
    "#comment_zero_label",        # <em id="comment_zero_label">쓰기</em>
    "button#commentOpen",
    "a#commentOpen",
    "div.comment_area_empty",     # 빈 댓글 영역
    "div.u_cbox_wrap",            # CBOX 로딩(카운트 미표시 상황 포함)
]

ZERO_COMMENT_TEXTS = [
    "댓글 쓰기",
    "댓글쓰기",
    "댓글 작성",
    "첫 댓글을 남겨보세요",
    "댓글을 입력해 주세요",
]

def has_zero_comment_ui(driver) -> bool:
    try:
        for css in ZERO_COMMENT_HINT_SELECTORS:
            if driver.find_elements(By.CSS_SELECTOR, css):
                return True

        nodes = driver.find_elements(
            By.XPATH, "//*[not(self::script) and not(self::style)]"
        )
        for nd in nodes[:1500]:
            txt = (nd.text or "").strip()
            if txt and any(kw in txt for kw in ZERO_COMMENT_TEXTS):
                return True

        for css in ["#commentCount", "em._commentCount", "a#CommentCount"]:
            for el in driver.find_elements(By.CSS_SELECTOR, css):
                raw = (el.text or "").strip()
                if raw == "":
                    try:
                        sibs = el.find_elements(By.XPATH, "../*")
                        for s in sibs:
                            st = (s.text or "").strip()
                            if any(kw in st for kw in ZERO_COMMENT_TEXTS):
                                return True
                    except Exception:
                        pass
        return False
    except Exception:
        return False

# ---------------- 한 건 크롤링 ----------------
def crawl_one(driver, row, administrative_dong: str):
    info = {
        "platform": "blog",
        "administrative_dong": administrative_dong,
        "title": row.get("title", ""),
        "link": row["link"],
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
        "crawled_at": datetime.utcnow()
        .replace(tzinfo=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "status": "ok",
    }

    try:
        if not is_post_url(info["link"]):
            info["status"] = "skip_non_post_url"
            return info

        if not goto_post_view(driver, info["link"]):
            info["status"] = "failed_goto_view"
            return info

        aid, pid = extract_ids(driver.current_url)
        info["author_id"], info["post_id"] = aid, pid
        if aid:
            info["bloggerlink"] = f"https://blog.naver.com/{aid}"

        info["bloggername"] = extract_bloggername(
            driver, fallback_author_id=aid
        )

        raw_date = get_first_text(
            driver,
            [
                "span.se_publishDate",
                "span.se_date",
                "span#post_date",
                "p.date",
                "span.se_publishDate._postAddDate",
            ],
        )
        m = re.search(
            r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", raw_date or ""
        )
        if m:
            y, mo, d = m.groups()
            info["postdate"] = f"{int(y):04d}{int(mo):02d}{int(d):02d}"

        body, tags, imgs, vids = extract_body_tags_imgs_videos(driver)
        info["content_raw"] = body
        info["hashtags"] = "|".join(dict.fromkeys(tags))
        info["images"] = "|".join(imgs)
        info["videos"] = "|".join(vids)

        wait_engagement_widgets(driver, timeout=8)

        info["like_count"] = get_int_by_selectors(driver, LIKE_SELECTORS) or get_count_by_keyword_fallback(
            driver, ("공감",)
        )

        cmt_num = get_int_by_selectors(driver, COMMENT_SELECTORS)
        if cmt_num is None:
            cmt_num = get_count_by_keyword_fallback(driver, ("댓글",))
        if cmt_num is None and has_zero_comment_ui(driver):
            cmt_num = 0
        info["comment_count"] = cmt_num

        if PROBE_DEBUG and (
            info["like_count"] is None or info["comment_count"] is None
        ):
            probe_counts_debug(driver)
    except Exception as e:
        info["status"] = f"error:{type(e).__name__}"

    return info

# ---------------- 메인 로직 (하나의 links CSV → blog_posts CSV) ----------------
def run_step2(links_csv_path: str, save_path: str, administrative_dong: str):
    assert os.path.exists(links_csv_path), f"링크 CSV가 없음: {links_csv_path}"
    df = pd.read_csv(links_csv_path)

    cols = [c.lower() for c in df.columns]
    df.columns = cols
    if "link" not in df.columns:
        raise RuntimeError("CSV에 'link' 컬럼이 없습니다.")
    if "title" not in df.columns:
        df["title"] = ""

    before = len(df)
    df = df[df["link"].apply(is_post_url)].copy()
    df.drop_duplicates(subset=["link"], inplace=True)
    after = len(df)
    print(f"🔗 입력 링크(원본): {before}건 → 글 URL만: {after}건")

    seeds = df.fillna("").to_dict(orient="records")

    driver = build_driver()
    out_rows = []
    try:
        for i, r in enumerate(seeds, 1):
            print(f"  [{i:03d}/{len(seeds):03d}] {r['link']}")
            out_rows.append(crawl_one(driver, r, administrative_dong))
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
    pd.DataFrame(out_rows)[cols_out].to_csv(
        save_path, index=False, encoding="utf-8-sig"
    )
    print(f"✅ 상세 CSV 저장 → {save_path}")

# ---------------- 직접 실행용 예시 ----------------
def main():
    # 직접 테스트할 때만 경로 수정해서 사용
    LINKS_CSV = "./data_html/한남동_명소/2025/links/links_한남동_명소_20251122.csv"
    SAVE_PATH = "./data_html/한남동_명소/2025/blog_posts/blog_posts_한남동_명소_20251122.csv"
    ADMIN_DONG = "한남동"

    run_step2(LINKS_CSV, SAVE_PATH, ADMIN_DONG)

if __name__ == "__main__":
    main()
