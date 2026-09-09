FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Environment variables
ENV PORT=8080
ENV HOST=0.0.0.0
ENV ENVIRONMENT=production

EXPOSE 8080

# Run uvicorn bound to 0.0.0.0
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
