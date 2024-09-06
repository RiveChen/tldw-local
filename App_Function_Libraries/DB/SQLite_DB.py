# SQLite_DB.py
#########################################
# SQLite_DB Library
# This library is used to perform any/all DB operations related to SQLite.
#
####
import configparser
####################
# Function List
# FIXME - UPDATE Function Arguments
# 1. get_connection(self)
# 2. execute_query(self, query: str, params: Tuple = ())
# 3. create_tables()
# 4. add_keyword(keyword: str)
# 5. delete_keyword(keyword: str)
# 6. add_media_with_keywords(url, title, media_type, content, keywords, prompt, summary, transcription_model, author, ingestion_date)
# 7. fetch_all_keywords()
# 8. keywords_browser_interface()
# 9. display_keywords()
# 10. export_keywords_to_csv()
# 11. browse_items(search_query, search_type)
# 12. fetch_item_details(media_id: int)
# 13. add_media_version(media_id: int, prompt: str, summary: str)
# 14. search_db(search_query: str, search_fields: List[str], keywords: str, page: int = 1, results_per_page: int = 10)
# 15. search_and_display(search_query, search_fields, keywords, page)
# 16. display_details(index, results)
# 17. get_details(index, dataframe)
# 18. format_results(results)
# 19. export_to_csv(search_query: str, search_fields: List[str], keyword: str, page: int = 1, results_per_file: int = 1000)
# 20. is_valid_url(url: str) -> bool
# 21. is_valid_date(date_string: str) -> bool
# 22. add_media_to_database(url, info_dict, segments, summary, keywords, custom_prompt_input, whisper_model)
# 23. create_prompts_db()
# 24. add_prompt(name, details, system, user=None)
# 25. fetch_prompt_details(name)
# 26. list_prompts()
# 27. insert_prompt_to_db(title, description, system_prompt, user_prompt)
# 28. update_media_content(media_id: int, content: str, prompt: str, summary: str)
# 29. search_media_database(query: str) -> List[Tuple[int, str, str]]
# 30. load_media_content(media_id: int)
# 31.
# 32.
#
#
#####################
#
# Import necessary libraries
import csv
import html
import logging
import os
import re
import shutil
import sqlite3
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any
# Local Libraries
from App_Function_Libraries.Utils.Utils import is_valid_url
# Third-Party Libraries
import gradio as gr
import pandas as pd
import yaml


# Import Local Libraries
#
#######################################################################################################################
# Function Definitions
#


# Set up logging
#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
#logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FIXME - Setup properly and test/add documentation for its existence...
config = configparser.ConfigParser()
config.read('config.txt')
sqlite_path = config.get('Database', 'sqlite_path', fallback='media_summary.db')
backup_path = config.get('Database', 'backup_path', fallback='database_backups')

db_path = sqlite_path
backup_dir = backup_path
#create_automated_backup(db_path, backup_dir)

# FIXME - Setup properly and test/add documentation for its existence...
#backup_file = create_automated_backup(db_path, backup_dir)
#upload_to_s3(backup_file, 'your-s3-bucket-name', f"database_backups/{os.path.basename(backup_file)}")

# FIXME - Setup properly and test/add documentation for its existence...
#create_incremental_backup(db_path, backup_dir)

# FIXME - Setup properly and test/add documentation for its existence...
#rotate_backups(backup_dir)

#
#
#######################################################################################################################
#
# Backup-related functions

def create_incremental_backup(db_path, backup_dir):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get the page count of the database
    cursor.execute("PRAGMA page_count")
    page_count = cursor.fetchone()[0]

    # Create a new backup file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"incremental_backup_{timestamp}.sqlib")

    # Perform the incremental backup
    conn.execute(f"VACUUM INTO '{backup_file}'")

    conn.close()
    print(f"Incremental backup created: {backup_file}")
    return backup_file


def create_automated_backup(db_path, backup_dir):
    # Ensure backup directory exists
    os.makedirs(backup_dir, exist_ok=True)

    # Create a timestamped backup file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"media_db_backup_{timestamp}.db")

    # Copy the database file
    shutil.copy2(db_path, backup_file)

    print(f"Backup created: {backup_file}")
    return backup_file

# FIXME - boto3 aint getting installed by default....
# def upload_to_s3(file_path, bucket_name, s3_key):
#     import boto3
#     s3 = boto3.client('s3')
#     try:
#         s3.upload_file(file_path, bucket_name, s3_key)
#         print(f"File uploaded to S3: {s3_key}")
#     except Exception as e:
#         print(f"Error uploading to S3: {str(e)}")


def rotate_backups(backup_dir, max_backups=10):
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.endswith('.db')],
        key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)),
        reverse=True
    )

    while len(backups) > max_backups:
        old_backup = backups.pop()
        os.remove(os.path.join(backup_dir, old_backup))
        print(f"Removed old backup: {old_backup}")

#
#
#######################################################################################################################
#
# DB-Integrity Check Functions

def check_database_integrity(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()

    conn.close()

    if result[0] == "ok":
        print("Database integrity check passed.")
        return True
    else:
        print("Database integrity check failed:", result[0])
        return False

#check_database_integrity(db_path)

#
# End of DB-Integrity Check functions
#######################################################################################################################
#
# Media-related Functions

# Custom exceptions
class DatabaseError(Exception):
    pass


class InputError(Exception):
    pass


# Database connection function with connection pooling
class Database:
    def __init__(self, db_name=None):
        self.db_name = db_name or os.getenv('DB_NAME', 'media_summary.db')
        self.pool = []
        self.pool_size = 10

    @contextmanager
    def get_connection(self):
        retry_count = 5
        retry_delay = 1
        conn = None
        while retry_count > 0:
            try:
                conn = self.pool.pop() if self.pool else sqlite3.connect(self.db_name, check_same_thread=False)
                yield conn
                self.pool.append(conn)
                return
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e):
                    logging.warning(f"Database is locked, retrying in {retry_delay} seconds...")
                    retry_count -= 1
                    time.sleep(retry_delay)
                else:
                    raise DatabaseError(f"Database error: {e}")
            except Exception as e:
                raise DatabaseError(f"Unexpected error: {e}")
            finally:
                # Ensure the connection is returned to the pool even on failure
                if conn:
                    self.pool.append(conn)
        raise DatabaseError("Database is locked and retries have been exhausted")

    def execute_query(self, query: str, params: Tuple = ()) -> None:
        with self.get_connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
            except sqlite3.Error as e:
                raise DatabaseError(f"Database error: {e}, Query: {query}")

db = Database()

def instantiate_SQLite_db():
    global sqlite_db
    sqlite_db = Database()


# Function to create tables with the new media schema
def create_tables(db) -> None:
    table_queries = [
        # CREATE TABLE statements
        '''
        CREATE TABLE IF NOT EXISTS Media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT,
            title TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT,
            author TEXT,
            ingestion_date TEXT,
            prompt TEXT,
            summary TEXT,
            transcription_model TEXT,
            is_trash BOOLEAN DEFAULT 0,
            trash_date DATETIME,
            vector_embedding BLOB
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS Keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS MediaKeywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL,
            keyword_id INTEGER NOT NULL,
            FOREIGN KEY (media_id) REFERENCES Media(id),
            FOREIGN KEY (keyword_id) REFERENCES Keywords(id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS MediaVersion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL,
            version INTEGER NOT NULL,
            prompt TEXT,
            summary TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (media_id) REFERENCES Media(id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS MediaModifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL,
            prompt TEXT,
            summary TEXT,
            modification_date TEXT,
            FOREIGN KEY (media_id) REFERENCES Media(id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS ChatConversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER,
            media_name TEXT,
            conversation_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_id) REFERENCES Media(id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS ChatMessages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            sender TEXT,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES ChatConversations(id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS Transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER,
            whisper_model TEXT,
            transcription TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_id) REFERENCES Media(id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS MediaChunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER,
            chunk_text TEXT,
            start_index INTEGER,
            end_index INTEGER,
            chunk_id TEXT,
            FOREIGN KEY (media_id) REFERENCES Media(id)
        )''',
        '''
        CREATE TABLE IF NOT EXISTS UnvectorizedMediaChunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            start_char INTEGER NOT NULL,
            end_char INTEGER NOT NULL,
            chunk_type TEXT,
            creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_processed BOOLEAN DEFAULT FALSE,
            metadata TEXT,
            FOREIGN KEY (media_id) REFERENCES Media(id)
        )
        ''',
        '''
        CREATE TABLE IF NOT EXISTS DocumentVersions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_id INTEGER NOT NULL,
            version_number INTEGER NOT NULL,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (media_id) REFERENCES Media(id)
        )
        ''',
    ]

    index_queries = [
        # CREATE INDEX statements
        'CREATE INDEX IF NOT EXISTS idx_media_title ON Media(title)',
        'CREATE INDEX IF NOT EXISTS idx_media_type ON Media(type)',
        'CREATE INDEX IF NOT EXISTS idx_media_author ON Media(author)',
        'CREATE INDEX IF NOT EXISTS idx_media_ingestion_date ON Media(ingestion_date)',
        'CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON Keywords(keyword)',
        'CREATE INDEX IF NOT EXISTS idx_mediakeywords_media_id ON MediaKeywords(media_id)',
        'CREATE INDEX IF NOT EXISTS idx_mediakeywords_keyword_id ON MediaKeywords(keyword_id)',
        'CREATE INDEX IF NOT EXISTS idx_media_version_media_id ON MediaVersion(media_id)',
        'CREATE INDEX IF NOT EXISTS idx_mediamodifications_media_id ON MediaModifications(media_id)',
        'CREATE INDEX IF NOT EXISTS idx_chatconversations_media_id ON ChatConversations(media_id)',
        'CREATE INDEX IF NOT EXISTS idx_chatmessages_conversation_id ON ChatMessages(conversation_id)',
        'CREATE INDEX IF NOT EXISTS idx_media_is_trash ON Media(is_trash)',
        'CREATE INDEX IF NOT EXISTS idx_mediachunks_media_id ON MediaChunks(media_id)',
        'CREATE INDEX IF NOT EXISTS idx_unvectorized_media_chunks_media_id ON UnvectorizedMediaChunks(media_id)',
        'CREATE INDEX IF NOT EXISTS idx_unvectorized_media_chunks_is_processed ON UnvectorizedMediaChunks(is_processed)',
        'CREATE INDEX IF NOT EXISTS idx_unvectorized_media_chunks_chunk_type ON UnvectorizedMediaChunks(chunk_type)',
        # CREATE UNIQUE INDEX statements
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_media_url ON Media(url)',
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_media_keyword ON MediaKeywords(media_id, keyword_id)',
        'CREATE INDEX IF NOT EXISTS idx_document_versions_media_id ON DocumentVersions(media_id)',
        'CREATE INDEX IF NOT EXISTS idx_document_versions_version_number ON DocumentVersions(version_number)',
    ]

    virtual_table_queries = [
        # CREATE VIRTUAL TABLE statements
        'CREATE VIRTUAL TABLE IF NOT EXISTS media_fts USING fts5(title, content)',
        'CREATE VIRTUAL TABLE IF NOT EXISTS keyword_fts USING fts5(keyword)'
    ]

    all_queries = table_queries + index_queries + virtual_table_queries

    for query in all_queries:
        try:
            db.execute_query(query)
        except Exception as e:
            logging.error(f"Error executing query: {query}")
            logging.error(f"Error details: {str(e)}")
            raise

    logging.info("All tables, indexes, and virtual tables created successfully.")

create_tables(db)


def check_media_exists(title, url):
    """Check if media with the given title or URL exists in the database."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM Media WHERE title = ? OR url = ?", (title, url))
        result = cursor.fetchone()
        return result is not None


def check_media_and_whisper_model(title=None, url=None, current_whisper_model=None):
    """
    Check if media exists in the database and compare the whisper model used.

    :param title: Title of the media (optional)
    :param url: URL of the media (optional)
    :param current_whisper_model: The whisper model currently selected for use
    :return: Tuple (bool, str) - (should_download, reason)
    """
    if not title and not url:
        return True, "No title or URL provided"

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # First, find the media_id
        query = "SELECT id FROM Media WHERE "
        params = []

        if title:
            query += "title = ?"
            params.append(title)

        if url:
            if params:
                query += " OR "
            query += "url = ?"
            params.append(url)

        cursor.execute(query, tuple(params))
        result = cursor.fetchone()

        if not result:
            return True, "Media not found in database"

        media_id = result[0]

        # Now, get the latest transcript for this media
        cursor.execute("""
            SELECT transcription 
            FROM Transcripts 
            WHERE media_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (media_id,))

        transcript_result = cursor.fetchone()

        if not transcript_result:
            return True, f"No transcript found for media (ID: {media_id})"

        transcription = transcript_result[0]

        # Extract the whisper model from the transcription
        match = re.search(r"This text was transcribed using whisper model: (.+)$", transcription, re.MULTILINE)
        if not match:
            return True, f"Whisper model information not found in transcript (Media ID: {media_id})"

        db_whisper_model = match.group(1).strip()

        if not current_whisper_model:
            return False, f"Media found in database (ID: {media_id})"

        if db_whisper_model != current_whisper_model:
            return True, f"Different whisper model (DB: {db_whisper_model}, Current: {current_whisper_model})"

        return False, f"Media found with same whisper model (ID: {media_id})"


def sqlite_add_media_chunk(db, media_id: int, chunk_text: str, start_index: int, end_index: int, chunk_id: str):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO MediaChunks (media_id, chunk_text, start_index, end_index, chunk_id) VALUES (?, ?, ?, ?, ?)",
            (media_id, chunk_text, start_index, end_index, chunk_id)
        )
        conn.commit()

def sqlite_update_fts_for_media(db, media_id: int):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO media_fts (rowid, title, content) SELECT id, title, content FROM Media WHERE id = ?", (media_id,))
        conn.commit()


def sqlite_get_unprocessed_media(db):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, content, type FROM Media WHERE id NOT IN (SELECT DISTINCT media_id FROM MediaChunks)")
        return cursor.fetchall()

#
# End of Media-related Functions
#######################################################################################################################
# Keyword-related Functions
#

# Function to add a keyword
def add_keyword(keyword: str) -> int:
    keyword = keyword.strip().lower()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT OR IGNORE INTO Keywords (keyword) VALUES (?)', (keyword,))
            cursor.execute('SELECT id FROM Keywords WHERE keyword = ?', (keyword,))
            keyword_id = cursor.fetchone()[0]
            cursor.execute('INSERT OR IGNORE INTO keyword_fts (rowid, keyword) VALUES (?, ?)', (keyword_id, keyword))
            logging.info(f"Keyword '{keyword}' added to keyword_fts with ID: {keyword_id}")
            conn.commit()
            return keyword_id
        except sqlite3.IntegrityError as e:
            logging.error(f"Integrity error adding keyword: {e}")
            raise DatabaseError(f"Integrity error adding keyword: {e}")
        except sqlite3.Error as e:
            logging.error(f"Error adding keyword: {e}")
            raise DatabaseError(f"Error adding keyword: {e}")


# Function to delete a keyword
def delete_keyword(keyword: str) -> str:
    keyword = keyword.strip().lower()
    with db.get_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT id FROM Keywords WHERE keyword = ?', (keyword,))
            keyword_id = cursor.fetchone()
            if keyword_id:
                cursor.execute('DELETE FROM Keywords WHERE keyword = ?', (keyword,))
                cursor.execute('DELETE FROM keyword_fts WHERE rowid = ?', (keyword_id[0],))
                conn.commit()
                return f"Keyword '{keyword}' deleted successfully."
            else:
                return f"Keyword '{keyword}' not found."
        except sqlite3.Error as e:
            raise DatabaseError(f"Error deleting keyword: {e}")



# Function to add media with keywords
def add_media_with_keywords(url, title, media_type, content, keywords, prompt, summary, transcription_model, author,
                            ingestion_date):
    # Set default values for missing fields
    url = url or 'Unknown'
    title = title or 'Untitled'
    media_type = media_type or 'Unknown'
    content = content or 'No content available'
    keywords = keywords or 'default'
    prompt = prompt or 'No prompt available'
    summary = summary or 'No summary available'
    transcription_model = transcription_model or 'Unknown'
    author = author or 'Unknown'
    ingestion_date = ingestion_date or datetime.now().strftime('%Y-%m-%d')

    # Ensure URL is valid
    if not is_valid_url(url):
        url = 'localhost'

    if media_type not in ['article', 'audio', 'document', 'obsidian_note', 'podcast', 'text', 'video', 'unknown']:
        raise InputError("Invalid media type. Allowed types: article, audio file, document, obsidian_note podcast, text, video, unknown.")

    if ingestion_date and not is_valid_date(ingestion_date):
        raise InputError("Invalid ingestion date format. Use YYYY-MM-DD.")

    # Handle keywords as either string or list
    if isinstance(keywords, str):
        keyword_list = [keyword.strip().lower() for keyword in keywords.split(',')]
    elif isinstance(keywords, list):
        keyword_list = [keyword.strip().lower() for keyword in keywords]
    else:
        keyword_list = ['default']

    logging.info(f"Adding/updating media: URL={url}, Title={title}, Type={media_type}")
    logging.debug(f"Content (first 500 chars): {content[:500]}...")
    logging.debug(f"Keywords: {keyword_list}")
    logging.info(f"Prompt: {prompt}")
    logging.info(f"Summary: {summary}")
    logging.info(f"Author: {author}")
    logging.info(f"Ingestion Date: {ingestion_date}")
    logging.info(f"Transcription Model: {transcription_model}")

    try:
        with db.get_connection() as conn:
            conn.execute("BEGIN TRANSACTION")
            cursor = conn.cursor()

            # Check if media already exists
            cursor.execute('SELECT id FROM Media WHERE url = ?', (url,))
            existing_media = cursor.fetchone()

            if existing_media:
                media_id = existing_media[0]
                logging.info(f"Updating existing media with ID: {media_id}")

                cursor.execute('''
                UPDATE Media 
                SET content = ?, transcription_model = ?, title = ?, type = ?, author = ?, ingestion_date = ?
                WHERE id = ?
                ''', (content, transcription_model, title, media_type, author, ingestion_date, media_id))
            else:
                logging.info("Creating new media entry")

                cursor.execute('''
                INSERT INTO Media (url, title, type, content, author, ingestion_date, transcription_model)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (url, title, media_type, content, author, ingestion_date, transcription_model))
                media_id = cursor.lastrowid

            logging.info(f"Adding new modification to MediaModifications for media ID: {media_id}")
            cursor.execute('''
            INSERT INTO MediaModifications (media_id, prompt, summary, modification_date)
            VALUES (?, ?, ?, ?)
            ''', (media_id, prompt, summary, ingestion_date))
            logger.info("New modification added to MediaModifications")

            # Insert keywords and associate with media item
            logging.info("Processing keywords")
            for keyword in keyword_list:
                keyword = keyword.strip().lower()
                cursor.execute('INSERT OR IGNORE INTO Keywords (keyword) VALUES (?)', (keyword,))
                cursor.execute('SELECT id FROM Keywords WHERE keyword = ?', (keyword,))
                keyword_id = cursor.fetchone()[0]
                cursor.execute('INSERT OR IGNORE INTO MediaKeywords (media_id, keyword_id) VALUES (?, ?)',
                               (media_id, keyword_id))

            # Update full-text search index
            logging.info("Updating full-text search index")
            cursor.execute('INSERT OR REPLACE INTO media_fts (rowid, title, content) VALUES (?, ?, ?)',
                           (media_id, title, content))

            logging.info("Adding new media version")
            add_media_version(media_id, prompt, summary)

            conn.commit()
            logging.info(f"Media '{title}' successfully added/updated with ID: {media_id}")

            return f"Media '{title}' added/updated successfully with keywords: {', '.join(keyword_list)}"

    except sqlite3.Error as e:
        conn.rollback()
        logging.error(f"SQL Error: {e}")
        raise DatabaseError(f"Error adding media with keywords: {e}")
    except Exception as e:
        conn.rollback()
        logging.error(f"Unexpected Error: {e}")
        raise DatabaseError(f"Unexpected error: {e}")


def ingest_article_to_db(url, title, author, content, keywords, summary, ingestion_date, custom_prompt):
    try:
        # Check if content is not empty or whitespace
        if not content.strip():
            raise ValueError("Content is empty.")

        keyword_list = keywords.split(',') if keywords else ["default"]
        keyword_str = ', '.join(keyword_list)

        # Set default values for missing fields
        url = url or 'Unknown'
        title = title or 'Unknown'
        author = author or 'Unknown'
        keywords = keywords or 'default'
        summary = summary or 'No summary available'
        ingestion_date = ingestion_date or datetime.now().strftime('%Y-%m-%d')

        # Log the values of all fields before calling add_media_with_keywords
        logging.debug(f"URL: {url}")
        logging.debug(f"Title: {title}")
        logging.debug(f"Author: {author}")
        logging.debug(f"Content: {content[:50]}... (length: {len(content)})")  # Log first 50 characters of content
        logging.debug(f"Keywords: {keywords}")
        logging.debug(f"Summary: {summary}")
        logging.debug(f"Ingestion Date: {ingestion_date}")
        logging.debug(f"Custom Prompt: {custom_prompt}")

        # Check if any required field is empty and log the specific missing field
        if not url:
            logging.error("URL is missing.")
            raise ValueError("URL is missing.")
        if not title:
            logging.error("Title is missing.")
            raise ValueError("Title is missing.")
        if not content:
            logging.error("Content is missing.")
            raise ValueError("Content is missing.")
        if not keywords:
            logging.error("Keywords are missing.")
            raise ValueError("Keywords are missing.")
        if not summary:
            logging.error("Summary is missing.")
            raise ValueError("Summary is missing.")
        if not ingestion_date:
            logging.error("Ingestion date is missing.")
            raise ValueError("Ingestion date is missing.")
        if not custom_prompt:
            logging.error("Custom prompt is missing.")
            raise ValueError("Custom prompt is missing.")

        # Add media with keywords to the database
        result = add_media_with_keywords(
            url=url,
            title=title,
            media_type='article',
            content=content,
            keywords=keyword_str or "article_default",
            prompt=custom_prompt or None,
            summary=summary or "No summary generated",
            transcription_model=None,  # or some default value if applicable
            author=author or 'Unknown',
            ingestion_date=ingestion_date
        )
        return result
    except Exception as e:
        logging.error(f"Failed to ingest article to the database: {e}")
        return str(e)


def fetch_all_keywords() -> List[str]:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT keyword FROM Keywords')
            keywords = [row[0] for row in cursor.fetchall()]
            return keywords
    except sqlite3.Error as e:
        raise DatabaseError(f"Error fetching keywords: {e}")

def keywords_browser_interface():
    keywords = fetch_all_keywords()
    return gr.Markdown("\n".join(f"- {keyword}" for keyword in keywords))

def display_keywords():
    try:
        keywords = fetch_all_keywords()
        return "\n".join(keywords) if keywords else "No keywords found."
    except DatabaseError as e:
        return str(e)


def export_keywords_to_csv():
    try:
        keywords = fetch_all_keywords()
        if not keywords:
            return None, "No keywords found in the database."

        filename = "keywords.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Keyword"])
            for keyword in keywords:
                writer.writerow([keyword])

        return filename, f"Keywords exported to {filename}"
    except Exception as e:
        logger.error(f"Error exporting keywords to CSV: {e}")
        return None, f"Error exporting keywords: {e}"


# Function to fetch items based on search query and type
def browse_items(search_query, search_type):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            if search_type == 'Title':
                cursor.execute("SELECT id, title, url FROM Media WHERE title LIKE ?", (f'%{search_query}%',))
            elif search_type == 'URL':
                cursor.execute("SELECT id, title, url FROM Media WHERE url LIKE ?", (f'%{search_query}%',))
            elif search_type == 'Keyword':
                return fetch_items_by_keyword(search_query)
            elif search_type == 'Content':
                cursor.execute("SELECT id, title, url FROM Media WHERE content LIKE ?", (f'%{search_query}%',))
            else:
                raise ValueError(f"Invalid search type: {search_type}")

            results = cursor.fetchall()
            return results
    except sqlite3.Error as e:
        logger.error(f"Error fetching items by {search_type}: {e}")
        raise DatabaseError(f"Error fetching items by {search_type}: {e}")


# Function to fetch item details
def fetch_item_details(media_id: int):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT prompt, summary 
                FROM MediaModifications 
                WHERE media_id = ? 
                ORDER BY modification_date DESC 
                LIMIT 1
            """, (media_id,))
            prompt_summary_result = cursor.fetchone()
            cursor.execute("SELECT content FROM Media WHERE id = ?", (media_id,))
            content_result = cursor.fetchone()

            prompt = prompt_summary_result[0] if prompt_summary_result else ""
            summary = prompt_summary_result[1] if prompt_summary_result else ""
            content = content_result[0] if content_result else ""

            return content, prompt, summary
    except sqlite3.Error as e:
        logging.error(f"Error fetching item details: {e}")
        # Return empty strings if there's an error
        return "", "", ""

#
#
#######################################################################################################################
#
# Media-related Functions



# Function to add a version of a prompt and summary
def add_media_version(media_id: int, prompt: str, summary: str) -> None:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Get the current version number
            cursor.execute('SELECT MAX(version) FROM MediaVersion WHERE media_id = ?', (media_id,))
            current_version = cursor.fetchone()[0] or 0

            # Insert the new version
            cursor.execute('''
            INSERT INTO MediaVersion (media_id, version, prompt, summary, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (media_id, current_version + 1, prompt, summary, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
    except sqlite3.Error as e:
        raise DatabaseError(f"Error adding media version: {e}")


# Function to search the database with advanced options, including keyword search and full-text search
def sqlite_search_db(search_query: str, search_fields: List[str], keywords: str, page: int = 1, results_per_page: int = 10):
    if page < 1:
        raise ValueError("Page number must be 1 or greater.")

    # Prepare keywords by splitting and trimming
    keywords = [keyword.strip().lower() for keyword in keywords.split(',') if keyword.strip()]

    with db.get_connection() as conn:
        cursor = conn.cursor()
        offset = (page - 1) * results_per_page

        # Prepare the search conditions for general fields
        search_conditions = []
        params = []

        for field in search_fields:
            if search_query:  # Ensure there's a search query before adding this condition
                search_conditions.append(f"Media.{field} LIKE ?")
                params.append(f'%{search_query}%')

        # Prepare the conditions for keywords filtering
        keyword_conditions = []
        for keyword in keywords:
            keyword_conditions.append(
                f"EXISTS (SELECT 1 FROM MediaKeywords mk JOIN Keywords k ON mk.keyword_id = k.id WHERE mk.media_id = Media.id AND k.keyword LIKE ?)")
            params.append(f'%{keyword}%')

        # Combine all conditions
        where_clause = " AND ".join(
            search_conditions + keyword_conditions) if search_conditions or keyword_conditions else "1=1"

        # Complete the query
        query = f'''
        SELECT DISTINCT Media.id, Media.url, Media.title, Media.type, Media.content, Media.author, Media.ingestion_date, 
               MediaModifications.prompt, MediaModifications.summary
        FROM Media
        LEFT JOIN MediaModifications ON Media.id = MediaModifications.media_id
        WHERE {where_clause}
        ORDER BY Media.ingestion_date DESC
        LIMIT ? OFFSET ?
        '''
        params.extend([results_per_page, offset])

        cursor.execute(query, params)
        results = cursor.fetchall()

        return results


# Gradio function to handle user input and display results with pagination, with better feedback
def search_and_display(search_query, search_fields, keywords, page):
    results = sqlite_search_db(search_query, search_fields, keywords, page)

    if isinstance(results, pd.DataFrame):
        # Convert DataFrame to a list of tuples or lists
        processed_results = results.values.tolist()  # This converts DataFrame rows to lists
    elif isinstance(results, list):
        # Ensure that each element in the list is itself a list or tuple (not a dictionary)
        processed_results = [list(item.values()) if isinstance(item, dict) else item for item in results]
    else:
        raise TypeError("Unsupported data type for results")

    return processed_results


def display_details(index, results):
    if index is None or results is None:
        return "Please select a result to view details."

    try:
        # Ensure the index is an integer and access the row properly
        index = int(index)
        if isinstance(results, pd.DataFrame):
            if index >= len(results):
                return "Index out of range. Please select a valid index."
            selected_row = results.iloc[index]
        else:
            # If results is not a DataFrame, but a list (assuming list of dicts)
            selected_row = results[index]
    except ValueError:
        return "Index must be an integer."
    except IndexError:
        return "Index out of range. Please select a valid index."

    # Build HTML output safely
    details_html = f"""
    <h3>{selected_row.get('Title', 'No Title')}</h3>
    <p><strong>URL:</strong> {selected_row.get('URL', 'No URL')}</p>
    <p><strong>Type:</strong> {selected_row.get('Type', 'No Type')}</p>
    <p><strong>Author:</strong> {selected_row.get('Author', 'No Author')}</p>
    <p><strong>Ingestion Date:</strong> {selected_row.get('Ingestion Date', 'No Date')}</p>
    <p><strong>Prompt:</strong> {selected_row.get('Prompt', 'No Prompt')}</p>
    <p><strong>Summary:</strong> {selected_row.get('Summary', 'No Summary')}</p>
    <p><strong>Content:</strong> {selected_row.get('Content', 'No Content')}</p>
    """
    return details_html


def get_details(index, dataframe):
    if index is None or dataframe is None or index >= len(dataframe):
        return "Please select a result to view details."
    row = dataframe.iloc[index]
    details = f"""
    <h3>{row['Title']}</h3>
    <p><strong>URL:</strong> {row['URL']}</p>
    <p><strong>Type:</strong> {row['Type']}</p>
    <p><strong>Author:</strong> {row['Author']}</p>
    <p><strong>Ingestion Date:</strong> {row['Ingestion Date']}</p>
    <p><strong>Prompt:</strong> {row['Prompt']}</p>
    <p><strong>Summary:</strong> {row['Summary']}</p>
    <p><strong>Content:</strong></p>
    <pre>{row['Content']}</pre>
    """
    return details


def format_results(results):
    if not results:
        return pd.DataFrame(columns=['URL', 'Title', 'Type', 'Content', 'Author', 'Ingestion Date', 'Prompt', 'Summary'])

    df = pd.DataFrame(results, columns=['URL', 'Title', 'Type', 'Content', 'Author', 'Ingestion Date', 'Prompt', 'Summary'])
    logging.debug(f"Formatted DataFrame: {df}")

    return df


# Function to export search results to CSV or markdown with pagination
def export_to_file(search_query: str, search_fields: List[str], keyword: str, page: int = 1, results_per_file: int = 1000, export_format: str = 'csv'):
    try:
        results = sqlite_search_db(search_query, search_fields, keyword, page, results_per_file)
        if not results:
            return "No results found to export."

        # Create an 'exports' directory if it doesn't exist
        if not os.path.exists('exports'):
            os.makedirs('exports')

        if export_format == 'csv':
            filename = f'exports/search_results_page_{page}.csv'
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['URL', 'Title', 'Type', 'Content', 'Author', 'Ingestion Date', 'Prompt', 'Summary'])
                for row in results:
                    writer.writerow(row)
        elif export_format == 'markdown':
            filename = f'exports/search_results_page_{page}.md'
            with open(filename, 'w', encoding='utf-8') as file:
                for item in results:
                    markdown_content = convert_to_markdown({
                        'title': item[1],
                        'url': item[0],
                        'type': item[2],
                        'content': item[3],
                        'author': item[4],
                        'ingestion_date': item[5],
                        'summary': item[7],
                        'keywords': item[8].split(',') if item[8] else []
                    })
                    file.write(markdown_content)
                    file.write("\n---\n\n")  # Separator between items
        else:
            return f"Unsupported export format: {export_format}"

        return f"Results exported to {filename}"
    except (DatabaseError, InputError) as e:
        return str(e)


# Helper function to validate date format
def is_valid_date(date_string: str) -> bool:
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False


# Add ingested media to DB
def add_media_to_database(url, info_dict, segments, summary, keywords, custom_prompt_input, whisper_model, media_type='video'):
    try:
        # Extract content from segments
        if isinstance(segments, list):
            content = ' '.join([segment.get('Text', '') for segment in segments if 'Text' in segment])
        elif isinstance(segments, dict):
            content = segments.get('text', '') or segments.get('content', '')
        else:
            content = str(segments)

        logging.debug(f"Extracted content (first 500 chars): {content[:500]}")

        # Set default custom prompt if not provided
        if custom_prompt_input is None:
            custom_prompt_input = """No Custom Prompt Provided or Was Used."""

        logging.info(f"Adding media to database: URL={url}, Title={info_dict.get('title', 'Untitled')}, Type={media_type}")

        # Process keywords
        if isinstance(keywords, str):
            keyword_list = [keyword.strip().lower() for keyword in keywords.split(',')]
        elif isinstance(keywords, (list, tuple)):
            keyword_list = [keyword.strip().lower() for keyword in keywords]
        else:
            keyword_list = ['default']

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Check if media already exists
            cursor.execute('SELECT id FROM Media WHERE url = ?', (url,))
            existing_media = cursor.fetchone()

            if existing_media:
                media_id = existing_media[0]
                logging.info(f"Updating existing media with ID: {media_id}")

                cursor.execute('''
                UPDATE Media 
                SET content = ?, transcription_model = ?, title = ?, type = ?, author = ?, ingestion_date = ?
                WHERE id = ?
                ''', (content, whisper_model, info_dict.get('title', 'Untitled'), media_type,
                      info_dict.get('uploader', 'Unknown'), datetime.now().strftime('%Y-%m-%d'), media_id))
            else:
                logging.info("Creating new media entry")

                cursor.execute('''
                INSERT INTO Media (url, title, type, content, author, ingestion_date, transcription_model)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (url, info_dict.get('title', 'Untitled'), media_type, content,
                      info_dict.get('uploader', 'Unknown'), datetime.now().strftime('%Y-%m-%d'), whisper_model))
                media_id = cursor.lastrowid

            logging.info(f"Adding new modification to MediaModifications for media ID: {media_id}")
            cursor.execute('''
            INSERT INTO MediaModifications (media_id, prompt, summary, modification_date)
            VALUES (?, ?, ?, ?)
            ''', (media_id, custom_prompt_input, summary, datetime.now().strftime('%Y-%m-%d')))

            # Insert keywords and associate with media item
            logging.info("Processing keywords")
            for keyword in keyword_list:
                cursor.execute('INSERT OR IGNORE INTO Keywords (keyword) VALUES (?)', (keyword,))
                cursor.execute('SELECT id FROM Keywords WHERE keyword = ?', (keyword,))
                keyword_id = cursor.fetchone()[0]
                cursor.execute('INSERT OR IGNORE INTO MediaKeywords (media_id, keyword_id) VALUES (?, ?)',
                               (media_id, keyword_id))

            # Update full-text search index
            logging.info("Updating full-text search index")
            cursor.execute('INSERT OR REPLACE INTO media_fts (rowid, title, content) VALUES (?, ?, ?)',
                           (media_id, info_dict.get('title', 'Untitled'), content))

            logging.info("Adding new media version")
            add_media_version(media_id, custom_prompt_input, summary)

            # Create initial document version
            create_document_version(media_id, content)

            conn.commit()

        logging.info(f"Media '{info_dict.get('title', 'Untitled')}' successfully added/updated with ID: {media_id}")

        return f"Media '{info_dict.get('title', 'Untitled')}' added/updated successfully with keywords: {', '.join(keyword_list)}"

    except sqlite3.Error as e:
        logging.error(f"SQL Error: {e}")
        raise DatabaseError(f"Error adding media with keywords: {e}")
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        raise DatabaseError(f"Unexpected error: {e}")

#
# End of ....
#######################################################################################################################
#
# Functions to manage prompts DB

def create_prompts_db():
    with sqlite3.connect('prompts.db') as conn:
        cursor = conn.cursor()
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS Prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                details TEXT,
                system TEXT,
                user TEXT
            );
            CREATE TABLE IF NOT EXISTS Keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE COLLATE NOCASE
            );
            CREATE TABLE IF NOT EXISTS PromptKeywords (
                prompt_id INTEGER,
                keyword_id INTEGER,
                FOREIGN KEY (prompt_id) REFERENCES Prompts (id),
                FOREIGN KEY (keyword_id) REFERENCES Keywords (id),
                PRIMARY KEY (prompt_id, keyword_id)
            );
            CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON Keywords(keyword);
            CREATE INDEX IF NOT EXISTS idx_promptkeywords_prompt_id ON PromptKeywords(prompt_id);
            CREATE INDEX IF NOT EXISTS idx_promptkeywords_keyword_id ON PromptKeywords(keyword_id);
        ''')


def normalize_keyword(keyword):
    return re.sub(r'\s+', ' ', keyword.strip().lower())


def add_prompt(name, details, system, user=None, keywords=None):
    if not name or not system:
        return "Name and system prompt are required."

    try:
        with sqlite3.connect('prompts.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Prompts (name, details, system, user)
                VALUES (?, ?, ?, ?)
            ''', (name, details, system, user))
            prompt_id = cursor.lastrowid

            if keywords:
                normalized_keywords = [normalize_keyword(k) for k in keywords if k.strip()]
                for keyword in set(normalized_keywords):  # Use set to remove duplicates
                    cursor.execute('''
                        INSERT OR IGNORE INTO Keywords (keyword) VALUES (?)
                    ''', (keyword,))
                    cursor.execute('SELECT id FROM Keywords WHERE keyword = ?', (keyword,))
                    keyword_id = cursor.fetchone()[0]
                    cursor.execute('''
                        INSERT OR IGNORE INTO PromptKeywords (prompt_id, keyword_id) VALUES (?, ?)
                    ''', (prompt_id, keyword_id))
        return "Prompt added successfully."
    except sqlite3.IntegrityError:
        return "Prompt with this name already exists."
    except sqlite3.Error as e:
        return f"Database error: {e}"


def fetch_prompt_details(name):
    with sqlite3.connect('prompts.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.name, p.details, p.system, p.user, GROUP_CONCAT(k.keyword, ', ') as keywords
            FROM Prompts p
            LEFT JOIN PromptKeywords pk ON p.id = pk.prompt_id
            LEFT JOIN Keywords k ON pk.keyword_id = k.id
            WHERE p.name = ?
            GROUP BY p.id
        ''', (name,))
        return cursor.fetchone()


def list_prompts(page=1, per_page=10):
    offset = (page - 1) * per_page
    with sqlite3.connect('prompts.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM Prompts LIMIT ? OFFSET ?', (per_page, offset))
        prompts = [row[0] for row in cursor.fetchall()]

        # Get total count of prompts
        cursor.execute('SELECT COUNT(*) FROM Prompts')
        total_count = cursor.fetchone()[0]

    total_pages = (total_count + per_page - 1) // per_page
    return prompts, total_pages, page

# This will not scale. For a large number of prompts, use a more efficient method.
# FIXME - see above statement.
def load_preset_prompts():
    try:
        with sqlite3.connect('prompts.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM Prompts ORDER BY name ASC')
            prompts = [row[0] for row in cursor.fetchall()]
        return prompts
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []


def insert_prompt_to_db(title, description, system_prompt, user_prompt, keywords=None):
    return add_prompt(title, description, system_prompt, user_prompt, keywords)


def search_prompts_by_keyword(keyword, page=1, per_page=10):
    normalized_keyword = normalize_keyword(keyword)
    offset = (page - 1) * per_page
    with sqlite3.connect('prompts.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT p.name
            FROM Prompts p
            JOIN PromptKeywords pk ON p.id = pk.prompt_id
            JOIN Keywords k ON pk.keyword_id = k.id
            WHERE k.keyword LIKE ?
            LIMIT ? OFFSET ?
        ''', ('%' + normalized_keyword + '%', per_page, offset))
        prompts = [row[0] for row in cursor.fetchall()]

        # Get total count of matching prompts
        cursor.execute('''
            SELECT COUNT(DISTINCT p.id)
            FROM Prompts p
            JOIN PromptKeywords pk ON p.id = pk.prompt_id
            JOIN Keywords k ON pk.keyword_id = k.id
            WHERE k.keyword LIKE ?
        ''', ('%' + normalized_keyword + '%',))
        total_count = cursor.fetchone()[0]

    total_pages = (total_count + per_page - 1) // per_page
    return prompts, total_pages, page


def update_prompt_keywords(prompt_name, new_keywords):
    try:
        with sqlite3.connect('prompts.db') as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT id FROM Prompts WHERE name = ?', (prompt_name,))
            prompt_id = cursor.fetchone()
            if not prompt_id:
                return "Prompt not found."
            prompt_id = prompt_id[0]

            cursor.execute('DELETE FROM PromptKeywords WHERE prompt_id = ?', (prompt_id,))

            normalized_keywords = [normalize_keyword(k) for k in new_keywords if k.strip()]
            for keyword in set(normalized_keywords):  # Use set to remove duplicates
                cursor.execute('INSERT OR IGNORE INTO Keywords (keyword) VALUES (?)', (keyword,))
                cursor.execute('SELECT id FROM Keywords WHERE keyword = ?', (keyword,))
                keyword_id = cursor.fetchone()[0]
                cursor.execute('INSERT INTO PromptKeywords (prompt_id, keyword_id) VALUES (?, ?)',
                               (prompt_id, keyword_id))

            # Remove unused keywords
            cursor.execute('''
                DELETE FROM Keywords
                WHERE id NOT IN (SELECT DISTINCT keyword_id FROM PromptKeywords)
            ''')
        return "Keywords updated successfully."
    except sqlite3.Error as e:
        return f"Database error: {e}"


def add_or_update_prompt(title, description, system_prompt, user_prompt, keywords=None):
    if not title:
        return "Error: Title is required."

    existing_prompt = fetch_prompt_details(title)
    if existing_prompt:
        # Update existing prompt
        result = update_prompt_in_db(title, description, system_prompt, user_prompt)
        if "successfully" in result:
            # Update keywords if the prompt update was successful
            keyword_result = update_prompt_keywords(title, keywords or [])
            result += f" {keyword_result}"
    else:
        # Insert new prompt
        result = insert_prompt_to_db(title, description, system_prompt, user_prompt, keywords)

    return result


def load_prompt_details(selected_prompt):
    if selected_prompt:
        details = fetch_prompt_details(selected_prompt)
        if details:
            return details[0], details[1], details[2], details[3], details[4]  # Include keywords
    return "", "", "", "", ""


def update_prompt_in_db(title, description, system_prompt, user_prompt):
    try:
        with sqlite3.connect('prompts.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE Prompts SET details = ?, system = ?, user = ? WHERE name = ?",
                (description, system_prompt, user_prompt, title)
            )
            if cursor.rowcount == 0:
                return "No prompt found with the given title."
        return "Prompt updated successfully!"
    except sqlite3.Error as e:
        return f"Error updating prompt: {e}"


create_prompts_db()

def delete_prompt(prompt_id):
    try:
        with sqlite3.connect('prompts.db') as conn:
            cursor = conn.cursor()

            # Delete associated keywords
            cursor.execute("DELETE FROM PromptKeywords WHERE prompt_id = ?", (prompt_id,))

            # Delete the prompt
            cursor.execute("DELETE FROM Prompts WHERE id = ?", (prompt_id,))

            if cursor.rowcount == 0:
                return f"No prompt found with ID {prompt_id}"
            else:
                conn.commit()
                return f"Prompt with ID {prompt_id} has been successfully deleted"
    except sqlite3.Error as e:
        return f"An error occurred: {e}"

#
#
#######################################################################################################################
#
# Function to fetch/update media content

def update_media_content(selected_item, item_mapping, content_input, prompt_input, summary_input):
    try:
        if selected_item and item_mapping and selected_item in item_mapping:
            media_id = item_mapping[selected_item]

            with db.get_connection() as conn:
                cursor = conn.cursor()

                # Update the main content in the Media table
                cursor.execute("UPDATE Media SET content = ? WHERE id = ?", (content_input, media_id))

                # Check if a row already exists in MediaModifications for this media_id
                cursor.execute("SELECT COUNT(*) FROM MediaModifications WHERE media_id = ?", (media_id,))
                exists = cursor.fetchone()[0] > 0

                if exists:
                    # Update existing row
                    cursor.execute("""
                        UPDATE MediaModifications
                        SET prompt = ?, summary = ?, modification_date = CURRENT_TIMESTAMP
                        WHERE media_id = ?
                    """, (prompt_input, summary_input, media_id))
                else:
                    # Insert new row
                    cursor.execute("""
                        INSERT INTO MediaModifications (media_id, prompt, summary, modification_date)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """, (media_id, prompt_input, summary_input))

                # Create new document version
                new_version = create_document_version(media_id, content_input)

                conn.commit()

            return f"Content updated successfully for media ID: {media_id}. New version: {new_version}"
        else:
            return "No item selected or invalid selection"
    except Exception as e:
        logging.error(f"Error updating media content: {e}")
        return f"Error updating content: {str(e)}"


def search_media_database(query: str) -> List[Tuple[int, str, str]]:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, url FROM Media WHERE title LIKE ?", (f'%{query}%',))
            results = cursor.fetchall()
        return results
    except sqlite3.Error as e:
        raise Exception(f"Error searching media database: {e}")

def load_media_content(media_id: int) -> dict:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content, prompt, summary FROM Media WHERE id = ?", (media_id,))
            result = cursor.fetchone()
            if result:
                return {
                    "content": result[0],
                    "prompt": result[1],
                    "summary": result[2]
                }
            return {"content": "", "prompt": "", "summary": ""}
    except sqlite3.Error as e:
        raise Exception(f"Error loading media content: {e}")


def fetch_items_by_title_or_url(search_query: str, search_type: str):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            if search_type == 'Title':
                cursor.execute("SELECT id, title, url FROM Media WHERE title LIKE ?", (f'%{search_query}%',))
            elif search_type == 'URL':
                cursor.execute("SELECT id, title, url FROM Media WHERE url LIKE ?", (f'%{search_query}%',))
            results = cursor.fetchall()
            return results
    except sqlite3.Error as e:
        raise DatabaseError(f"Error fetching items by {search_type}: {e}")


def fetch_items_by_keyword(search_query: str):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id, m.title, m.url
                FROM Media m
                JOIN MediaKeywords mk ON m.id = mk.media_id
                JOIN Keywords k ON mk.keyword_id = k.id
                WHERE k.keyword LIKE ?
            """, (f'%{search_query}%',))
            results = cursor.fetchall()
            return results
    except sqlite3.Error as e:
        raise DatabaseError(f"Error fetching items by keyword: {e}")


def fetch_items_by_content(search_query: str):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, url FROM Media WHERE content LIKE ?", (f'%{search_query}%',))
            results = cursor.fetchall()
            return results
    except sqlite3.Error as e:
        raise DatabaseError(f"Error fetching items by content: {e}")


def fetch_item_details_single(media_id: int):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT prompt, summary 
                FROM MediaModifications 
                WHERE media_id = ? 
                ORDER BY modification_date DESC 
                LIMIT 1
            """, (media_id,))
            prompt_summary_result = cursor.fetchone()
            cursor.execute("SELECT content FROM Media WHERE id = ?", (media_id,))
            content_result = cursor.fetchone()

            prompt = prompt_summary_result[0] if prompt_summary_result else ""
            summary = prompt_summary_result[1] if prompt_summary_result else ""
            content = content_result[0] if content_result else ""

            return prompt, summary, content
    except sqlite3.Error as e:
        raise Exception(f"Error fetching item details: {e}")



def convert_to_markdown(item):
    markdown = f"# {item['title']}\n\n"
    markdown += f"**URL:** {item['url']}\n\n"
    markdown += f"**Author:** {item['author']}\n\n"
    markdown += f"**Ingestion Date:** {item['ingestion_date']}\n\n"
    markdown += f"**Type:** {item['type']}\n\n"
    markdown += f"**Keywords:** {', '.join(item['keywords'])}\n\n"
    markdown += "## Summary\n\n"
    markdown += f"{item['summary']}\n\n"
    markdown += "## Content\n\n"
    markdown += f"{item['content']}\n\n"
    return markdown

# Gradio function to handle user input and display results with pagination for displaying entries in the DB
def fetch_paginated_data(page: int, results_per_page: int) -> Tuple[List[Tuple], int]:
    try:
        offset = (page - 1) * results_per_page
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Media")
            total_entries = cursor.fetchone()[0]

            cursor.execute("SELECT id, title, url FROM Media LIMIT ? OFFSET ?", (results_per_page, offset))
            results = cursor.fetchall()

        return results, total_entries
    except sqlite3.Error as e:
        raise Exception(f"Error fetching paginated data: {e}")

def format_results_as_html(results: List[Tuple]) -> str:
    html = "<table class='table table-striped'>"
    html += "<tr><th>ID</th><th>Title</th><th>URL</th></tr>"
    for row in results:
        html += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td></tr>"
    html += "</table>"
    return html

def view_database(page: int, results_per_page: int) -> Tuple[str, str, int]:
    results, total_entries = fetch_paginated_data(page, results_per_page)
    formatted_results = format_results_as_html(results)
    # Calculate total pages
    total_pages = (total_entries + results_per_page - 1) // results_per_page
    return formatted_results, f"Page {page} of {total_pages}", total_pages


def search_and_display_items(query, search_type, page, entries_per_page,char_count):
    offset = (page - 1) * entries_per_page
    try:
        with sqlite3.connect('media_summary.db') as conn:
            cursor = conn.cursor()

            # Adjust the SQL query based on the search type
            if search_type == "Title":
                where_clause = "WHERE m.title LIKE ?"
            elif search_type == "URL":
                where_clause = "WHERE m.url LIKE ?"
            elif search_type == "Keyword":
                where_clause = "WHERE k.keyword LIKE ?"
            elif search_type == "Content":
                where_clause = "WHERE m.content LIKE ?"
            else:
                raise ValueError("Invalid search type")

            cursor.execute(f'''
                SELECT m.id, m.title, m.url, m.content, mm.summary, GROUP_CONCAT(k.keyword, ', ') as keywords
                FROM Media m
                LEFT JOIN MediaModifications mm ON m.id = mm.media_id
                LEFT JOIN MediaKeywords mk ON m.id = mk.media_id
                LEFT JOIN Keywords k ON mk.keyword_id = k.id
                {where_clause}
                GROUP BY m.id
                ORDER BY m.ingestion_date DESC
                LIMIT ? OFFSET ?
            ''', (f'%{query}%', entries_per_page, offset))
            items = cursor.fetchall()

            cursor.execute(f'''
                SELECT COUNT(DISTINCT m.id)
                FROM Media m
                LEFT JOIN MediaKeywords mk ON m.id = mk.media_id
                LEFT JOIN Keywords k ON mk.keyword_id = k.id
                {where_clause}
            ''', (f'%{query}%',))
            total_items = cursor.fetchone()[0]

        results = ""
        for item in items:
            title = html.escape(item[1]).replace('\n', '<br>')
            url = html.escape(item[2]).replace('\n', '<br>')
            # First X amount of characters of the content
            content = html.escape(item[3] or '')[:char_count] + '...'
            summary = html.escape(item[4] or '').replace('\n', '<br>')
            keywords = html.escape(item[5] or '').replace('\n', '<br>')

            results += f"""
            <div style="border: 1px solid #ddd; padding: 10px; margin-bottom: 20px;">
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div><strong>Title:</strong> {title}</div>
                    <div><strong>URL:</strong> {url}</div>
                </div>
                <div style="margin-top: 10px;">
                    <strong>Content (first {char_count} characters):</strong>
                    <pre style="white-space: pre-wrap; word-wrap: break-word;">{content}</pre>
                </div>
                <div style="margin-top: 10px;">
                    <strong>Summary:</strong>
                    <pre style="white-space: pre-wrap; word-wrap: break-word;">{summary}</pre>
                </div>
                <div style="margin-top: 10px;">
                    <strong>Keywords:</strong> {keywords}
                </div>
            </div>
            """

        total_pages = (total_items + entries_per_page - 1) // entries_per_page
        pagination = f"Page {page} of {total_pages} (Total items: {total_items})"

        return results, pagination, total_pages
    except sqlite3.Error as e:
        return f"<p>Error searching items: {e}</p>", "Error", 0


#
# End of Functions to manage prompts DB / Fetch and update media content
#######################################################################################################################
#
# Obsidian-related Functions

def import_obsidian_note_to_db(note_data):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM Media WHERE title = ? AND type = 'obsidian_note'", (note_data['title'],))
            existing_note = cursor.fetchone()

            # Generate a relative path or meaningful identifier instead of using the temporary file path
            relative_path = os.path.relpath(note_data['file_path'], start=os.path.dirname(note_data['file_path']))

            if existing_note:
                media_id = existing_note[0]
                cursor.execute("""
                    UPDATE Media
                    SET content = ?, author = ?, ingestion_date = CURRENT_TIMESTAMP, url = ?
                    WHERE id = ?
                """, (note_data['content'], note_data['frontmatter'].get('author', 'Unknown'), relative_path, media_id))

                cursor.execute("DELETE FROM MediaKeywords WHERE media_id = ?", (media_id,))
            else:
                cursor.execute("""
                    INSERT INTO Media (title, content, type, author, ingestion_date, url)
                    VALUES (?, ?, 'obsidian_note', ?, CURRENT_TIMESTAMP, ?)
                """, (note_data['title'], note_data['content'], note_data['frontmatter'].get('author', 'Unknown'),
                      relative_path))

                media_id = cursor.lastrowid

            for tag in note_data['tags']:
                cursor.execute("INSERT OR IGNORE INTO Keywords (keyword) VALUES (?)", (tag,))
                cursor.execute("SELECT id FROM Keywords WHERE keyword = ?", (tag,))
                keyword_id = cursor.fetchone()[0]
                cursor.execute("INSERT OR IGNORE INTO MediaKeywords (media_id, keyword_id) VALUES (?, ?)",
                               (media_id, keyword_id))

            frontmatter_str = yaml.dump(note_data['frontmatter'])
            cursor.execute("""
                INSERT INTO MediaModifications (media_id, prompt, summary, modification_date)
                VALUES (?, 'Obsidian Frontmatter', ?, CURRENT_TIMESTAMP)
            """, (media_id, frontmatter_str))

            # Update full-text search index
            cursor.execute('INSERT OR REPLACE INTO media_fts (rowid, title, content) VALUES (?, ?, ?)',
                           (media_id, note_data['title'], note_data['content']))

        action = "Updated" if existing_note else "Imported"
        logger.info(f"{action} Obsidian note: {note_data['title']}")
        return True, None
    except sqlite3.Error as e:
        error_msg = f"Database error {'updating' if existing_note else 'importing'} note {note_data['title']}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error {'updating' if existing_note else 'importing'} note {note_data['title']}: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return False, error_msg


#
# End of Obsidian-related Functions
#######################################################################################################################
#
# Chat-related Functions



def create_chat_conversation(media_id, conversation_name):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ChatConversations (media_id, conversation_name, created_at, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (media_id, conversation_name))
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Error creating chat conversation: {e}")
        raise DatabaseError(f"Error creating chat conversation: {e}")


def add_chat_message(conversation_id: int, sender: str, message: str) -> int:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ChatMessages (conversation_id, sender, message)
                VALUES (?, ?, ?)
            ''', (conversation_id, sender, message))
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logging.error(f"Error adding chat message: {e}")
        raise DatabaseError(f"Error adding chat message: {e}")


def get_chat_messages(conversation_id: int) -> List[Dict[str, Any]]:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, sender, message, timestamp
                FROM ChatMessages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            ''', (conversation_id,))
            messages = cursor.fetchall()
            return [
                {
                    'id': msg[0],
                    'sender': msg[1],
                    'message': msg[2],
                    'timestamp': msg[3]
                }
                for msg in messages
            ]
    except sqlite3.Error as e:
        logging.error(f"Error retrieving chat messages: {e}")
        raise DatabaseError(f"Error retrieving chat messages: {e}")


def search_chat_conversations(search_query: str) -> List[Dict[str, Any]]:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT cc.id, cc.media_id, cc.conversation_name, cc.created_at, m.title as media_title
                FROM ChatConversations cc
                LEFT JOIN Media m ON cc.media_id = m.id
                WHERE cc.conversation_name LIKE ? OR m.title LIKE ?
                ORDER BY cc.updated_at DESC
            ''', (f'%{search_query}%', f'%{search_query}%'))
            conversations = cursor.fetchall()
            return [
                {
                    'id': conv[0],
                    'media_id': conv[1],
                    'conversation_name': conv[2],
                    'created_at': conv[3],
                    'media_title': conv[4] or "Unknown Media"
                }
                for conv in conversations
            ]
    except sqlite3.Error as e:
        logging.error(f"Error searching chat conversations: {e}")
        return []


def update_chat_message(message_id: int, new_message: str) -> None:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE ChatMessages
                SET message = ?, timestamp = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (new_message, message_id))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error updating chat message: {e}")
        raise DatabaseError(f"Error updating chat message: {e}")


def delete_chat_message(message_id: int) -> None:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ChatMessages WHERE id = ?', (message_id,))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Error deleting chat message: {e}")
        raise DatabaseError(f"Error deleting chat message: {e}")


def save_chat_history_to_database(chatbot, conversation_id, media_id, media_name, conversation_name):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # If conversation_id is None, create a new conversation
            if conversation_id is None:
                cursor.execute('''
                    INSERT INTO ChatConversations (media_id, media_name, conversation_name, created_at, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (media_id, media_name, conversation_name))
                conversation_id = cursor.lastrowid
            else:
                # If conversation exists, update the media_name
                cursor.execute('''
                    UPDATE ChatConversations
                    SET media_name = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (media_name, conversation_id))

            # Save each message in the chatbot history
            for i, (user_msg, ai_msg) in enumerate(chatbot):
                cursor.execute('''
                    INSERT INTO ChatMessages (conversation_id, sender, message, timestamp)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (conversation_id, 'user', user_msg))

                cursor.execute('''
                    INSERT INTO ChatMessages (conversation_id, sender, message, timestamp)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (conversation_id, 'ai', ai_msg))

            # Update the conversation's updated_at timestamp
            cursor.execute('''
                UPDATE ChatConversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (conversation_id,))

            conn.commit()

        return conversation_id
    except Exception as e:
        logging.error(f"Error saving chat history to database: {str(e)}")
        raise


def get_conversation_name(conversation_id):
    if conversation_id is None:
        return None

    try:
        with sqlite3.connect('media_summary.db') as conn:  # Replace with your actual database name
            cursor = conn.cursor()

            query = """
            SELECT conversation_name, media_name
            FROM ChatConversations
            WHERE id = ?
            """

            cursor.execute(query, (conversation_id,))
            result = cursor.fetchone()

            if result:
                conversation_name, media_name = result
                if conversation_name:
                    return conversation_name
                elif media_name:
                    return f"{media_name}-chat"

            return None  # Return None if no result found
    except sqlite3.Error as e:
        logging.error(f"Database error in get_conversation_name: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in get_conversation_name: {e}")
        return None

#
# End of Chat-related Functions
#######################################################################################################################


#######################################################################################################################
#
# Functions to Compare Transcripts

# Fetch Transcripts
def get_transcripts(media_id):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, whisper_model, transcription, created_at
            FROM Transcripts
            WHERE media_id = ?
            ORDER BY created_at DESC
            ''', (media_id,))
            return cursor.fetchall()
    except Exception as e:
        logging.error(f"Error in get_transcripts: {str(e)}")
        return []


#
# End of Functions to Compare Transcripts
#######################################################################################################################


#######################################################################################################################
#
# Functions to handle deletion of media items


def mark_as_trash(media_id: int) -> None:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Media 
            SET is_trash = 1, trash_date = ?
            WHERE id = ?
        """, (datetime.now(), media_id))
        conn.commit()


def restore_from_trash(media_id: int) -> None:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Media 
            SET is_trash = 0, trash_date = NULL
            WHERE id = ?
        """, (media_id,))
        conn.commit()


def get_trashed_items() -> List[Dict]:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, trash_date 
            FROM Media 
            WHERE is_trash = 1
            ORDER BY trash_date DESC
        """)
        return [{'id': row[0], 'title': row[1], 'trash_date': row[2]} for row in cursor.fetchall()]


def permanently_delete_item(media_id: int) -> None:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Media WHERE id = ?", (media_id,))
        cursor.execute("DELETE FROM MediaKeywords WHERE media_id = ?", (media_id,))
        cursor.execute("DELETE FROM MediaVersion WHERE media_id = ?", (media_id,))
        cursor.execute("DELETE FROM MediaModifications WHERE media_id = ?", (media_id,))
        cursor.execute("DELETE FROM media_fts WHERE rowid = ?", (media_id,))
        conn.commit()


def empty_trash(days_threshold: int) -> Tuple[int, int]:
    threshold_date = datetime.now() - timedelta(days=days_threshold)
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM Media 
            WHERE is_trash = 1 AND trash_date <= ?
        """, (threshold_date,))
        old_items = cursor.fetchall()

        for item in old_items:
            permanently_delete_item(item[0])

        cursor.execute("""
            SELECT COUNT(*) FROM Media 
            WHERE is_trash = 1 AND trash_date > ?
        """, (threshold_date,))
        remaining_items = cursor.fetchone()[0]

    return len(old_items), remaining_items


def user_delete_item(media_id: int, force: bool = False) -> str:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_trash, trash_date FROM Media WHERE id = ?", (media_id,))
        result = cursor.fetchone()

        if not result:
            return "Item not found."

        is_trash, trash_date = result

        if not is_trash:
            mark_as_trash(media_id)
            return "Item moved to trash."

        if force or (trash_date and (datetime.now() - trash_date).days >= 30):
            permanently_delete_item(media_id)
            return "Item permanently deleted."
        else:
            return "Item is already in trash. Use force=True to delete permanently before 30 days."

def get_media_transcripts(media_id):
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, whisper_model, transcription, created_at
            FROM Transcripts
            WHERE media_id = ?
            ORDER BY created_at DESC
            ''', (media_id,))
            results = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'whisper_model': row[1],
                    'content': row[2],
                    'created_at': row[3]
                }
                for row in results
            ]
    except Exception as e:
        logging.error(f"Error in get_media_transcripts: {str(e)}")
        return []

def get_specific_transcript(transcript_id: int) -> Dict:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, whisper_model, transcription, created_at
            FROM Transcripts
            WHERE id = ?
            ''', (transcript_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'whisper_model': result[1],
                    'content': result[2],
                    'created_at': result[3]
                }
            return {'error': f"No transcript found with ID {transcript_id}"}
    except Exception as e:
        logging.error(f"Error in get_specific_transcript: {str(e)}")
        return {'error': f"Error retrieving transcript: {str(e)}"}

def get_media_summaries(media_id: int) -> List[Dict]:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, summary, modification_date
            FROM MediaModifications
            WHERE media_id = ? AND summary IS NOT NULL
            ORDER BY modification_date DESC
            ''', (media_id,))
            results = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'content': row[1],
                    'created_at': row[2]
                }
                for row in results
            ]
    except Exception as e:
        logging.error(f"Error in get_media_summaries: {str(e)}")

def get_specific_summary(summary_id: int) -> Dict:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, summary, modification_date
            FROM MediaModifications
            WHERE id = ?
            ''', (summary_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'content': result[1],
                    'created_at': result[2]
                }
            return {'error': f"No summary found with ID {summary_id}"}
    except Exception as e:
        logging.error(f"Error in get_specific_summary: {str(e)}")
        return {'error': f"Error retrieving summary: {str(e)}"}

def get_media_prompts(media_id: int) -> List[Dict]:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, prompt, modification_date
            FROM MediaModifications
            WHERE media_id = ? AND prompt IS NOT NULL
            ORDER BY modification_date DESC
            ''', (media_id,))
            results = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'content': row[1],
                    'created_at': row[2]
                }
                for row in results
            ]
    except Exception as e:
        logging.error(f"Error in get_media_prompts: {str(e)}")
        return []

def get_specific_prompt(prompt_id: int) -> Dict:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT id, prompt, modification_date
            FROM MediaModifications
            WHERE id = ?
            ''', (prompt_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'content': result[1],
                    'created_at': result[2]
                }
            return {'error': f"No prompt found with ID {prompt_id}"}
    except Exception as e:
        logging.error(f"Error in get_specific_prompt: {str(e)}")
        return {'error': f"Error retrieving prompt: {str(e)}"}


def delete_specific_transcript(transcript_id: int) -> str:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM Transcripts WHERE id = ?', (transcript_id,))
            conn.commit()
            if cursor.rowcount > 0:
                return f"Transcript with ID {transcript_id} has been deleted successfully."
            else:
                return f"No transcript found with ID {transcript_id}."
    except Exception as e:
        logging.error(f"Error in delete_specific_transcript: {str(e)}")
        return f"Error deleting transcript: {str(e)}"

def delete_specific_summary(summary_id: int) -> str:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE MediaModifications SET summary = NULL WHERE id = ?', (summary_id,))
            conn.commit()
            if cursor.rowcount > 0:
                return f"Summary with ID {summary_id} has been deleted successfully."
            else:
                return f"No summary found with ID {summary_id}."
    except Exception as e:
        logging.error(f"Error in delete_specific_summary: {str(e)}")
        return f"Error deleting summary: {str(e)}"

def delete_specific_prompt(prompt_id: int) -> str:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE MediaModifications SET prompt = NULL WHERE id = ?', (prompt_id,))
            conn.commit()
            if cursor.rowcount > 0:
                return f"Prompt with ID {prompt_id} has been deleted successfully."
            else:
                return f"No prompt found with ID {prompt_id}."
    except Exception as e:
        logging.error(f"Error in delete_specific_prompt: {str(e)}")
        return f"Error deleting prompt: {str(e)}"

#
# End of Functions to handle deletion of media items
#######################################################################################################################
#
# Functions to manage document versions

def create_document_version(media_id: int, content: str) -> int:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Get the latest version number
            cursor.execute('''
                SELECT MAX(version_number) 
                FROM DocumentVersions 
                WHERE media_id = ?
            ''', (media_id,))

            latest_version = cursor.fetchone()[0] or 0
            new_version = latest_version + 1

            # Insert new version
            cursor.execute('''
                INSERT INTO DocumentVersions (media_id, version_number, content)
                VALUES (?, ?, ?)
            ''', (media_id, new_version, content))

            conn.commit()
            return new_version
    except sqlite3.Error as e:
        logging.error(f"Error creating document version: {e}")
        raise DatabaseError(f"Error creating document version: {e}")


def get_document_version(media_id: int, version_number: int = None) -> Dict[str, Any]:
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            if version_number is None:
                # Get the latest version
                cursor.execute('''
                    SELECT id, version_number, content, created_at
                    FROM DocumentVersions
                    WHERE media_id = ?
                    ORDER BY version_number DESC
                    LIMIT 1
                ''', (media_id,))
            else:
                cursor.execute('''
                    SELECT id, version_number, content, created_at
                    FROM DocumentVersions
                    WHERE media_id = ? AND version_number = ?
                ''', (media_id, version_number))

            result = cursor.fetchone()

            if result:
                return {
                    'id': result[0],
                    'version_number': result[1],
                    'content': result[2],
                    'created_at': result[3]
                }
            else:
                return {'error': f"No document version found for media_id {media_id}" + (f" and version_number {version_number}" if version_number is not None else "")}
    except sqlite3.Error as e:
        error_message = f"Error retrieving document version: {e}"
        logging.error(error_message)
        return {'error': error_message}

#
# End of Functions to manage document versions
#######################################################################################################################