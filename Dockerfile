FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Telethon and cryptg
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port used by Uvicorn
ENV PORT=7860
EXPOSE 7860

# Run the FastAPI application
CMD ["python", "main.py"]