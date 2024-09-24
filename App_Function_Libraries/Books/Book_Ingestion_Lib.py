# Book_Ingestion_Lib.py
#########################################
# Library to hold functions for ingesting book files.#
#
####################
# Function List
#
# 1. ingest_text_file(file_path, title=None, author=None, keywords=None):
# 2.
#
#
####################
#
# Import necessary libraries
import os
import re
from datetime import datetime
import logging

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub
#
# Import Local
from App_Function_Libraries.DB.DB_Manager import add_media_with_keywords
#
#######################################################################################################################
# Function Definitions
#



def read_epub(file_path):
    """Read and extract text from an EPUB file."""
    book = epub.read_epub(file_path)
    chapters = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            chapters.append(item.get_content())

    text = ""
    for html_content in chapters:
        soup = BeautifulSoup(html_content, 'html.parser')
        text += soup.get_text() + "\n\n"
    return text


# Ingest a text file into the database with Title/Author/Keywords
def extract_epub_metadata(content):
    title_match = re.search(r'Title:\s*(.*?)\n', content)
    author_match = re.search(r'Author:\s*(.*?)\n', content)

    title = title_match.group(1) if title_match else None
    author = author_match.group(1) if author_match else None

    return title, author


def ingest_text_file(file_path, title=None, author=None, keywords=None):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        # Check if it's a converted epub and extract metadata if so
        if 'epub_converted' in (keywords or ''):
            extracted_title, extracted_author = extract_epub_metadata(content)
            title = title or extracted_title
            author = author or extracted_author

        # If title is still not provided, use the filename without extension
        if not title:
            title = os.path.splitext(os.path.basename(file_path))[0]

        # If author is still not provided, set it to 'Unknown'
        if not author:
            author = 'Unknown'

        # If keywords are not provided, use a default keyword
        if not keywords:
            keywords = 'text_file,epub_converted'
        else:
            keywords = f'text_file,epub_converted,{keywords}'

        # Add the text file to the database
        add_media_with_keywords(
            url=file_path,
            title=title,
            media_type='document',
            content=content,
            keywords=keywords,
            prompt='No prompt for text files',
            summary='No summary for text files',
            transcription_model='None',
            author=author,
            ingestion_date=datetime.now().strftime('%Y-%m-%d')
        )

        return f"Text file '{title}' by {author} ingested successfully."
    except Exception as e:
        logging.error(f"Error ingesting text file: {str(e)}")
        return f"Error ingesting text file: {str(e)}"


def ingest_folder(folder_path, keywords=None):
    results = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.txt'):
            file_path = os.path.join(folder_path, filename)
            result = ingest_text_file(file_path, keywords=keywords)
            results.append(result)


def epub_to_markdown(epub_path):
    book = epub.read_epub(epub_path)
    markdown_content = "# Table of Contents\n\n"
    chapters = []

    # Extract and format the table of contents
    toc = book.toc
    for item in toc:
        if isinstance(item, tuple):
            section, children = item
            level = 1
            markdown_content += format_toc_item(section, level)
            for child in children:
                markdown_content += format_toc_item(child, level + 1)
        else:
            markdown_content += format_toc_item(item, 1)

    markdown_content += "\n---\n\n"

    # Process each chapter
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            chapter_content = item.get_content().decode('utf-8')
            soup = BeautifulSoup(chapter_content, 'html.parser')

            # Extract chapter title
            title = soup.find(['h1', 'h2', 'h3'])
            if title:
                chapter_title = title.get_text()
                markdown_content += f"# {chapter_title}\n\n"

            # Process chapter content
            for elem in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol']):
                if elem.name.startswith('h'):
                    level = int(elem.name[1])
                    markdown_content += f"{'#' * level} {elem.get_text()}\n\n"
                elif elem.name == 'p':
                    markdown_content += f"{elem.get_text()}\n\n"
                elif elem.name in ['ul', 'ol']:
                    for li in elem.find_all('li'):
                        markdown_content += f"- {li.get_text()}\n"
                    markdown_content += "\n"

            markdown_content += "---\n\n"

    return markdown_content


def format_toc_item(item, level):
    return f"{'  ' * (level - 1)}- [{item.title}](#{slugify(item.title)})\n"


def slugify(text):
    return re.sub(r'[\W_]+', '-', text.lower())

#
# End of Function Definitions
#######################################################################################################################
