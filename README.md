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

---

내가 만들고 있는 파이프라인

```
BIGDATA_PIPELINE/
 ├─ crawl/                      # 크롤링 모듈
 │   ├─ step1_links_single.py
 │   ├─ step2_posts_single.py
 │   └─ __init__.py
 │
 ├─ scripts/                    # 실행 스크립트(파이프라인)
 │   ├─ run_pipeline.py         # 전체 파이프라인
 │   ├─ run_daily_single.py     # 크롤링만 실행
 │   ├─ silver_job.py           # silver layer 실행
 │   ├─ gold_job.py             # gold layer 실행(추가 예정)
 │   └─ processed_job.py        # processed layer 실행(추가 예정)
 │
 ├─ raw/                        # 크롤링 데이터 원본
 ├─ silver/                     # silver 결과
 ├─ gold/                       # gold 결과
 ├─ processed/                  # processed 결과
 ├─ models/                     # NLP 모델/토픽 모델 저장소
 ├─ logs/                       # 실행 로그
 ├─ requirements.txt
 └─ README.md
```