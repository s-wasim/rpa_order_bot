FROM mcr.microsoft.com/playwright/python:v1.51.0-noble
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# System libs for Chromium already ship in the Playwright base image.
# PYTHONPATH=/ makes the copied `app` package importable (main.py uses `from app...`).
ENV PYTHONPATH=/
COPY . .
# The Playwright base image already ships a non-root user `pwuser` (uid 1000).
RUN mkdir -p /app/data && chown -R pwuser:pwuser /app
USER pwuser
CMD ["streamlit", "run", "main.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
