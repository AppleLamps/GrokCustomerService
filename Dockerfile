# Use a slim Python image for smaller build size
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg libsndfile1 curl build-essential && \
    apt-get clean

# Set working directory
WORKDIR /app

# Copy app code
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Expose the port your app runs on
EXPOSE 8000

# Launch the app using uvicorn (for FastAPI + WebSockets support)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
