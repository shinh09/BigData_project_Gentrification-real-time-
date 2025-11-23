# BigData_project_Gentrification-real-time-
[ITM] *** 실시간 *** SNS 감정분석과 젠트리피케이션 상관관계 분석 레포지토리

그런데 일단은 아직 `step1_links`, `step2_posts.py`, `run_daily` 만 사용.. (하루치)


```
mycrawler/
│
├── run_daily.py                # 크론이 실행하는 파일 (전날 날짜 크롤링)
│
├── config.py                   # 키워드, 경로 등 공통 설정
│
├── step1/                      # Step1: 링크 수집
│   ├── __init__.py
│   ├── crawler_step1.py        # 하루치 링크 수집 함수
│   └── selectors_step1.py      # Step1에서 사용하는 CSS selector 정리
│
├── step2/                      # Step2: 상세 크롤링
│   ├── __init__.py
│   ├── crawler_step2.py        # 하루치 상세 크롤링 함수
│   ├── extractor.py            # 본문/해시태그/이미지 등 추출 로직
│   └── selectors_step2.py      # Step2에서 사용하는 CSS selector
│
└── utils/
    ├── __init__.py
    ├── driver.py               # undetected-chromedriver 설정
    ├── date_utils.py           # 전날 날짜, 포맷팅 유틸
    └── common.py               # clean(), sanitize(), 파일 함수 등
```