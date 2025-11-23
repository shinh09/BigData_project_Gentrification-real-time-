FROM python:3.10

# 기본 pip 업그레이드
RUN pip install --upgrade pip

# torch CPU 버전
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# NLP 모델 패키지
RUN pip install transformers sentence-transformers bertopic sklearn pandas fugashi ipadic

WORKDIR /models

CMD ["bash"]
