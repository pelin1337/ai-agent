# Base image for Python
FROM python:slim

# Install dependencies
WORKDIR /app
COPY requirements.txt /app
RUN pip install -r requirements.txt

# Copy application code
COPY app/ /app

EXPOSE 8000

# Start Celery worker and FastAPI server
CMD ["sh", "-c", "celery -A tasks worker --loglevel=info & uvicorn main:app --host 0.0.0.0 --port 8000"]