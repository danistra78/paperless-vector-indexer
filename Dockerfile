FROM python:3.11-slim

WORKDIR /app

# Abhaengigkeiten installieren (separater Layer fuer Caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Quellcode
COPY main.py .

# One-Shot: einmaliger Lauf, danach beendet sich der Container
CMD ["python", "main.py"]
