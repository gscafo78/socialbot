#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script per gestire la memorizzazione in MariaDB della configurazione AI
e dei dati degli account social (Telegram, Bluesky, LinkedIn),
con inizializzazione delle tabelle e inserimento interattivo.
"""

import argparse
import sys
import getpass
import os
from cryptography.fernet import Fernet
import logging

import mariadb
import pwinput

__version__ = "1.0.0"


class DatabaseManager:
    """
    Classe per gestire connessione, creazione tabelle e inserimento dati
    su un database MariaDB.
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
        """Apre la connessione al database MariaDB."""
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
        """Chiude la connessione al database."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        self.logger.info("Database connection closed.")

    def create_tables(self):
        """Crea le tabelle (se non esistono) per AI config e social accounts, inclusa la tabella Language."""
        ddl = [
            # Tabella Language
            """
            CREATE TABLE IF NOT EXISTS language (
                code VARCHAR(5) PRIMARY KEY,
                name VARCHAR(50) NOT NULL
            );
            """,
            # Tabella per la configurazione AI
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
            # Tabella per Telegram
            """
            CREATE TABLE IF NOT EXISTS telegram_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                token VARCHAR(255) NOT NULL,
                chat_id VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            # Tabella per Bluesky
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
            # Tabella per LinkedIn
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
            # Tabella per i Feed
            """
            CREATE TABLE IF NOT EXISTS feeds (
                id INT AUTO_INCREMENT PRIMARY KEY,
                rss VARCHAR(255) NOT NULL,
                ai BOOLEAN NOT NULL DEFAULT FALSE
            );
            """,
            # Tabella per Feed Telegram
            """
            CREATE TABLE IF NOT EXISTS feed_telegram_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                feed_id INT NOT NULL,
                telegram_account_id INT NOT NULL,
                FOREIGN KEY (feed_id) REFERENCES feeds(id),
                FOREIGN KEY (telegram_account_id) REFERENCES telegram_accounts(id)
            );
            """,
            # Tabella per Feed Linkedin
            """
            CREATE TABLE IF NOT EXISTS feed_linkedin_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                feed_id INT NOT NULL,
                linkedin_account_id INT NOT NULL,
                FOREIGN KEY (feed_id) REFERENCES feeds(id),
                FOREIGN KEY (linkedin_account_id) REFERENCES linkedin_accounts(id)
            );
            """,
            # Tabella per Feed Bluesky
            """
            CREATE TABLE IF NOT EXISTS feed_bluesky_accounts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                feed_id INT NOT NULL,
                bluesky_account_id INT NOT NULL,
                FOREIGN KEY (feed_id) REFERENCES feeds(id),
                FOREIGN KEY (bluesky_account_id) REFERENCES bluesky_accounts(id)
            );
            """,
            # Tabella per i log di esecuzione
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

        # Precarica i valori nella tabella language
        languages = [
            ("IT", "Italian"),
            ("EN", "English"),
            ("ES", "Espagnol"),
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
        """Inserisce un record in ai_config chiedendo i valori in input, mostrando e validando le lingue disponibili."""
        print("== Inserimento AI Config ==")
        ai_key = pwinput.pwinput(prompt="Enter your AI key: ", mask="*")
        ai_base_url = input("ai_base_url (default: https://api.openai.com/v1/): ").strip() or "https://api.openai.com/v1/"
        ai_model = input("ai_model: ").strip()
        ai_comment_max_chars = int(input("ai_comment_max_chars: ").strip())
        # Mostra lingue disponibili
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
        """Inserisce un record in telegram_accounts chiedendo i valori in input."""
        print("== Inserimento Telegram Account ==")
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
        """Inserisce un record in bluesky_accounts chiedendo i valori in input."""
        print("== Inserimento Bluesky Account ==")
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
        """Inserisce un record in linkedin_accounts chiedendo i valori in input."""
        print("== Inserimento LinkedIn Account ==")
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
            print("Account Telegram disponibili:")
            for acc in telegram_accounts:
                print(f"  {acc[0]}: {acc[1]}")
            tg_ids = input("Inserisci gli ID degli account Telegram da collegare (separati da virgola, lascia vuoto per saltare): ").strip()
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
            print("Account LinkedIn disponibili:")
            for acc in linkedin_accounts:
                print(f"  {acc[0]}: {acc[1]}")
            li_ids = input("Inserisci gli ID degli account LinkedIn da collegare (separati da virgola, lascia vuoto per saltare): ").strip()
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
            print("Account Bluesky disponibili:")
            for acc in bluesky_accounts:
                print(f"  {acc[0]}: {acc[1]}")
            bs_ids = input("Inserisci gli ID degli account Bluesky da collegare (separati da virgola, lascia vuoto per saltare): ").strip()
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Gestione configurazione AI e account social in MariaDB"
    )
    parser.add_argument("--host", default="localhost", help="hostname DB (default: localhost)")
    parser.add_argument("--port", type=int, default=3306, help="porta DB (default: 3306)")
    parser.add_argument("--user", required=True, help="utente DB")
    parser.add_argument("--password", help="password DB (se non fornita verrà richiesta)")
    parser.add_argument("--database", required=True, help="nome del database")
    parser.add_argument(
        "-V", "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument("--secret-key", help="Fernet key for encryption (or set SOCIALBOT_SECRET_KEY env variable)")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG-level logging (default is INFO)")

    sub = parser.add_subparsers(dest="command", required=True, help="comando da eseguire")
    sub.add_parser("init", help="inizializza le tabelle nel database")
    sub.add_parser("insert-ai", help="inserisce configurazione AI (interactive)")
    sub.add_parser("insert-telegram", help="inserisce account Telegram (interactive)")
    sub.add_parser("insert-bluesky", help="inserisce account Bluesky (interactive)")
    sub.add_parser("insert-linkedin", help="inserisce account LinkedIn (interactive)")
    sub.add_parser("insert-feed", help="inserisce un nuovo feed (interactive)")
    sub.add_parser("drop-all", help="rimuove tutti i dati e le tabelle (ATTENZIONE: operazione distruttiva)")

    return parser.parse_args()


def main():
    args = parse_args()
    # Setup logging
    level = logging.DEBUG if getattr(args, "debug", False) else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger = logging.getLogger("socialbot.initdb")

    pwd = args.password or getpass.getpass("Password DB: ")

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
    elif args.command == "drop-all":
        confirm = input("Sei sicuro di voler rimuovere TUTTI i dati e le tabelle? (y/N): ").strip().lower()
        if confirm in ("y", "yes"):
            db.drop_all_tables()
        else:
            print("[INFO] Operazione annullata.")
    else:
        print(f"[ERRORE] Comando sconosciuto: {args.command}")
        sys.exit(1)

    db.close()


if __name__ == "__main__":
    main()