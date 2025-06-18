# Use an official Python image based on Debian Bookworm slim
FROM python:3.11.12-slim-bookworm

# Install required packages using apt (not apk, which is for Alpine)
RUN apt-get update && \
    apt-get install -y --no-install-recommends tzdata \
                                               curl \
                                               git \
                                               python3-dev \
                                               build-essential \
                                               libmariadb-dev \
                                               libmariadb-dev-compat \
                                               pkg-config && \
    rm -rf /var/lib/apt/lists/*

# Improve container logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8

# Set the working directory inside the container
WORKDIR /app

# Clone the repository directly into /app
RUN git clone https://github.com/gscafo78/socialbot.git /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entrypoint script into the container
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# (Optional) Copy other local files if needed
# COPY app/ .

# Use the entrypoint script to check/copy config files and run the app
ENTRYPOINT ["/app/entrypoint.sh"]

