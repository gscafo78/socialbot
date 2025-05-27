#!/bin/bash

# Check and copy settings.json if missing
if [ ! -f "/app/settings.json" ]; then
    echo "settings.json not found. Copying from settings_example.json..."
    cp settings_example.json settings.json
fi

# Check and copy feeds.json if missing
if [ ! -f "/app/feeds.json" ]; then
    echo "feeds.json not found. Copying from feeds_example.json..."
    cp feeds_example.json feeds.json
fi

# Start the main application
python /app/socialbot.py