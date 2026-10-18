FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose FastAPI (8000) and Streamlit (8501)
EXPOSE 8000 8501

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

