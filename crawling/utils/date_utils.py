# utils/date_utils.py
from datetime import datetime, timedelta

def get_yesterday():
    return datetime.now() - timedelta(days=1)

def fmt_day(dt):
    return dt.strftime("%Y%m%d")

def fmt_year(dt):
    return dt.year
