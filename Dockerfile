# ParcelFlow image: runs both the pipeline CLI and the Streamlit dashboard.
FROM python:3.11-slim

# Keep Python output unbuffered and skip .pyc files in the container.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so Docker layer caching skips reinstalls when only
# source code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project.
COPY . .

# Make the src layout importable.
ENV PYTHONPATH=/app/src

EXPOSE 8501

# Default: launch the dashboard. Override the command to run the pipeline, e.g.
#   docker compose run --rm pipeline python pipeline.py backfill
CMD ["streamlit", "run", "dashboard/app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true"]
