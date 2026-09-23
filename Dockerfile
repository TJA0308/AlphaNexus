# Container image for the AlphaNexus FastAPI backend.
# The Next.js frontend deploys separately (Vercel); this image serves the API.

FROM python:3.14-slim

# Keep Python output unbuffered and skip .pyc files for cleaner container logs.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first so this layer is cached unless requirements change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY alphanexus ./alphanexus
COPY api ./api

EXPOSE 8000

# Honor $PORT if the host sets one (e.g. Render), otherwise default to 8000.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
