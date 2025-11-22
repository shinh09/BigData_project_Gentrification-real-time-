# step2/extractor.py
from bs4 import BeautifulSoup

def extract_body(driver):
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    # 최대 텍스트 블록만 가져오기
    texts = [t.get_text(" ", strip=True) for t in soup.find_all(["p", "div", "span"])]
    if not texts:
        return ""
    return max(texts, key=len)[:200000]


def extract_tags(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    tags = []
    for el in soup.select("span.se_hashtag, a.link_tag"):
        raw = el.get_text(strip=True)
        if raw:
            if not raw.startswith("#"):
                raw = "#" + raw
            tags.append(raw)
    return "|".join(tags)


def extract_images(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    imgs = []
    for img in soup.select("img"):
        src = img.get("src")
        if src and src.startswith("http"):
            imgs.append(src)
    return "|".join(imgs)


def extract_videos(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    vids = []
    for ifr in soup.select("iframe"):
        s = ifr.get("src") or ""
        if any(k in s for k in ["youtube", "tv.naver", "vimeo"]):
            vids.append(s)
    return "|".join(vids)
