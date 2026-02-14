FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app/src

COPY requirements.txt README.md ./
COPY src ./src
COPY heart_disease_uci.csv ./heart_disease_uci.csv

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "twin.cli", "run-baseline"]
