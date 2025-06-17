#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script to manage AI configuration and social account data (Telegram, Bluesky, LinkedIn)
in MariaDB, with table initialization and interactive data entry.
"""

import argparse
import sys
import getpass
import os
from cryptography.fernet import Fernet
import logging
import json
import datetime

import mariadb
import pwinput

__version__ = "1.0.1"


class DatabaseManager:
    """
    Class to manage connection, table creation, and data insertion
    for a MariaDB database.
    """

    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306, secret_key: str = None, logger=None):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.conn = None  # tipo: mariadb.Connection
        self.cur = None   # tipo: mariadb.Cursor
        # Setup Fernet
        key = secret_key or os.environ.get('SOCIALBOT_SECRET_KEY')
        if not key:
            raise ValueError("A secret key must be provided via argument or SOCIALBOT_SECRET_KEY env variable.")
        if len(key) != 44:
            raise ValueError("Fernet key must be 32 url-safe base64-encoded bytes (44 chars). Generate with Fernet.generate_key().")
        self.fernet = Fernet(key)
        self.logger = logger or logging.getLogger("socialbot.initdb")

    def _encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        return self.fernet.decrypt(value.encode()).decode()

    def connect(self):
        """Open connection to MariaDB database."""
        try:
            self.conn = mariadb.connect(
                host=self.host,
                user=self.user,
                port=self.port,
                password=self.password,
                database=self.database
            )
            self.cur = self.conn.cursor()
            self.logger.info(f"Connected to DB '{self.database}' on {self.host}:{self.port}")
        except mariadb.Error as e:
            self.logger.error(f"Failed to connect to MariaDB: {e}")
            sys.exit(1)

    def close(self):
        """Close the database connection."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        self.logger.info("Database connection closed.")

    def create_tables(self):
        """Create all tables (if not exist) for AI config and social accounts, including the Language table."""
        ddl = [
            # Language table
            """
            CREATE TABLE IF NOT EXISTS language (
                code VARCHAR(5) PRIMARY KEY,
                name VARCHAR(50) NOT NULL
            );
            """,
            # Table for AI configuration
            """
            CREATE TABLE IF NOT EXISTS ai_config (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ai_key TEXT NOT NULL,
                ai_base_url VARCHAR(255) DEFAULT 'https://api.openai.com/v1/',
                ai_model VARCHAR(255) NOT NULL,
                ai_comment_max_chars INT NOT NULL,
                ai_comment_language VARCHAR(10) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ai_comment_language) REFERENCES language(code)
            );
            """,
            # Table for Telegram accounts
            """
            CREATE TABLE IF NOT EXISTS telegram_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                token VARCHAR(255) NOT NULL,
                chat_id VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # Table for Bluesky accounts
            """
            CREATE TABLE IF NOT EXISTS bluesky_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                handle VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                service VARCHAR(255) NOT NULL,
                mute BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # Table for LinkedIn accounts
            """
            CREATE TABLE IF NOT EXISTS linkedin_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                urn VARCHAR(255) NOT NULL,
                access_token TEXT NOT NULL,
                mute BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # Table for Feeds
            """
            CREATE TABLE IF NOT EXISTS feeds (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rss VARCHAR(255) NOT NULL,
                ai BOOLEAN NOT NULL DEFAULT FALSE
            );
            """,
            # Table for Telegram Feed links
            """
            CREATE TABLE IF NOT EXISTS feed_telegram_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                feed_id INT NOT NULL,
                telegram_account_id INT NOT NULL,
                FOREIGN KEY (feed_id) REFERENCES feeds(id),
                FOREIGN KEY (telegram_account_id) REFERENCES telegram_accounts(id)
            );
            """,
            # Table for LinkedIn Feed links
            """
            CREATE TABLE IF NOT EXISTS feed_linkedin_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                feed_id INT NOT NULL,
                linkedin_account_id INT NOT NULL,
                FOREIGN KEY (feed_id) REFERENCES feeds(id),
                FOREIGN KEY (linkedin_account_id) REFERENCES linkedin_accounts(id)
            );
            """,
            # Table for Bluesky Feed links
            """
            CREATE TABLE IF NOT EXISTS feed_bluesky_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                feed_id INT NOT NULL,
                bluesky_account_id INT NOT NULL,
                FOREIGN KEY (feed_id) REFERENCES feeds(id),
                FOREIGN KEY (bluesky_account_id) REFERENCES bluesky_accounts(id)
            );
            """,
            # Table for execution logs
            """
            CREATE TABLE IF NOT EXISTS execution_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                feed_id INT NOT NULL,
                link VARCHAR(255) NOT NULL,
                datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT,
                title VARCHAR(255) NOT NULL,
                ai_comment TEXT,
                category TEXT,
                short_link VARCHAR(255),
                img_link VARCHAR(255),
                FOREIGN KEY (feed_id) REFERENCES feeds(id)
            );
            """
        ]

        for stmt in ddl:
            try:
                self.cur.execute(stmt)
            except mariadb.Error as e:
                self.logger.error(f"Table creation failed: {e}")
                self.conn.rollback()
                sys.exit(1)

        # Preload language values
        languages = [
            ("IT", "Italian"),
            ("EN", "English"),
            ("ES", "Spanish"),
            ("FR", "French"),
            ("DE", "German"),
            ("PT", "Portuguese"),
            ("RU", "Russian"),
            ("ZH", "Chinese"),
            ("JA", "Japanese"),
            ("AR", "Arabic"),
            ("NL", "Dutch"),
            ("TR", "Turkish"),
            ("PL", "Polish"),
            ("UK", "Ukrainian"),
            ("HI", "Hindi"),
            ("KO", "Korean"),
            ("SV", "Swedish"),
            ("NO", "Norwegian"),
            ("FI", "Finnish"),
            ("DA", "Danish"),
            ("CS", "Czech"),
            ("EL", "Greek"),
            ("RO", "Romanian"),
            ("HU", "Hungarian"),
            ("BG", "Bulgarian"),
            ("HE", "Hebrew"),
        ]
        try:
            for code, name in languages:
                self.cur.execute(
                    "INSERT IGNORE INTO language (code, name) VALUES (%s, %s)", (code, name)
                )
            self.conn.commit()
        except mariadb.Error as e:
            self.logger.error(f"Failed to insert language values: {e}")
            self.conn.rollback()
            sys.exit(1)

        self.logger.info("Table initialization completed.")

    def insert_ai_config_interactive(self):
        """Insert a record into ai_config interactively, showing and validating available languages."""
        print("== Insert AI Config ==")
        ai_key = pwinput.pwinput(prompt="Enter your AI key: ", mask="*")
        ai_base_url = input("ai_base_url (default: https://api.openai.com/v1/): ").strip() or "https://api.openai.com/v1/"
        ai_model = input("ai_model: ").strip()
        ai_comment_max_chars = int(input("ai_comment_max_chars: ").strip())
        # Show available languages
        self.cur.execute("SELECT code, name FROM language ORDER BY code")
        languages = self.cur.fetchall()
        print("Available languages:")
        for code, name in languages:
            print(f"  {code}: {name}")
        valid_codes = {code for code, _ in languages}
        while True:
            ai_comment_language = input("ai_comment_language (choose code from above): ").strip().upper()
            if ai_comment_language in valid_codes:
                break
            print("[ERROR] Invalid language code. Please choose from the list above.")
        stmt = """
            INSERT INTO ai_config (ai_key, ai_base_url ,ai_model, ai_comment_max_chars, ai_comment_language)
            VALUES (%s, %s, %s, %s, %s)
        """
        try:
            self.cur.execute(stmt, (self._encrypt(ai_key), ai_base_url, ai_model, ai_comment_max_chars, ai_comment_language))
            self.conn.commit()
            self.logger.info("AI Config record inserted.")
        except mariadb.Error as e:
            self.logger.error(f"Failed to insert AI Config: {e}")
            self.conn.rollback()


    def insert_telegram_interactive(self):
        """Insert a record into telegram_accounts interactively."""
        print("== Insert Telegram Account ==")
        name = input("name: ").strip()
        token = pwinput.pwinput(prompt="Enter your token: ", mask="*")
        chat_id = input("chat_id: ").strip()
        # Cifra il token
        token_enc = self._encrypt(token)
        stmt = """
            INSERT INTO telegram_accounts (name, token, chat_id)
            VALUES (%s, %s, %s)
        """
        try:
            self.cur.execute(stmt, (name, token_enc, chat_id))
            self.conn.commit()
            self.logger.info("Telegram record inserted.")
        except mariadb.Error as e:
            self.logger.error(f"Failed to insert Telegram: {e}")
            self.conn.rollback()

    def insert_bluesky_interactive(self):
        """Insert a record into bluesky_accounts interactively."""
        print("== Insert Bluesky Account ==")
        name = input("name: ").strip()
        handle = input("handle: ").strip()
        password = pwinput.pwinput(prompt="Enter your password: ", mask="*")
        service = input("service: ").strip()
        mute_input = input("mute (y/N): ").strip().lower()
        mute = True if mute_input in ("y", "yes") else False
        # Cifra la password
        password_enc = self._encrypt(password)
        stmt = """
            INSERT INTO bluesky_accounts (name, handle, password, service, mute)
            VALUES (%s, %s, %s, %s, %s)
        """
        try:
            self.cur.execute(stmt, (name, handle, password_enc, service, mute))
            self.conn.commit()
            self.logger.info("Bluesky record inserted.")
        except mariadb.Error as e:
            self.logger.error(f"Failed to insert Bluesky: {e}")
            self.conn.rollback()

    def insert_linkedin_interactive(self):
        """Insert a record into linkedin_accounts interactively."""
        print("== Insert LinkedIn Account ==")
        name = input("name: ").strip()
        urn = input("urn: ").strip()
        access_token = pwinput.pwinput(prompt="Enter your Token: ", mask="*")
        mute_input = input("mute (y/N): ").strip().lower()
        mute = True if mute_input in ("y", "yes") else False
        # Cifra il token
        access_token_enc = self._encrypt(access_token)
        stmt = """
            INSERT INTO linkedin_accounts (name, urn, access_token, mute)
            VALUES (%s, %s, %s, %s)
        """
        try:
            self.cur.execute(stmt, (name, urn, access_token_enc, mute))
            self.conn.commit()
            self.logger.info("LinkedIn record inserted.")
        except mariadb.Error as e:
            self.logger.error(f"Failed to insert LinkedIn: {e}")
            self.conn.rollback()

    def insert_feed_interactive(self):
        """
        Interactively insert a new feed and link it to Telegram, LinkedIn, and Bluesky accounts.
        """
        print("== Insert New Feed ==")
        rss = input("Feed RSS URL: ").strip()
        ai_input = input("Enable AI? (y/N): ").strip().lower()
        ai = True if ai_input in ("y", "yes") else False

        # Insert feed
        stmt = "INSERT INTO feeds (rss, ai) VALUES (%s, %s)"
        try:
            self.cur.execute(stmt, (rss, ai))
            self.conn.commit()
            feed_id = self.cur.lastrowid
            self.logger.info(f"Feed inserted with id {feed_id}.")
        except Exception as e:
            self.logger.error(f"Failed to insert feed: {e}")
            self.conn.rollback()
            return

        # Link Telegram accounts
        self.cur.execute("SELECT id, name FROM telegram_accounts")
        telegram_accounts = self.cur.fetchall()
        if telegram_accounts:
            print("Available Telegram accounts:")
            for acc in telegram_accounts:
                print(f"  {acc[0]}: {acc[1]}")
            tg_ids = input("Enter Telegram account IDs to link (comma separated, blank to skip): ").strip()
            if tg_ids:
                for tg_id in tg_ids.split(","):
                    tg_id = tg_id.strip()
                    if tg_id.isdigit():
                        try:
                            self.cur.execute(
                                "INSERT INTO feed_telegram_accounts (feed_id, telegram_account_id) VALUES (%s, %s)",
                                (feed_id, int(tg_id))
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to link Telegram account {tg_id}: {e}")
                self.conn.commit()

        # Link LinkedIn accounts
        self.cur.execute("SELECT id, name FROM linkedin_accounts")
        linkedin_accounts = self.cur.fetchall()
        if linkedin_accounts:
            print("Available LinkedIn accounts:")
            for acc in linkedin_accounts:
                print(f"  {acc[0]}: {acc[1]}")
            li_ids = input("Enter LinkedIn account IDs to link (comma separated, blank to skip): ").strip()
            if li_ids:
                for li_id in li_ids.split(","):
                    li_id = li_id.strip()
                    if li_id.isdigit():
                        try:
                            self.cur.execute(
                                "INSERT INTO feed_linkedin_accounts (feed_id, linkedin_account_id) VALUES (%s, %s)",
                                (feed_id, int(li_id))
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to link LinkedIn account {li_id}: {e}")
                self.conn.commit()

        # Link Bluesky accounts
        self.cur.execute("SELECT id, name FROM bluesky_accounts")
        bluesky_accounts = self.cur.fetchall()
        if bluesky_accounts:
            print("Available Bluesky accounts:")
            for acc in bluesky_accounts:
                print(f"  {acc[0]}: {acc[1]}")
            bs_ids = input("Enter Bluesky account IDs to link (comma separated, blank to skip): ").strip()
            if bs_ids:
                for bs_id in bs_ids.split(","):
                    bs_id = bs_id.strip()
                    if bs_id.isdigit():
                        try:
                            self.cur.execute(
                                "INSERT INTO feed_bluesky_accounts (feed_id, bluesky_account_id) VALUES (%s, %s)",
                                (feed_id, int(bs_id))
                            )
                        except Exception as e:
                            self.logger.error(f"Failed to link Bluesky account {bs_id}: {e}")
                self.conn.commit()

        self.logger.info("Feed and account links saved.")

    def drop_all_tables(self):
        """
        Drop all tables related to the socialbot database.
        WARNING: This will delete ALL data!
        """
        tables = [
            "feed_bluesky_accounts",
            "feed_linkedin_accounts",
            "feed_telegram_accounts",
            "bluesky_accounts",
            "linkedin_accounts",
            "telegram_accounts",
            "execution_logs",
            "ai_config",            
            "feeds",
            "language"
        ]
        for table in tables:
            try:
                self.cur.execute(f"DROP TABLE IF EXISTS {table}")
                self.logger.info(f"Dropped table: {table}")
            except Exception as e:
                self.logger.error(f"Could not drop table {table}: {e}")
        self.conn.commit()
        self.logger.info("All tables dropped.")

    def generate_feed_list(self):
        """
        Extract feeds from the database and generate a list of dicts with the required structure.
        Requires an open connection.
        """
        feeds = []
        self.cur.execute("SELECT id, rss, ai FROM feeds")
        for feed_id, rss, ai in self.cur.fetchall():
            entry = {"rss": rss, "ai": bool(ai)}
            # Bluesky bots
            self.cur.execute("""
                SELECT b.name FROM feed_bluesky_accounts fba
                JOIN bluesky_accounts b ON fba.bluesky_account_id = b.id
                WHERE fba.feed_id = %s
            """, (feed_id,))
            bluesky_bots = [row[0] for row in self.cur.fetchall()]
            if bluesky_bots:
                entry["bluesky"] = {"bots": bluesky_bots}
            # LinkedIn bots
            self.cur.execute("""
                SELECT l.name FROM feed_linkedin_accounts fla
                JOIN linkedin_accounts l ON fla.linkedin_account_id = l.id
                WHERE fla.feed_id = %s
            """, (feed_id,))
            linkedin_bots = [row[0] for row in self.cur.fetchall()]
            if linkedin_bots:
                entry["linkedin"] = {"bots": linkedin_bots}
            # Telegram bots (optional)
            self.cur.execute("""
                SELECT t.name FROM feed_telegram_accounts fta
                JOIN telegram_accounts t ON fta.telegram_account_id = t.id
                WHERE fta.feed_id = %s
            """, (feed_id,))
            telegram_bots = [row[0] for row in self.cur.fetchall()]
            if telegram_bots:
                entry["telegram"] = {"bots": telegram_bots}
            feeds.append(entry)
        return feeds

    def export_accounts_cleartext(self):
        """
        Extract all Telegram, Bluesky, and LinkedIn accounts from the database,
        decrypt sensitive fields and return a structured list as required.
        """
        result = []
        # Telegram
        self.cur.execute("SELECT name, token, chat_id FROM telegram_accounts")
        telegram = []
        for name, token, chat_id in self.cur.fetchall():
            telegram.append({
                "name": name,
                "token": self._decrypt(token),
                "chat_id": chat_id
            })
        if telegram:
            result.append({"telegram": telegram})
        # Bluesky
        self.cur.execute("SELECT name, handle, password, service, mute FROM bluesky_accounts")
        bluesky = []
        for name, handle, password, service, mute in self.cur.fetchall():
            entry = {
                "name": name,
                "handle": handle,
                "password": self._decrypt(password),
                "service": service
            }
            if mute is not None:
                entry["mute"] = bool(mute)
            bluesky.append(entry)
        if bluesky:
            result.append({"bluesky": bluesky})
        # LinkedIn
        self.cur.execute("SELECT name, urn, access_token, mute FROM linkedin_accounts")
        linkedin = []
        for name, urn, access_token, mute in self.cur.fetchall():
            entry = {
                "name": name,
                "urn": urn,
                "access_token": self._decrypt(access_token)
            }
            if mute is not None:
                entry["mute"] = bool(mute)
            linkedin.append(entry)
        if linkedin:
            result.append({"linkedin": linkedin})
        return result

    def export_ai_config_cleartext(self):
        """
        Extract all AI configs from the database, decrypt the key and return a list of dicts.
        """
        result = []
        self.cur.execute("SELECT ai_key, ai_base_url, ai_model, ai_comment_max_chars, ai_comment_language, created_at FROM ai_config")
        for ai_key, ai_base_url, ai_model, ai_comment_max_chars, ai_comment_language, created_at in self.cur.fetchall():
            result.append({
                "ai_key": self._decrypt(ai_key),
                "ai_base_url": ai_base_url,
                "ai_model": ai_model,
                "ai_comment_max_chars": ai_comment_max_chars,
                "ai_comment_language": ai_comment_language,
                "created_at": str(created_at)
            })
        return result

    def export_execution_logs(self):
        """
        Extract all records from execution_logs and return as a list of dict/json.
        """
        self.cur.execute("""
            SELECT l.id, f.rss, l.link, l.datetime, l.description, l.title, l.ai_comment, l.category, l.short_link, l.img_link
            FROM execution_logs l
            JOIN feeds f ON l.feed_id = f.id
            ORDER BY l.datetime DESC
        """)
        logs = []
        for row in self.cur.fetchall():
            logs.append({
                "id": row[0],
                "rss": row[1],
                "link": row[2],
                "datetime": str(row[3]),
                "description": row[4],
                "title": row[5],
                "ai-comment": row[6],
                "category": json.loads(row[7]) if row[7] else None,
                "short_link": row[8],
                "img_link": row[9]
            })
        return logs

    def insert_execution_log_from_json(self, data):
        """
        Insert one or more records into execution_logs from a dict or list of dicts (JSON).
        Looks up feed id via the 'rss' field.
        If the feed does not exist, logs a warning and skips the insert.
        If the datetime is invalid or out of range, replaces with None (default now).
        Returns a tuple (inserted, skipped).
        """
        inserted = 0
        skipped = 0
        if isinstance(data, list):
            for item in data:
                i, s = self.insert_execution_log_from_json(item)
                inserted += i
                skipped += s
            return inserted, skipped
        # Find feed_id from rss field
        self.cur.execute("SELECT id FROM feeds WHERE rss = %s", (data["rss"],))
        row = self.cur.fetchone()
        if not row:
            self.logger.warning(f"Feed RSS not found in DB: {data['rss']}. Skipping log entry.")
            return 0, 1
        feed_id = row[0]
        # Handle datetime
        dt = data.get("datetime")
        dt_valid = None
        if dt:
            try:
                # MariaDB TIMESTAMP: 1970-01-01 00:00:01 to 2038-01-19 03:14:07
                dt_obj = datetime.datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                if dt_obj < datetime.datetime(1970,1,1,0,0,1) or dt_obj > datetime.datetime(2038,1,19,3,14,7):
                    self.logger.warning(f"Datetime '{dt}' out of range for MariaDB TIMESTAMP. Using default (now).")
                    dt_valid = None
                else:
                    dt_valid = dt
            except Exception:
                self.logger.warning(f"Invalid datetime format: '{dt}'. Using default (now).")
                dt_valid = None
        stmt = """
            INSERT INTO execution_logs (
                feed_id, link, datetime, description, title, ai_comment, category, short_link, img_link
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        self.cur.execute(stmt, (
            feed_id,
            data.get("link"),
            dt_valid,
            data.get("description"),
            data.get("title"),
            data.get("ai-comment"),
            json.dumps(data.get("category")) if data.get("category") is not None else None,
            data.get("short_link"),
            data.get("img_link")
        ))
        self.conn.commit()
        self.logger.info(f"Execution log inserted for feed_id={feed_id}, title={data.get('title')}")
        return 1, 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Manage AI configuration and social accounts in MariaDB"
    )
    parser.add_argument("--host", default="localhost", help="DB hostname (default: localhost)")
    parser.add_argument("--port", type=int, default=3306, help="DB port (default: 3306)")
    parser.add_argument("--user", required=True, help="DB user")
    parser.add_argument("--password", help="DB password (if not provided, will be requested)")
    parser.add_argument("--database", required=True, help="Database name")
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--secret-key", help="Fernet key for encryption (or set SOCIALBOT_SECRET_KEY env variable)")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG-level logging (default is INFO)")

    sub = parser.add_subparsers(dest="command", required=True, help="command to execute")
    sub.add_parser("init", help="initialize tables in the database")
    sub.add_parser("insert-ai", help="insert AI configuration (interactive)")
    sub.add_parser("insert-telegram", help="insert Telegram account (interactive)")
    sub.add_parser("insert-bluesky", help="insert Bluesky account (interactive)")
    sub.add_parser("insert-linkedin", help="insert LinkedIn account (interactive)")
    sub.add_parser("insert-feed", help="insert a new feed (interactive)")
    sub.add_parser("drop-all", help="remove all data and tables (WARNING: destructive operation)")
    sub.add_parser("export-feeds", help="export feed+bot list as JSON")
    sub.add_parser("export-accounts", help="export all accounts in cleartext as JSON")
    sub.add_parser("export-ai", help="export AI configuration in cleartext as JSON")
    sub.add_parser("insert-execution-log", help="insert record(s) into execution_logs from a JSON file")
    sub.add_parser("export-execution-logs", help="export all execution logs as JSON")
    return parser.parse_args()



def main():
    args = parse_args()
    # Setup logging
    level = logging.DEBUG if getattr(args, "debug", False) else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger = logging.getLogger("socialbot.initdb")

    pwd = args.password or getpass.getpass("DB Password: ")

    db = DatabaseManager(
        host=args.host,
        port=args.port,
        user=args.user,
        password=pwd,
        database=args.database,
        secret_key=args.secret_key,
        logger=logger
    )
    db.connect()

    if args.command == "init":
        db.create_tables()
    elif args.command == "insert-ai":
        db.insert_ai_config_interactive()
    elif args.command == "insert-telegram":
        db.insert_telegram_interactive()
    elif args.command == "insert-bluesky":
        db.insert_bluesky_interactive()
    elif args.command == "insert-linkedin":
        db.insert_linkedin_interactive()
    elif args.command == "insert-feed":
        db.insert_feed_interactive()
    elif args.command == "export-feeds":
        feeds = db.generate_feed_list()
        print(json.dumps(feeds, indent=4, ensure_ascii=False))
    elif args.command == "export-accounts":
        accounts = db.export_accounts_cleartext()
        print(json.dumps(accounts, indent=4, ensure_ascii=False))
    elif args.command == "export-ai":
        ai_config = db.export_ai_config_cleartext()
        print(json.dumps(ai_config, indent=4, ensure_ascii=False))
    elif args.command == "drop-all":
        confirm = input("Are you sure you want to remove ALL data and tables? (y/N): ").strip().lower()
        if confirm in ("y", "yes"):
            db.drop_all_tables()
        else:
            print("[INFO] Operation cancelled.")
    elif args.command == "insert-execution-log":
        json_path = input("Path to JSON file to insert: ").strip()
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        inserted, skipped = db.insert_execution_log_from_json(data)
        print(f"[OK] Execution logs inserted: {inserted}, skipped: {skipped}.")
    elif args.command == "export-execution-logs":
        logs = db.export_execution_logs()
        print(json.dumps(logs, indent=4, ensure_ascii=False))
    else:
        print(f"[ERROR] Unknown command: {args.command}")
        sys.exit(1)

    db.close()


if __name__ == "__main__":
    main()

