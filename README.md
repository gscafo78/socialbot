# socialbot

**socialbot** is an automated Python tool for sharing RSS feed updates to multiple social platforms, including Telegram, Bluesky, and LinkedIn.  
It supports AI-generated comments (via OpenAI), flexible scheduling (cron), mute periods, and is ready for Docker deployment.

---

## Features

- **RSS Feed Monitoring**: Fetches and processes new items from multiple RSS feeds.
- **Multi-platform Publishing**: Supports Telegram, Bluesky, and LinkedIn (easily extendable).
- **AI Comments**: Generates comments for posts using OpenAI GPT models.
- **Mute Time**: Avoids posting during configured hours.
- **Flexible Scheduling**: Uses cron syntax for update intervals.
- **Logging**: Configurable log level and file.
- **Docker-ready**: Includes Dockerfile and docker-compose for easy deployment.

---

## Requirements

- Python 3.11+
- Docker (optional, for containerized deployment)
- Telegram Bot Token and Chat ID (for Telegram publishing)
- Bluesky credentials (for Bluesky publishing)
- LinkedIn access token and URN (for LinkedIn publishing)
- OpenAI API Key (for AI comments, optional)

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/gscafo78/socialbot.git
cd socialbot
```

### 2. Configure

Edit `settings.json` and `feeds.json` to match your needs.  
If these files do not exist, they will be created from the example files on first run.

- **settings.json**: General configuration, logging, scheduling, social credentials.
- **feeds.json**: List of RSS feeds to monitor.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run with Python

```bash
python socialbot.py
```

### 5. Run with Docker

Build and run with Docker Compose (recommended):

```bash
cd docker
docker-compose up --build
```

This will bind your `settings.json` and `feeds.json` from the host to the container.

---

## Configuration

- **settings.json**:
  - `log_level`: Logging level (DEBUG, INFO, etc.)
  - `log_file`: Path to log file
  - `feeds_file`: Path to feeds file
  - `days_of_retention`: How many days to keep old feeds
  - `cron`: Cron expression for scheduling
  - `mute`: Time range to mute posting
  - `telegram`: Telegram bot credentials
  - `bluesky`: Bluesky account credentials
  - `linkedin`: LinkedIn account credentials

- **feeds.json**:
  - List of feeds, each with RSS URL and optional social/bot configuration.

---

## Extending

You can add new social platforms by implementing a new sender class in `senders/` and updating the `send_feed_to_<platform>` function in `socialbot.py`.

---

## Troubleshooting

- **Import Errors**:  
  If you encounter `ModuleNotFoundError` for local modules, ensure you are running scripts from the project root or adjust your `PYTHONPATH` accordingly.  
  For development, prefer running scripts as modules, e.g.:
  ```bash
  python -m senders.senders
  ```
- **Docker Issues**:  
  Make sure your config files are correctly mounted and paths are valid inside the container.

---

## License

MIT License

## Author

[github.com/gscafo78](https://github.com/gscafo78)