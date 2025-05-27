# Use a base Python image
FROM python:3.11.2-alpine

# Install required packages
RUN apk update && \
    apk add --no-cache tzdata curl git

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
COPY docker/build/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# (Optional) Copy other local files if needed
# COPY app/ .

# Use the entrypoint script to check/copy config files and run the app
ENTRYPOINT ["/app/entrypoint.sh"]

