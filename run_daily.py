# -*- coding: utf-8 -*-
"""
run_daily.py

- 전날 기준으로:
  1) STEP1: 모든 KEYWORDS에 대해 links 수집
  2) STEP2: 생성된 links CSV들에 대해 상세 본문 수집
"""

import os
import glob
from datetime import datetime, timedelta

from step1_links import run_step1, KEYWORDS
from step2_posts import run_step2

def main():
    today = datetime.now()
    target_day = today - timedelta(days=1)
    day_key = target_day.strftime("%Y%m%d")
    year_str = target_day.strftime("%Y")

    print(f"🚀 전체 파이프라인 시작 — 대상일: {day_key}")

    # ----------------------
    # STEP 1 실행 (links 수집)
    # ----------------------
    print("▶ STEP 1: 전날 하루치 링크 수집 시작")
    run_step1(target_day=target_day)
    print("✅ STEP 1 완료\n")

    # ----------------------
    # STEP 2 실행 (상세 본문 수집)
    # ----------------------
    print("▶ STEP 2: 전날 하루치 상세 본문 수집 시작")

    base_dir = "./data_html"

    # KEYWORDS 기준으로 각 동네별 links 파일 경로를 구성해서 호출
    for _, dong in KEYWORDS:
        dong_slug = f"{dong}_명소"
        links_csv = os.path.join(
            base_dir,
            dong_slug,
            year_str,
            "links",
            f"links_{dong_slug}_{day_key}.csv",
        )

        if not os.path.exists(links_csv):
            print(f"⚠️ [{dong_slug}] links CSV 없음, 건너뜀: {links_csv}")
            continue

        save_dir = os.path.join(base_dir, dong_slug, year_str, "blog_posts")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(
            save_dir,
            f"blog_posts_{dong_slug}_{day_key}.csv",
        )

        print(f"👉 STEP2 실행: {links_csv} → {save_path}")
        run_step2(links_csv, save_path, administrative_dong=dong)

    print("🎉 모든 KEYWORDS 파이프라인 완료!")

if __name__ == "__main__":
    main()
