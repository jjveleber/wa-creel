# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .
COPY index.py .

# Create data directory
RUN mkdir -p wdfw_creel_data

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

# Run the application
CMD ["python", "index.py"]
