# config.py
import os
from datetime import datetime

# ----- 기본 설정 -----
QUERY = "신사동 명소"          # (행정동 + 명소 조합)
BASE_DIR = "./data_html"       # 전체 기본 저장 경로

# ----- 날짜 -----
def get_base_dir_for_year(keyword, year):
    return os.path.join(BASE_DIR, keyword.replace(" ", "_"), str(year))
