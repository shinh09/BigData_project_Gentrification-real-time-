# step2/crawler_step2.py

import os
import pandas as pd
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urljoin
from selenium.webdriver.common.by import By

from utils.driver import build_driver
from utils.common import sanitize_for_fname, ensure_dir
from step2.selectors_step2 import LIKE_SELECTORS, COMMENT_SELECTORS
from step2.extractor import extract_body, extract_tags, extract_images, extract_videos


def is_post_url(url):
    return (
        "blog.naver.com" in url or
        "m.blog.naver.com" in url
    ) and any(s in url for s in ["PostView.naver", "/"])


def goto_post_view(driver, url):
    driver.get(url)
    return True


def extract_ids(url):
    p = urlparse(url)
    if "m.blog.naver.com" in p.netloc:
        parts = p.path.split("/")
        if len(parts) >= 3:
            return parts[1], parts[2]
    q = parse_qs(p.query)
    return (q.get("blogId", [""])[0], q.get("logNo", [""])[0])


def crawl_one(driver, row, keyword):
    info = {
        "platform": "blog",
        "administrative_dong": keyword.split()[0],
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
        "crawled_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "status": "ok",
    }

    try:
        goto_post_view(driver, row["link"])

        aid, pid = extract_ids(driver.current_url)
        info["author_id"] = aid
        info["post_id"] = pid
        info["bloggerlink"] = f"https://blog.naver.com/{aid}"

        # 본문 / 태그 / 이미지 / 영상 추출
        info["content_raw"] = extract_body(driver)
        info["hashtags"] = extract_tags(driver)
        info["images"] = extract_images(driver)
        info["videos"] = extract_videos(driver)

        # 공감/댓글
        for css in LIKE_SELECTORS:
            els = driver.find_elements(By.CSS_SELECTOR, css)
            if els:
                try:
                    info["like_count"] = int(els[0].text.replace(",", ""))
                except:
                    pass

        for css in COMMENT_SELECTORS:
            els = driver.find_elements(By.CSS_SELECTOR, css)
            if els:
                try:
                    info["comment_count"] = int(els[0].text.replace(",", ""))
                except:
                    pass

    except Exception as e:
        info["status"] = f"error:{type(e).__name__}"

    return info


def run_step2_for_day(keyword, link_csv_path, save_dir, day):
    ensure_dir(save_dir)

    df = pd.read_csv(link_csv_path)
    df.columns = [c.lower() for c in df.columns]
    df = df[df["link"].apply(is_post_url)]
    seeds = df.fillna("").to_dict(orient="records")

    driver = build_driver()
    out_rows = []

    try:
        for i, r in enumerate(seeds, 1):
            print(f" {i}/{len(seeds)} → {r['link']}")
            out_rows.append(crawl_one(driver, r, keyword))
    finally:
        driver.quit()

    fname = f"blog_{sanitize_for_fname(keyword)}_{day.strftime('%Y%m%d')}.csv"
    save_path = os.path.join(save_dir, fname)

    pd.DataFrame(out_rows).to_csv(save_path, index=False, encoding="utf-8-sig")

    print(f"✅ Step2 저장 완료 → {save_path}")
    return save_path
