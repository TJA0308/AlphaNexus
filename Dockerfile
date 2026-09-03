# Container image for the AlphaNexus FastAPI backend.
# The Next.js frontend deploys separately (Vercel); this image serves the API.

FROM python:3.12-slim

# Keep Python output unbuffered and skip .pyc files for cleaner container logs.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first so this layer is cached unless requirements change.
# requirements-api.txt is the runtime subset: no Streamlit, plotting stack, or
# test runner, none of which the API imports.
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Copy the application code.
COPY alphanexus ./alphanexus
COPY api ./api

# Drop root. The API never writes outside its working directory, and the SQLite
# file lives under /app, so the app user owns everything it needs.
RUN useradd --create-home --shell /usr/sbin/nologin alphanexus \
    && chown -R alphanexus:alphanexus /app
USER alphanexus

EXPOSE 8000

# Honor $PORT if the host sets one (e.g. Render), otherwise default to 8000.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
