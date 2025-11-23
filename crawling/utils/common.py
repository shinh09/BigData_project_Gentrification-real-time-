# utils/common.py
import re
import random
import time
import os

def clean(s):
    return re.sub(r"\s+", " ", (s or "").strip())

def human_pause(a=1.0, b=2.0):
    time.sleep(random.uniform(a, b))

def sanitize_for_fname(s: str) -> str:
    s = s.strip().replace(" ", "_")
    s = re.sub(r"[^\w\-\.가-힣]+", "", s)
    return s

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
