FROM mcr.microsoft.com/playwright/python:v1.51.0-noble
WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# System libs for Chromium already ship in the Playwright base image.
# PYTHONPATH=/ makes the copied `app` package importable (server.py uses `from app...`).
ENV PYTHONPATH=/
COPY app/ .
# frontend/ is a sibling of app/ in the repo (server.py resolves it via
# ../frontend), so it's copied to the container's own root to preserve that
# relative layout.
COPY frontend/ /frontend
# The Playwright base image already ships a non-root user `pwuser` (uid 1000).
RUN mkdir -p /app/data && chown -R pwuser:pwuser /app /frontend
USER pwuser
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8501"]
