FROM python:3.11-slim

# Prevent Python from buffering logs (important for Railway logs)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps (needed for pandas, numpy, matplotlib sometimes)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Railway uses PORT env variable
ENV PORT=8080
EXPOSE 8080

# Run app
CMD ["python", "app.py"]