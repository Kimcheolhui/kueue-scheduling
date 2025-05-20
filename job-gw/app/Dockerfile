FROM python:3.11-slim
WORKDIR /app
COPY app.py /app/
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    kubernetes \
    pyyaml \
    requests \
    python-multipart      # ← 추가
EXPOSE 8080
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
