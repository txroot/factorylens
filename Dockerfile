# Use the official Python 3.9-slim image as the base image
FROM python:3.9-slim

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies for mysqlclient & wait-for-it
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      gcc \
      default-libmysqlclient-dev \
      python3-dev \
      curl \
    && rm -rf /var/lib/apt/lists/*

# Download wait-for-it script
ADD https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh /usr/local/bin/wait-for-it.sh
RUN chmod +x /usr/local/bin/wait-for-it.sh

# Set the working directory inside the container
WORKDIR /app

# Copy only requirements first (leverages Docker cache)
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# Expose the Flask port
EXPOSE 8082

# Default command: wait for DB, then start the app
CMD ["wait-for-it.sh", "db:3306", "--", "python", "app.py"]
