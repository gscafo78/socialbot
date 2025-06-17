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

import mariadb
import pwinput

__version__ = "1.0.0"


class DatabaseManager:
    """
    Classe per gestire connessione, creazione tabelle e inserimento dati
    su un database MariaDB.
    """

    def __init__(self, host: str, user: str, password: str, database: str, port: int = 3306):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.port = port
        self.conn = None  # tipo: mariadb.Connection
        self.cur = None   # tipo: mariadb.Cursor

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
            print(f"[INFO] Connesso al DB '{self.database}' su {self.host}:{self.port}")
        except mariadb.Error as e:
            print(f"[ERRORE] Connessione a MariaDB fallita: {e}")
            sys.exit(1)

    def close(self):
        """Chiude la connessione al database."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        print("[INFO] Connessione al DB chiusa.")

    def create_tables(self):
        """Crea le tabelle (se non esistono) per AI config e social accounts."""
        ddl = [
            # Tabella per la configurazione AI
            """
            CREATE TABLE IF NOT EXISTS ai_config (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ai_key VARCHAR(255) NOT NULL,
                ai_model VARCHAR(255) NOT NULL,
                ai_comment_max_chars INT NOT NULL,
                ai_comment_language VARCHAR(10) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                access_token VARCHAR(255) NOT NULL,
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
                print(f"[ERRORE] Creazione tabella fallita: {e}")
                self.conn.rollback()
                sys.exit(1)

        self.conn.commit()
        print("[INFO] Inizializzazione tabelle completata.")

    def insert_ai_config_interactive(self):
        """Inserisce un record in ai_config chiedendo i valori in input."""
        print("== Inserimento AI Config ==")
        ai_key = pwinput.pwinput(prompt="Enter your AI key: ", mask="*")
        ai_model = input("ai_model: ").strip()
        ai_comment_max_chars = int(input("ai_comment_max_chars: ").strip())
        ai_comment_language = input("ai_comment_language: ").strip()

        stmt = """
            INSERT INTO ai_config (ai_key, ai_model, ai_comment_max_chars, ai_comment_language)
            VALUES (%s, %s, %s, %s)
        """
        try:
            self.cur.execute(stmt, (ai_key, ai_model, ai_comment_max_chars, ai_comment_language))
            self.conn.commit()
            print("[OK] Record AI Config inserito.")
        except mariadb.Error as e:
            print(f"[ERRORE] Inserimento AI Config fallito: {e}")
            self.conn.rollback()

    def insert_telegram_interactive(self):
        """Inserisce un record in telegram_accounts chiedendo i valori in input."""
        print("== Inserimento Telegram Account ==")
        name = input("name: ").strip()
        token = pwinput.pwinput(prompt="Enter your token: ", mask="*")
        chat_id = input("chat_id: ").strip()

        stmt = """
            INSERT INTO telegram_accounts (name, token, chat_id)
            VALUES (%s, %s, %s)
        """
        try:
            self.cur.execute(stmt, (name, token, chat_id))
            self.conn.commit()
            print("[OK] Record Telegram inserito.")
        except mariadb.Error as e:
            print(f"[ERRORE] Inserimento Telegram fallito: {e}")
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

        stmt = """
            INSERT INTO bluesky_accounts (name, handle, password, service, mute)
            VALUES (%s, %s, %s, %s, %s)
        """
        try:
            self.cur.execute(stmt, (name, handle, password, service, mute))
            self.conn.commit()
            print("[OK] Record Bluesky inserito.")
        except mariadb.Error as e:
            print(f"[ERRORE] Inserimento Bluesky fallito: {e}")
            self.conn.rollback()

    def insert_linkedin_interactive(self):
        """Inserisce un record in linkedin_accounts chiedendo i valori in input."""
        print("== Inserimento LinkedIn Account ==")
        name = input("name: ").strip()
        urn = input("urn: ").strip()
        access_token = pwinput.pwinput(prompt="Enter your Token: ", mask="*")
        mute_input = input("mute (y/N): ").strip().lower()
        mute = True if mute_input in ("y", "yes") else False

        stmt = """
            INSERT INTO linkedin_accounts (name, urn, access_token, mute)
            VALUES (%s, %s, %s, %s)
        """
        try:
            self.cur.execute(stmt, (name, urn, access_token, mute))
            self.conn.commit()
            print("[OK] Record LinkedIn inserito.")
        except mariadb.Error as e:
            print(f"[ERRORE] Inserimento LinkedIn fallito: {e}")
            self.conn.rollback()


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

    sub = parser.add_subparsers(dest="command", required=True, help="comando da eseguire")
    sub.add_parser("init", help="inizializza le tabelle nel database")
    sub.add_parser("insert-ai", help="inserisce configurazione AI (interactive)")
    sub.add_parser("insert-telegram", help="inserisce account Telegram (interactive)")
    sub.add_parser("insert-bluesky", help="inserisce account Bluesky (interactive)")
    sub.add_parser("insert-linkedin", help="inserisce account LinkedIn (interactive)")

    return parser.parse_args()


def main():
    args = parse_args()

    pwd = args.password or getpass.getpass("Password DB: ")

    db = DatabaseManager(
        host=args.host,
        port=args.port,
        user=args.user,
        password=pwd,
        database=args.database,
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
    else:
        print(f"[ERRORE] Comando sconosciuto: {args.command}")
        sys.exit(1)

    db.close()


if __name__ == "__main__":
    main()