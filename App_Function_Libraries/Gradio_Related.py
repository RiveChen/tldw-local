# Gradio_Related.py
#########################################
# Gradio UI Functions Library
# This library is used to hold all UI-related functions for Gradio.
# I fucking hate Gradio.
#
#####
# Functions:
#
# download_audio_file(url, save_path)
# process_audio(
# process_audio_file(audio_url, audio_file, whisper_model="small.en", api_name=None, api_key=None)
#
#
#########################################
#
# Built-In Imports
import base64
import glob
import html
import math
import re
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime
import json
import logging
import os.path
from pathlib import Path
import sqlite3
from time import sleep
from typing import Dict, List, Tuple, Optional
import traceback
from functools import wraps
#
# Import 3rd-Party Libraries
import pypandoc
import yt_dlp
import gradio as gr
from PIL import Image
from textstat import textstat
#
# Local Imports
from App_Function_Libraries.Article_Summarization_Lib import scrape_and_summarize_multiple
from App_Function_Libraries.Audio_Files import process_audio_files, process_podcast, download_youtube_audio
from App_Function_Libraries.Chat_related_functions import get_character_names, load_characters, save_character
from App_Function_Libraries.Chunk_Lib import improved_chunking_process
from App_Function_Libraries.LLM_API_Calls import chat_with_openai, chat_with_anthropic, \
    chat_with_cohere, chat_with_groq, chat_with_openrouter, chat_with_deepseek, chat_with_mistral, chat_with_vllm, \
    chat_with_huggingface
from App_Function_Libraries.LLM_API_Calls_Local import chat_with_llama, chat_with_kobold, chat_with_oobabooga, \
    chat_with_tabbyapi, chat_with_local_llm, chat_with_ollama, chat_with_aphrodite
from App_Function_Libraries.PDF_Ingestion_Lib import process_and_cleanup_pdf, extract_text_and_format_from_pdf, \
    extract_metadata_from_pdf
from App_Function_Libraries.Local_LLM_Inference_Engine_Lib import local_llm_gui_function
from App_Function_Libraries.Local_Summarization_Lib import summarize_with_llama, summarize_with_kobold, \
    summarize_with_oobabooga, summarize_with_tabbyapi, summarize_with_vllm, summarize_with_local_llm, \
    summarize_with_ollama
from App_Function_Libraries.RAG_Libary_2 import rag_search
from App_Function_Libraries.Summarization_General_Lib import summarize_with_openai, summarize_with_cohere, \
    summarize_with_anthropic, summarize_with_groq, summarize_with_openrouter, summarize_with_deepseek, \
    summarize_with_huggingface, perform_summarization, save_transcription_and_summary, \
    perform_transcription, summarize_chunk
from App_Function_Libraries.DB_Manager import update_media_content, list_prompts, search_and_display, db, DatabaseError, \
    fetch_prompt_details, keywords_browser_interface, add_keyword, delete_keyword, \
    export_keywords_to_csv, add_media_to_database, import_obsidian_note_to_db, add_prompt, \
    delete_chat_message, update_chat_message, add_chat_message, get_chat_messages, search_chat_conversations, \
    create_chat_conversation, save_chat_history_to_database, view_database, get_transcripts, get_trashed_items, \
    user_delete_item, empty_trash, create_automated_backup, backup_dir, db_path, add_or_update_prompt, \
    load_prompt_details, load_preset_prompts, insert_prompt_to_db, delete_prompt, search_and_display_items, \
    get_conversation_name, get_db_config
from App_Function_Libraries.Utils import sanitize_filename, extract_text_from_segments, create_download_directory, \
    convert_to_seconds, load_comprehensive_config, safe_read_file, downloaded_files, generate_unique_identifier, \
    generate_unique_filename
from App_Function_Libraries.Video_DL_Ingestion_Lib import parse_and_expand_urls, \
    generate_timestamped_url, extract_metadata, download_video

#
#######################################################################################################################
# Function Definitions
#

whisper_models = ["small", "medium", "small.en", "medium.en", "medium", "large", "large-v1", "large-v2", "large-v3",
                  "distil-large-v2", "distil-medium.en", "distil-small.en"]
custom_prompt_input = None
server_mode = False
share_public = False
custom_prompt_summarize_bulleted_notes = ("""
                    <s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
                        **Bulleted Note Creation Guidelines**

                        **Headings**:
                        - Based on referenced topics, not categories like quotes or terms
                        - Surrounded by **bold** formatting 
                        - Not listed as bullet points
                        - No space between headings and list items underneath

                        **Emphasis**:
                        - **Important terms** set in bold font
                        - **Text ending in a colon**: also bolded

                        **Review**:
                        - Ensure adherence to specified format
                        - Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]
                    """)


def gradio_download_youtube_video(url):
    try:
        # Determine ffmpeg path based on the operating system.
        ffmpeg_path = './Bin/ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract information about the video
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                sanitized_title = sanitize_filename(info_dict['title'])
                original_ext = info_dict['ext']

            # Setup the temporary filename
            temp_file_path = Path(temp_dir) / f"{sanitized_title}.{original_ext}"

            # Initialize yt-dlp with generic options and the output template
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'ffmpeg_location': ffmpeg_path,
                'outtmpl': str(temp_file_path),
                'noplaylist': True,
                'quiet': True
            }

            # Execute yt-dlp to download the video
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Final check to ensure file exists
            if not temp_file_path.exists():
                raise FileNotFoundError(f"Expected file was not found: {temp_file_path}")

            # Create a persistent directory for the download if it doesn't exist
            persistent_dir = Path("downloads")
            persistent_dir.mkdir(exist_ok=True)

            # Move the file from the temporary directory to the persistent directory
            persistent_file_path = persistent_dir / f"{sanitized_title}.{original_ext}"
            shutil.move(str(temp_file_path), str(persistent_file_path))

            # Add the file to the list of downloaded files
            downloaded_files.append(str(persistent_file_path))

            return str(persistent_file_path), f"Video downloaded successfully: {sanitized_title}.{original_ext}"
    except Exception as e:
        return None, f"Error downloading video: {str(e)}"


def format_transcription(content):
    # Replace '\n' with actual line breaks
    content = content.replace('\\n', '\n')
    # Split the content by newlines first
    lines = content.split('\n')
    formatted_lines = []
    for line in lines:
        # Add extra space after periods for better readability
        line = line.replace('.', '. ').replace('.  ', '. ')

        # Split into sentences using a more comprehensive regex
        sentences = re.split('(?<=[.!?]) +', line)

        # Trim whitespace from each sentence and add a line break
        formatted_sentences = [sentence.strip() for sentence in sentences if sentence.strip()]

        # Join the formatted sentences
        formatted_lines.append(' '.join(formatted_sentences))

    # Join the lines with HTML line breaks
    formatted_content = '<br>'.join(formatted_lines)

    return formatted_content


def format_file_path(file_path, fallback_path=None):
    if file_path and os.path.exists(file_path):
        logging.debug(f"File exists: {file_path}")
        return file_path
    elif fallback_path and os.path.exists(fallback_path):
        logging.debug(f"File does not exist: {file_path}. Returning fallback path: {fallback_path}")
        return fallback_path
    else:
        logging.debug(f"File does not exist: {file_path}. No fallback path available.")
        return None


def search_media(query, fields, keyword, page):
    try:
        results = search_and_display(query, fields, keyword, page)
        return results
    except Exception as e:
        logger = logging.getLogger()
        logger.error(f"Error searching media: {e}")
        return str(e)




# Sample data
prompts_category_1 = [
    "What are the key points discussed in the video?",
    "Summarize the main arguments made by the speaker.",
    "Describe the conclusions of the study presented."
]

prompts_category_2 = [
    "How does the proposed solution address the problem?",
    "What are the implications of the findings?",
    "Can you explain the theory behind the observed phenomenon?"
]

all_prompts = prompts_category_1 + prompts_category_2





# Handle prompt selection
def handle_prompt_selection(prompt):
    return f"You selected: {prompt}"

# FIXME - Dead code?
# def display_details(media_id):
#     if media_id:
#         details = display_item_details(media_id)
#         details_html = ""
#         for detail in details:
#             details_html += f"<h4>Prompt:</h4><p>{detail[0]}</p>"
#             details_html += f"<h4>Summary:</h4><p>{detail[1]}</p>"
#
#             # Format the transcription
#             formatted_transcription = format_transcription(detail[2])
#
#             # Use <pre> tag with style for better formatting
#             details_html += f"<h4>Transcription:</h4><pre style='white-space: pre-wrap; word-wrap: break-word;'>{formatted_transcription}</pre><hr>"
#
#         return details_html
#     return "No details available."


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
        return "", "", ""  # Return empty strings if there's an error


def browse_items(search_query, search_type):
    if search_type == 'Keyword':
        results = fetch_items_by_keyword(search_query)
    elif search_type == 'Content':
        results = fetch_items_by_content(search_query)
    else:
        results = fetch_items_by_title_or_url(search_query, search_type)
    return results


def update_dropdown(search_query, search_type):
    results = browse_items(search_query, search_type)
    item_options = [f"{item[1]} ({item[2]})" for item in results]
    new_item_mapping = {f"{item[1]} ({item[2]})": item[0] for item in results}
    print(f"Debug - Update Dropdown - New Item Mapping: {new_item_mapping}")
    return gr.update(choices=item_options), new_item_mapping



def get_media_id(selected_item, item_mapping):
    return item_mapping.get(selected_item)


def update_detailed_view(item, item_mapping):
    # Function to update the detailed view based on selected item
    if item:
        item_id = item_mapping.get(item)
        if item_id:
            content, prompt, summary = fetch_item_details(item_id)
            if content or prompt or summary:
                details_html = "<h4>Details:</h4>"
                if prompt:
                    formatted_prompt = format_transcription(prompt)
                    details_html += f"<h4>Prompt:</h4>{formatted_prompt}</p>"
                if summary:
                    formatted_summary = format_transcription(summary)
                    details_html += f"<h4>Summary:</h4>{formatted_summary}</p>"
                # Format the transcription content for better readability
                formatted_content = format_transcription(content)
                #content_html = f"<h4>Transcription:</h4><div style='white-space: pre-wrap;'>{content}</div>"
                content_html = f"<h4>Transcription:</h4><div style='white-space: pre-wrap;'>{formatted_content}</div>"
                return details_html, content_html
            else:
                return "No details available.", "No details available."
        else:
            return "No item selected", "No item selected"
    else:
        return "No item selected", "No item selected"


def format_content(content):
    # Format content using markdown
    formatted_content = f"```\n{content}\n```"
    return formatted_content


def update_prompt_dropdown():
    prompt_names = list_prompts()
    return gr.update(choices=prompt_names)


def display_prompt_details(selected_prompt):
    if selected_prompt:
        prompts = update_user_prompt(selected_prompt)
        if prompts["title"]:  # Check if we have any details
            details_str = f"<h4>Details:</h4><p>{prompts['details']}</p>"
            system_str = f"<h4>System:</h4><p>{prompts['system_prompt']}</p>"
            user_str = f"<h4>User:</h4><p>{prompts['user_prompt']}</p>" if prompts['user_prompt'] else ""
            return details_str + system_str + user_str
    return "No details available."

def search_media_database(query: str) -> List[Tuple[int, str, str]]:
    return browse_items(query, 'Title')


def load_media_content(media_id: int) -> dict:
    try:
        print(f"Debug - Load Media Content - Media ID: {media_id}")
        item_details = fetch_item_details(media_id)
        print(f"Debug - Load Media Content - Item Details: \n\n{item_details}\n\n\n\n")

        if isinstance(item_details, tuple) and len(item_details) == 3:
            content, prompt, summary = item_details
        else:
            print(f"Debug - Load Media Content - Unexpected item_details format: \n\n{item_details}\n\n\n\n")
            content, prompt, summary = "", "", ""

        return {
            "content": content or "No content available",
            "prompt": prompt or "No prompt available",
            "summary": summary or "No summary available"
        }
    except Exception as e:
        print(f"Debug - Load Media Content - Error: {str(e)}")
        return {"content": "", "prompt": "", "summary": ""}


def error_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_message = f"Error in {func.__name__}: {str(e)}"
            logging.error(f"{error_message}\n{traceback.format_exc()}")
            return {"error": error_message, "details": traceback.format_exc()}
    return wrapper


def create_chunking_inputs():
    chunk_text_by_words_checkbox = gr.Checkbox(label="Chunk Text by Words", value=False, visible=True)
    max_words_input = gr.Number(label="Max Words", value=300, precision=0, visible=True)
    chunk_text_by_sentences_checkbox = gr.Checkbox(label="Chunk Text by Sentences", value=False, visible=True)
    max_sentences_input = gr.Number(label="Max Sentences", value=10, precision=0, visible=True)
    chunk_text_by_paragraphs_checkbox = gr.Checkbox(label="Chunk Text by Paragraphs", value=False, visible=True)
    max_paragraphs_input = gr.Number(label="Max Paragraphs", value=5, precision=0, visible=True)
    chunk_text_by_tokens_checkbox = gr.Checkbox(label="Chunk Text by Tokens", value=False, visible=True)
    max_tokens_input = gr.Number(label="Max Tokens", value=1000, precision=0, visible=True)
    gr_semantic_chunk_long_file = gr.Checkbox(label="Semantic Chunking by Sentence similarity", value=False, visible=True)
    gr_semantic_chunk_long_file_size = gr.Number(label="Max Chunk Size", value=2000, visible=True)
    gr_semantic_chunk_long_file_overlap = gr.Number(label="Max Chunk Overlap Size", value=100, visible=True)
    return [chunk_text_by_words_checkbox, max_words_input, chunk_text_by_sentences_checkbox, max_sentences_input,
            chunk_text_by_paragraphs_checkbox, max_paragraphs_input, chunk_text_by_tokens_checkbox, max_tokens_input]








#
# End of miscellaneous unsorted functions
#######################################################################################################################
#
# Start of Video/Audio Transcription and Summarization Functions

def create_introduction_tab():
    with (gr.TabItem("Introduction")):
        db_config = get_db_config()
        db_type = db_config['type']
        gr.Markdown(f"# tldw: Your LLM-powered Research Multi-tool (Using {db_type.capitalize()} Database)")
        with gr.Row():
            with gr.Column():
                gr.Markdown("""### What can it do?
                - Transcribe and summarize videos from URLs/Local files
                - Transcribe and Summarize Audio files/Podcasts (URL/local file)
                - Summarize articles from URLs/Local notes
                - Ingest and summarize books(epub/PDF)
                - Ingest and summarize research papers (PDFs - WIP)
                - Search and display ingested content + summaries
                - Create and manage custom prompts
                - Chat with an LLM of your choice to generate content using the selected item + Prompts
                - Keyword support for content search and display
                - Export keywords/items to markdown/CSV(csv is wip)
                - Import existing notes from Obsidian to the database (Markdown/txt files or a zip containing a collection of files)
                - View and manage chat history
                - Writing Tools: Grammar & Style check, Tone Analyzer & Editor, more planned...
                - RAG (Retrieval-Augmented Generation) support for content generation(think about asking questions about your entire library of items)
                - More features planned...
                - All powered by your choice of LLM. 
                    - Currently supports: Local-LLM(llamafile-server), OpenAI, Anthropic, Cohere, Groq, DeepSeek, OpenRouter, Llama.cpp, Kobold, Ooba, Tabbyapi, VLLM and more to come...
                - All data is stored locally in a SQLite database for easy access and management.
                - No trackers (Gradio has some analytics but it's disabled here...)
                - No ads, no tracking, no BS. Just you and your content.
                - Open-source and free to use. Contributions welcome!
                - If you have any thoughts or feedback, please let me know on github or via email.
                """)
                gr.Markdown("""Follow this project at [tl/dw: Too Long, Didn't Watch - Your Personal Research Multi-Tool - GitHub](https://github.com/rmusser01/tldw)""")
            with gr.Column():
                gr.Markdown("""### How to use:
                ##### Quick Start: Just click on the appropriate tab for what you're trying to do and fill in the required fields. Click "Process <video/audio/article/etc>" and wait for the results.
                #### Simple Instructions
                - Basic Usage:
                    - If you don't have an API key/don't know what an LLM is/don't know what an API key is, please look further down the page for information on getting started.
                    - If you want summaries/chat with an LLM, you'll need:
                        1. An API key for the LLM API service you want to use, or,
                        2. A local inference server running an LLM (like llamafile-server/llama.cpp - for instructions on how to do so see the projects README or below), or,
                        3. A "local" inference server you have access to running an LLM.
                    - If you just want transcriptions you can ignore the above.
                    - Select the tab for the task you want to perform
                    - Fill in the required fields
                    - Click the "Process" button
                    - Wait for the results to appear
                    - Download the results if needed
                    - Repeat as needed
                    - As of writing this, the UI is still a work in progress.
                    - That being said, I plan to replace it all eventually. In the meantime, please have patience.
                    - The UI is divided into tabs for different tasks.
                    - Each tab has a set of fields that you can fill in to perform the task.
                    - Some fields are mandatory, some are optional.
                    - The fields are mostly self-explanatory, but I will try to add more detailed instructions as I go.
                #### Detailed Usage:
                - There are 8 Top-level tabs in the UI. Each tab has a specific set of tasks that you can perform by selecting one of the 'sub-tabs' made available by clicking on the top tab.
                - The tabs are as follows:
                    1. Transcription / Summarization / Ingestion - This tab is for processing videos, audio files, articles, books, and PDFs/office docs.
                    2. Search / Detailed View - This tab is for searching and displaying content from the database. You can also view detailed information about the selected item.
                    3. Chat with an LLM - This tab is for chatting with an LLM to generate content based on the selected item and prompts.
                    4. Edit Existing Items - This tab is for editing existing items in the database (Prompts + ingested items).
                    5. Writing Tools - This tab is for using various writing tools like Grammar & Style check, Tone Analyzer & Editor, etc.
                    6. Keywords - This tab is for managing keywords for content search and display.
                    7. Import/Export - This tab is for importing notes from Obsidian and exporting keywords/items to markdown/CSV.
                    8. Utilities - This tab contains some random utilities that I thought might be useful.
                - Each sub-tab is responsible for that set of functionality. This is reflected in the codebase as well, where I have split the functionality into separate files for each tab/larger goal.
                """)
        with gr.Row():
            gr.Markdown("""### HELP! I don't know what any of this this shit is!
            ### DON'T PANIC
            #### Its ok, you're not alone, most people have no clue what any of this stuff is. 
            - So let's try and fix that.
            
            #### Introduction to LLMs:
            - Non-Technical introduction to Generative AI and LLMs: https://paruir.medium.com/understanding-generative-ai-and-llms-a-non-technical-overview-part-1-788c0eb0dd64
            - Google's Intro to LLMs: https://developers.google.com/machine-learning/resources/intro-llms#llm_considerations
            - LLMs 101(coming from a tech background): https://vinija.ai/models/LLM/
            - LLM Fundamentals / LLM Scientist / LLM Engineer courses(Free): https://github.com/mlabonne/llm-course

            #### Various Phrases & Terms to know
            - **LLM** - Large Language Model - A type of neural network that can generate human-like text.
            - **API** - Application Programming Interface - A set of rules and protocols that allows one software application to communicate with another. 
                * Think of it like a post address for a piece of software. You can send messages to and from it.
            - **API Key** - A unique identifier that is used to authenticate a user, developer, or calling program to an API.
                * Like the key to a post office box. You need it to access the contents.
            - **GUI** - Graphical User Interface - the thing facilitating your interact with this application.
            - **DB** - Database
            - **Prompt Engineering** - The process of designing prompts that are used to guide the output of a language model. Is a meme but also very much not.
            - **Quantization** - The process of converting a continuous range of values into a finite range of discrete values.
            - **GGUF Files** - GGUF is a binary format that is designed for fast loading and saving of models, and for ease of reading. Models are traditionally developed using PyTorch or another framework, and then converted to GGUF for use in GGML. https://github.com/ggerganov/ggml/blob/master/docs/gguf.md
            - **Inference Engine** - A software system that is designed to execute a model that has been trained by a machine learning algorithm. Llama.cpp and Kobold.cpp are examples of inference engines.
            - **Abliteration** - https://huggingface.co/blog/mlabonne/abliteration
            """)
        with gr.Row():
            gr.Markdown("""### Ok cool, but how do I get started? I don't have an API key or a local server running...
                #### Great, glad you asked! Getting Started:
                - **Getting an API key for a commercial services provider:
                    - **OpenAI:**
                        * https://platform.openai.com/docs/quickstart
                    - **Anthropic:**
                        * https://docs.anthropic.com/en/api/getting-started
                    - **Cohere:**
                        * https://docs.cohere.com/
                        * They offer 1k free requests a month(up to 1million tokens total I think?), so you can try it out without paying.
                    - **Groq:**
                        * https://console.groq.com/keys
                        * Offer an account with free credits to try out their service. No idea how much you get.
                    - **DeepSeek:**
                        * https://platform.deepseek.com/ (Chinese-hosted/is in english)
                    - **OpenRouter:**
                        * https://openrouter.ai/
                    - **Mistral:**
                        * https://console.mistral.ai/
                - **Choosing a Model to download**
                    - You'll first need to select a model you want to use with the server.
                        - Keep in mind that the model you select will determine the quality of the output you get, and that models run fastest when offloaded fully to your GPU.
                        * So this means that you can run a large model (Command-R) on CPU+System RAM, but you're gonna see a massive performance hit. Not saying its unusable, but it's not ideal.
                        * With that in mind, I would recommend an abliterated version of Meta's Llama3.1 model for most tasks. (Abliterated since it won't refuse requests)
                        * I say this because of the general quality of the model + it's context size.
                        * You can find the model here: https://huggingface.co/mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF
                        * And the Q8 quant(total size 8.6GB): https://huggingface.co/mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF/resolve/main/meta-llama-3.1-8b-instruct-abliterated.Q8_0.gguf?download=true
                - **Local Inference Server:**
                    - **Llamafile-Server (wrapper for llama.cpp):**
                        * Run this script with the `--local_llm` argument next time, and you'll be walked through setting up a local instance of llamafile-server.
                    - **Llama.cpp Inference Engine:**
                        * Download the latest release for your platform here: https://github.com/ggerganov/llama.cpp/releases
                        * Windows: `llama-<release_number>-bin-win-cuda-cu<11.7.1 or 12.2.0 - version depends on installed cuda>-x64.zip`
                            * Run it: `llama-server.exe --model <path_to_model> -ctx 8192 -ngl 999` 
                                - `-ctx 8192` sets the context size to 8192 tokens, `-ngl 999` sets the number of layers to offload to the GPU to 999. (essentially ensuring we only use our GPU and not CPU for processing)
                        * Macos: `llama-<release_number>-bin-macos-arm64.zip - for Apple Silicon / `llama-<release_number>-bin-macos-x64.zip` - for Intel Macs
                            * Run it: `llama-server --model <path_to_model> -ctx 8192 -ngl 999` 
                                - `-ctx 8192` sets the context size to 8192 tokens, `-ngl 999` sets the number of layers to offload to the GPU to 999. (essentially ensuring we only use our GPU and not CPU for processing)
                        * Linux: You can probably figure it out.
                    - **Kobold.cpp Server:**
                        1. Download from here: https://github.com/LostRuins/koboldcpp/releases/latest
                        2. `Double click KoboldCPP.exe and select model OR run "KoboldCPP.exe --help" in CMD prompt to get command line arguments for more control.`
                        3. `Generally you don't have to change much besides the Presets and GPU Layers. Run with CuBLAS or CLBlast for GPU acceleration.`
                        4. `Select your GGUF or GGML model you downloaded earlier, and connect to the displayed URL once it finishes loading.`
                    - **Linux**
                        1. `On Linux, we provide a koboldcpp-linux-x64 PyInstaller prebuilt binary on the releases page for modern systems. Simply download and run the binary.`
                            * Alternatively, you can also install koboldcpp to the current directory by running the following terminal command: `curl -fLo koboldcpp https://github.com/LostRuins/koboldcpp/releases/latest/download/koboldcpp-linux-x64 && chmod +x koboldcpp`
                        2. When you can't use the precompiled binary directly, we provide an automated build script which uses conda to obtain all dependencies, and generates (from source) a ready-to-use a pyinstaller binary for linux users. Simply execute the build script with `./koboldcpp.sh dist` and run the generated binary.
            """)

def create_video_transcription_tab():
    with (gr.TabItem("Video Transcription + Summarization")):
        gr.Markdown("# Transcribe & Summarize Videos from URLs")
        with gr.Row():
            gr.Markdown("""Follow this project at [tldw - GitHub](https://github.com/rmusser01/tldw)""")
        with gr.Row():
            gr.Markdown("""If you're wondering what all this is, please see the 'Introduction/Help' tab up above for more detailed information and how to obtain an API Key.""")
        with gr.Row():
            with gr.Column():
                url_input = gr.Textbox(label="URL(s) (Mandatory)",
                                       placeholder="Enter video URLs here, one per line. Supports YouTube, Vimeo, other video sites and Youtube playlists.",
                                       lines=5)
                video_file_input = gr.File(label="Upload Video File (Optional)", file_types=["video/*"])
                diarize_input = gr.Checkbox(label="Enable Speaker Diarization", value=False)
                whisper_model_input = gr.Dropdown(choices=whisper_models, value="medium", label="Whisper Model")

                with gr.Row():
                    custom_prompt_checkbox = gr.Checkbox(label="Use a Custom Prompt",
                                                     value=False,
                                                     visible=True)
                    preset_prompt_checkbox = gr.Checkbox(label="Use a pre-set Prompt",
                                                     value=False,
                                                     visible=True)
                with gr.Row():
                    preset_prompt = gr.Dropdown(label="Select Preset Prompt",
                                                choices=load_preset_prompts(),
                                                visible=False)
                with gr.Row():
                    custom_prompt_input = gr.Textbox(label="Custom Prompt",
                                                     placeholder="Enter custom prompt here",
                                                     lines=3,
                                                     visible=False)
                with gr.Row():
                    system_prompt_input = gr.Textbox(label="System Prompt",
                                                     value="""<s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
**Bulleted Note Creation Guidelines**

**Headings**:
- Based on referenced topics, not categories like quotes or terms
- Surrounded by **bold** formatting 
- Not listed as bullet points
- No space between headings and list items underneath

**Emphasis**:
- **Important terms** set in bold font
- **Text ending in a colon**: also bolded

**Review**:
- Ensure adherence to specified format
- Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]
""",
                                                     lines=3,
                                                     visible=False,
                                                     interactive=True)
                custom_prompt_checkbox.change(
                    fn=lambda x: (gr.update(visible=x), gr.update(visible=x)),
                    inputs=[custom_prompt_checkbox],
                    outputs=[custom_prompt_input, system_prompt_input]
                )
                preset_prompt_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[preset_prompt_checkbox],
                    outputs=[preset_prompt]
                )

                def update_prompts(preset_name):
                    prompts = update_user_prompt(preset_name)
                    return (
                        gr.update(value=prompts["user_prompt"], visible=True),
                        gr.update(value=prompts["system_prompt"], visible=True)
                    )

                preset_prompt.change(
                    update_prompts,
                    inputs=preset_prompt,
                    outputs=[custom_prompt_input, system_prompt_input]
                )

                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "ollama", "HuggingFace"],
                    value=None, label="API Name (Mandatory)")
                api_key_input = gr.Textbox(label="API Key (Mandatory)", placeholder="Enter your API key here", type="password")
                keywords_input = gr.Textbox(label="Keywords", placeholder="Enter keywords here (comma-separated)",
                                            value="default,no_keyword_set")
                batch_size_input = gr.Slider(minimum=1, maximum=10, value=1, step=1,
                                             label="Batch Size (Number of videos to process simultaneously)")
                timestamp_option = gr.Radio(choices=["Include Timestamps", "Exclude Timestamps"],
                                            value="Include Timestamps", label="Timestamp Option")
                keep_original_video = gr.Checkbox(label="Keep Original Video", value=False)
                # First, create a checkbox to toggle the chunking options
                chunking_options_checkbox = gr.Checkbox(label="Show Chunking Options", value=False)
                summarize_recursively = gr.Checkbox(label="Enable Recursive Summarization", value=False)
                use_cookies_input = gr.Checkbox(label="Use cookies for authenticated download", value=False)
                use_time_input = gr.Checkbox(label="Use Start and End Time", value=False)

                with gr.Row(visible=False) as time_input_box:
                    gr.Markdown("### Start and End time")
                    with gr.Column():
                        start_time_input = gr.Textbox(label="Start Time (Optional)",
                                              placeholder="e.g., 1:30 or 90 (in seconds)")
                        end_time_input = gr.Textbox(label="End Time (Optional)", placeholder="e.g., 5:45 or 345 (in seconds)")

                use_time_input.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[use_time_input],
                    outputs=[time_input_box]
                )

                cookies_input = gr.Textbox(
                    label="User Session Cookies",
                    placeholder="Paste your cookies here (JSON format)",
                    lines=3,
                    visible=False
                )

                use_cookies_input.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[use_cookies_input],
                    outputs=[cookies_input]
                )
                # Then, create a Box to group the chunking options
                with gr.Row(visible=False) as chunking_options_box:
                    gr.Markdown("### Chunking Options")
                    with gr.Column():
                        chunk_method = gr.Dropdown(choices=['words', 'sentences', 'paragraphs', 'tokens'],
                                                   label="Chunking Method")
                        max_chunk_size = gr.Slider(minimum=100, maximum=1000, value=300, step=50, label="Max Chunk Size")
                        chunk_overlap = gr.Slider(minimum=0, maximum=100, value=0, step=10, label="Chunk Overlap")
                        use_adaptive_chunking = gr.Checkbox(label="Use Adaptive Chunking (Adjust chunking based on text complexity)")
                        use_multi_level_chunking = gr.Checkbox(label="Use Multi-level Chunking")
                        chunk_language = gr.Dropdown(choices=['english', 'french', 'german', 'spanish'],
                                                     label="Chunking Language")

                # Add JavaScript to toggle the visibility of the chunking options box
                chunking_options_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[chunking_options_checkbox],
                    outputs=[chunking_options_box]
                )
                process_button = gr.Button("Process Videos")

            with gr.Column():
                progress_output = gr.Textbox(label="Progress")
                error_output = gr.Textbox(label="Errors", visible=False)
                results_output = gr.HTML(label="Results")
                download_transcription = gr.File(label="Download All Transcriptions as JSON")
                download_summary = gr.File(label="Download All Summaries as Text")

            @error_handler
            def process_videos_with_error_handling(inputs, start_time, end_time, diarize, whisper_model,
                                                   custom_prompt_checkbox, custom_prompt, chunking_options_checkbox,
                                                   chunk_method, max_chunk_size, chunk_overlap, use_adaptive_chunking,
                                                   use_multi_level_chunking, chunk_language, api_name,
                                                   api_key, keywords, use_cookies, cookies, batch_size,
                                                   timestamp_option, keep_original_video, summarize_recursively,
                                                   progress: gr.Progress = gr.Progress()) -> tuple:
                try:
                    logging.info("Entering process_videos_with_error_handling")
                    logging.info(f"Received inputs: {inputs}")

                    if not inputs:
                        raise ValueError("No inputs provided")

                    logging.debug("Input(s) is(are) valid")

                    # Ensure batch_size is an integer
                    try:
                        batch_size = int(batch_size)
                    except (ValueError, TypeError):
                        batch_size = 1  # Default to processing one video at a time if invalid

                    # Separate URLs and local files
                    urls = [input for input in inputs if
                            isinstance(input, str) and input.startswith(('http://', 'https://'))]
                    local_files = [input for input in inputs if
                                   isinstance(input, str) and not input.startswith(('http://', 'https://'))]

                    # Parse and expand URLs if there are any
                    expanded_urls = parse_and_expand_urls(urls) if urls else []

                    valid_local_files = []
                    invalid_local_files = []

                    for file_path in local_files:
                        if os.path.exists(file_path):
                            valid_local_files.append(file_path)
                        else:
                            invalid_local_files.append(file_path)
                            error_message = f"Local file not found: {file_path}"
                            logging.error(error_message)

                    if invalid_local_files:
                        logging.warning(f"Found {len(invalid_local_files)} invalid local file paths")
                        # FIXME - Add more complete error handling for invalid local files

                    all_inputs = expanded_urls + valid_local_files
                    logging.info(f"Total valid inputs to process: {len(all_inputs)} "
                                 f"({len(expanded_urls)} URLs, {len(valid_local_files)} local files)")

                    all_inputs = expanded_urls + local_files
                    logging.info(f"Total inputs to process: {len(all_inputs)}")
                    results = []
                    errors = []
                    results_html = ""
                    all_transcriptions = {}
                    all_summaries = ""

                    for i in range(0, len(all_inputs), batch_size):
                        batch = all_inputs[i:i + batch_size]
                        batch_results = []

                        for input_item in batch:
                            try:
                                start_seconds = convert_to_seconds(start_time)
                                end_seconds = convert_to_seconds(end_time) if end_time else None

                                logging.info(f"Attempting to extract metadata for {input_item}")

                                if input_item.startswith(('http://', 'https://')):
                                    logging.info(f"Attempting to extract metadata for URL: {input_item}")
                                    video_metadata = extract_metadata(input_item, use_cookies, cookies)
                                    if not video_metadata:
                                        raise ValueError(f"Failed to extract metadata for {input_item}")
                                else:
                                    logging.info(f"Processing local file: {input_item}")
                                    video_metadata = {"title": os.path.basename(input_item), "url": input_item}

                                chunk_options = {
                                    'method': chunk_method,
                                    'max_size': max_chunk_size,
                                    'overlap': chunk_overlap,
                                    'adaptive': use_adaptive_chunking,
                                    'multi_level': use_multi_level_chunking,
                                    'language': chunk_language
                                } if chunking_options_checkbox else None

                                if custom_prompt_checkbox:
                                    custom_prompt = custom_prompt
                                else:
                                    custom_prompt = ("""
                                    <s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
                                        **Bulleted Note Creation Guidelines**
                                        
                                        **Headings**:
                                        - Based on referenced topics, not categories like quotes or terms
                                        - Surrounded by **bold** formatting 
                                        - Not listed as bullet points
                                        - No space between headings and list items underneath
                                        
                                        **Emphasis**:
                                        - **Important terms** set in bold font
                                        - **Text ending in a colon**: also bolded
                                        
                                        **Review**:
                                        - Ensure adherence to specified format
                                        - Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]
                                    """)

                                logging.debug("Gradio_Related.py: process_url_with_metadata being called")
                                result = process_url_with_metadata(
                                    input_item, 2, whisper_model,
                                    custom_prompt,
                                    start_seconds, api_name, api_key,
                                    False, False, False, False, 0.01, None, keywords, None, diarize,
                                    end_time=end_seconds,
                                    include_timestamps=(timestamp_option == "Include Timestamps"),
                                    metadata=video_metadata,
                                    use_chunking=chunking_options_checkbox,
                                    chunk_options=chunk_options,
                                    keep_original_video=keep_original_video,
                                    current_whisper_model=whisper_model,
                                )

                                if result[0] is None:
                                    error_message = "Processing failed without specific error"
                                    batch_results.append(
                                        (input_item, error_message, "Error", video_metadata, None, None))
                                    errors.append(f"Error processing {input_item}: {error_message}")
                                else:
                                    url, transcription, summary, json_file, summary_file, result_metadata = result
                                    if transcription is None:
                                        error_message = f"Processing failed for {input_item}: Transcription is None"
                                        batch_results.append(
                                            (input_item, error_message, "Error", result_metadata, None, None))
                                        errors.append(error_message)
                                    else:
                                        batch_results.append(
                                            (input_item, transcription, "Success", result_metadata, json_file,
                                             summary_file))


                            except Exception as e:
                                error_message = f"Error processing {input_item}: {str(e)}"
                                logging.error(error_message, exc_info=True)
                                batch_results.append((input_item, error_message, "Error", {}, None, None))
                                errors.append(error_message)

                        results.extend(batch_results)
                        logging.debug(f"Processed {len(batch_results)} videos in batch")
                        if isinstance(progress, gr.Progress):
                            progress((i + len(batch)) / len(all_inputs),
                                     f"Processed {i + len(batch)}/{len(all_inputs)} videos")

                    # Generate HTML for results
                    logging.debug(f"Generating HTML for {len(results)} results")
                    for url, transcription, status, metadata, json_file, summary_file in results:
                        if status == "Success":
                            title = metadata.get('title', 'Unknown Title')

                            # Check if transcription is a string (which it should be now)
                            if isinstance(transcription, str):
                                # Split the transcription into metadata and actual transcription
                                parts = transcription.split('\n\n', 1)
                                if len(parts) == 2:
                                    metadata_text, transcription_text = parts
                                else:
                                    metadata_text = "Metadata not found"
                                    transcription_text = transcription
                            else:
                                metadata_text = "Metadata format error"
                                transcription_text = "Transcription format error"

                            summary = safe_read_file(summary_file) if summary_file else "No summary available"

                            # FIXME - Add to other functions that generate HTML
                            # Format the transcription
                            formatted_transcription = format_transcription(transcription_text)
                            # Format the summary
                            formatted_summary = format_transcription(summary)

                            results_html += f"""
                            <div class="result-box">
                                <gradio-accordion>
                                    <gradio-accordion-item label="{title}">
                                        <p><strong>URL:</strong> <a href="{url}" target="_blank">{url}</a></p>
                                        <h4>Metadata:</h4>
                                        <pre>{metadata_text}</pre>
                                        <h4>Transcription:</h4>
                                        <div class="transcription" style="white-space: pre-wrap; word-wrap: break-word;">
                                            {formatted_transcription}
                                        </div>
                                        <h4>Summary:</h4>
                                        <div class="summary">{formatted_summary}</div>
                                    </gradio-accordion-item>
                                </gradio-accordion>
                            </div>
                            """
                            logging.debug(f"Transcription for {url}: {transcription[:200]}...")
                            all_transcriptions[url] = transcription
                            all_summaries += f"Title: {title}\nURL: {url}\n\n{metadata_text}\n\nTranscription:\n{transcription_text}\n\nSummary:\n{summary}\n\n---\n\n"
                        else:
                            results_html += f"""
                            <div class="result-box error">
                                <h3>Error processing {url}</h3>
                                <p>{transcription}</p>
                            </div>
                            """

                    # Save all transcriptions and summaries to files
                    logging.debug("Saving all transcriptions and summaries to files")
                    with open('all_transcriptions.json', 'w', encoding='utf-8') as f:
                        json.dump(all_transcriptions, f, indent=2, ensure_ascii=False)

                    with open('all_summaries.txt', 'w', encoding='utf-8') as f:
                        f.write(all_summaries)

                    error_summary = "\n".join(errors) if errors else "No errors occurred."

                    total_inputs = len(all_inputs)
                    return (
                        f"Processed {total_inputs} videos. {len(errors)} errors occurred.",
                        error_summary,
                        results_html,
                        'all_transcriptions.json',
                        'all_summaries.txt'
                    )
                except Exception as e:
                    logging.error(f"Unexpected error in process_videos_with_error_handling: {str(e)}", exc_info=True)
                    return (
                        f"An unexpected error occurred: {str(e)}",
                        str(e),
                        "<div class='result-box error'><h3>Unexpected Error</h3><p>" + str(e) + "</p></div>",
                        None,
                        None
                    )

            def process_videos_wrapper(url_input, video_file, start_time, end_time, diarize, whisper_model,
                                       custom_prompt_checkbox, custom_prompt, chunking_options_checkbox,
                                       chunk_method, max_chunk_size, chunk_overlap, use_adaptive_chunking,
                                       use_multi_level_chunking, chunk_language, summarize_recursively, api_name,
                                       api_key, keywords, use_cookies, cookies, batch_size,
                                       timestamp_option, keep_original_video):
                try:
                    logging.info("process_videos_wrapper(): process_videos_wrapper called")

                    # Define file paths
                    transcriptions_file = os.path.join('all_transcriptions.json')
                    summaries_file = os.path.join('all_summaries.txt')

                    # Delete existing files if they exist
                    for file_path in [transcriptions_file, summaries_file]:
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                logging.info(f"Deleted existing file: {file_path}")
                        except Exception as e:
                            logging.warning(f"Failed to delete file {file_path}: {str(e)}")

                    # Handle both URL input and file upload
                    inputs = []
                    if url_input:
                        inputs.extend([url.strip() for url in url_input.split('\n') if url.strip()])
                    if video_file is not None:
                        # Assuming video_file is a file object with a 'name' attribute
                        inputs.append(video_file.name)

                    if not inputs:
                        raise ValueError("No input provided. Please enter URLs or upload a video file.")
                    try:
                        result = process_videos_with_error_handling(
                            inputs, start_time, end_time, diarize, whisper_model,
                            custom_prompt_checkbox, custom_prompt, chunking_options_checkbox,
                            chunk_method, max_chunk_size, chunk_overlap, use_adaptive_chunking,
                            use_multi_level_chunking, chunk_language, api_name,
                            api_key, keywords, use_cookies, cookies, batch_size,
                            timestamp_option, keep_original_video, summarize_recursively
                        )
                    except Exception as e:
                        logging.error(f"process_videos_wrapper(): Error in process_videos_with_error_handling: {str(e)}", exc_info=True)

                    logging.info("process_videos_wrapper(): process_videos_with_error_handling completed")

                    # Ensure that result is a tuple with 5 elements
                    if not isinstance(result, tuple) or len(result) != 5:
                        raise ValueError(
                            f"process_videos_wrapper(): Expected 5 outputs, but got {len(result) if isinstance(result, tuple) else 1}")

                    return result
                except Exception as e:
                    logging.error(f"process_videos_wrapper(): Error in process_videos_wrapper: {str(e)}", exc_info=True)
                    # Return a tuple with 5 elements in case of any error
                    return (
                        # progress_output
                        f"process_videos_wrapper(): An error occurred: {str(e)}",
                        # error_output
                        str(e),
                        # results_output
                        f"<div class='error'>Error: {str(e)}</div>",
                        # download_transcription
                        None,
                        # download_summary
                        None
                    )

            # FIXME - remove dead args for process_url_with_metadata
            @error_handler
            def process_url_with_metadata(input_item, num_speakers, whisper_model, custom_prompt, offset, api_name, api_key,
                                          vad_filter, download_video_flag, download_audio, rolling_summarization,
                                          detail_level, question_box, keywords, local_file_path, diarize, end_time=None,
                                          include_timestamps=True, metadata=None, use_chunking=False,
                                          chunk_options=None, keep_original_video=False, current_whisper_model="Blank"):

                try:
                    logging.info(f"Starting process_url_metadata for URL: {input_item}")
                    # Create download path
                    download_path = create_download_directory("Video_Downloads")
                    logging.info(f"Download path created at: {download_path}")

                    # Initialize info_dict
                    info_dict = {}

                    # Handle URL or local file
                    if os.path.isfile(input_item):
                        video_file_path = input_item
                        unique_id = generate_unique_identifier(input_item)
                        # Extract basic info from local file
                        info_dict = {
                            'webpage_url': unique_id,
                            'title': os.path.basename(input_item),
                            'description': "Local file",
                            'channel_url': None,
                            'duration': None,
                            'channel': None,
                            'uploader': None,
                            'upload_date': None
                        }
                    else:
                        # Extract video information
                        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                            try:
                                full_info = ydl.extract_info(input_item, download=False)

                                # Create a safe subset of info to log
                                safe_info = {
                                    'title': full_info.get('title', 'No title'),
                                    'duration': full_info.get('duration', 'Unknown duration'),
                                    'upload_date': full_info.get('upload_date', 'Unknown upload date'),
                                    'uploader': full_info.get('uploader', 'Unknown uploader'),
                                    'view_count': full_info.get('view_count', 'Unknown view count')
                                }

                                logging.debug(f"Full info extracted for {input_item}: {safe_info}")
                            except Exception as e:
                                logging.error(f"Error extracting video info: {str(e)}")
                                return None, None, None, None, None, None

                        # Filter the required metadata
                        if full_info:
                            info_dict = {
                                'webpage_url': full_info.get('webpage_url', input_item),
                                'title': full_info.get('title'),
                                'description': full_info.get('description'),
                                'channel_url': full_info.get('channel_url'),
                                'duration': full_info.get('duration'),
                                'channel': full_info.get('channel'),
                                'uploader': full_info.get('uploader'),
                                'upload_date': full_info.get('upload_date')
                            }
                            logging.debug(f"Filtered info_dict: {info_dict}")
                        else:
                            logging.error("Failed to extract video information")
                            return None, None, None, None, None, None

                        # Download video/audio
                        logging.info("Downloading video/audio...")
                        video_file_path = download_video(input_item, download_path, full_info, download_video_flag, current_whisper_model="Blank")
                        if not video_file_path:
                            logging.error(f"Failed to download video/audio from {input_item}")
                            return None, None, None, None, None, None

                    logging.info(f"Processing file: {video_file_path}")

                    # Perform transcription
                    logging.info("Starting transcription...")
                    audio_file_path, segments = perform_transcription(video_file_path, offset, whisper_model,
                                                                      vad_filter, diarize)

                    if audio_file_path is None or segments is None:
                        logging.error("Transcription failed or segments not available.")
                        return None, None, None, None, None, None

                    logging.info(f"Transcription completed. Number of segments: {len(segments)}")

                    # Add metadata to segments
                    segments_with_metadata = {
                        "metadata": info_dict,
                        "segments": segments
                    }

                    # Save segments with metadata to JSON file
                    segments_json_path = os.path.splitext(audio_file_path)[0] + ".segments.json"
                    with open(segments_json_path, 'w') as f:
                        json.dump(segments_with_metadata, f, indent=2)

                    # FIXME - why isnt this working?
                    # Delete the .wav file after successful transcription
                    files_to_delete = [audio_file_path]
                    for file_path in files_to_delete:
                        if file_path and os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                logging.info(f"Successfully deleted file: {file_path}")
                            except Exception as e:
                                logging.warning(f"Failed to delete file {file_path}: {str(e)}")

                    # Delete the mp4 file after successful transcription if not keeping original audio
                    # Modify the file deletion logic to respect keep_original_video
                    if not keep_original_video:
                        files_to_delete = [audio_file_path, video_file_path]
                        for file_path in files_to_delete:
                            if file_path and os.path.exists(file_path):
                                try:
                                    os.remove(file_path)
                                    logging.info(f"Successfully deleted file: {file_path}")
                                except Exception as e:
                                    logging.warning(f"Failed to delete file {file_path}: {str(e)}")
                    else:
                        logging.info(f"Keeping original video file: {video_file_path}")
                        logging.info(f"Keeping original audio file: {audio_file_path}")

                    # Process segments based on the timestamp option
                    if not include_timestamps:
                        segments = [{'Text': segment['Text']} for segment in segments]

                    logging.info(f"Segments processed for timestamp inclusion: {segments}")

                    # Extract text from segments
                    transcription_text = extract_text_from_segments(segments)

                    if transcription_text.startswith("Error:"):
                        logging.error(f"Failed to extract transcription: {transcription_text}")
                        return None, None, None, None, None, None

                    # Use transcription_text instead of segments for further processing
                    full_text_with_metadata = f"{json.dumps(info_dict, indent=2)}\n\n{transcription_text}"

                    logging.debug(f"Full text with metadata extracted: {full_text_with_metadata[:100]}...")

                    # Perform summarization if API is provided
                    summary_text = None
                    if api_name:
                        # API key resolution handled at base of function if none provided
                        api_key = api_key if api_key else None
                        logging.info(f"Starting summarization with {api_name}...")
                        summary_text = perform_summarization(api_name, full_text_with_metadata, custom_prompt, api_key)
                        if summary_text is None:
                            logging.error("Summarization failed.")
                            return None, None, None, None, None, None
                        logging.debug(f"Summarization completed: {summary_text[:100]}...")

                    # Save transcription and summary
                    logging.info("Saving transcription and summary...")
                    download_path = create_download_directory("Audio_Processing")
                    json_file_path, summary_file_path = save_transcription_and_summary(full_text_with_metadata,
                                                                                       summary_text,
                                                                                       download_path, info_dict)
                    logging.info(f"Transcription saved to: {json_file_path}")
                    logging.info(f"Summary saved to: {summary_file_path}")

                    # Prepare keywords for database
                    if isinstance(keywords, str):
                        keywords_list = [kw.strip() for kw in keywords.split(',') if kw.strip()]
                    elif isinstance(keywords, (list, tuple)):
                        keywords_list = keywords
                    else:
                        keywords_list = []
                    logging.info(f"Keywords prepared: {keywords_list}")

                    # Add to database
                    logging.info("Adding to database...")
                    add_media_to_database(info_dict['webpage_url'], info_dict, full_text_with_metadata, summary_text,
                                          keywords_list, custom_prompt, whisper_model)
                    logging.info(f"Media added to database: {info_dict['webpage_url']}")

                    return info_dict[
                        'webpage_url'], full_text_with_metadata, summary_text, json_file_path, summary_file_path, info_dict

                except Exception as e:
                    logging.error(f"Error in process_url_with_metadata: {str(e)}", exc_info=True)
                    return None, None, None, None, None, None

            process_button.click(
                fn=process_videos_wrapper,
                inputs=[
                    url_input, video_file_input, start_time_input, end_time_input, diarize_input, whisper_model_input,
                    custom_prompt_checkbox, custom_prompt_input, chunking_options_checkbox,
                    chunk_method, max_chunk_size, chunk_overlap, use_adaptive_chunking,
                    use_multi_level_chunking, chunk_language, summarize_recursively, api_name_input, api_key_input,
                    keywords_input, use_cookies_input, cookies_input, batch_size_input,
                    timestamp_option, keep_original_video
                ],
                outputs=[progress_output, error_output, results_output, download_transcription, download_summary]
            )


def create_audio_processing_tab():
    with gr.TabItem("Audio File Transcription + Summarization"):
        gr.Markdown("# Transcribe & Summarize Audio Files from URLs or Local Files!")
        with gr.Row():
            with gr.Column():
                audio_url_input = gr.Textbox(label="Audio File URL(s)", placeholder="Enter the URL(s) of the audio file(s), one per line")
                audio_file_input = gr.File(label="Upload Audio File", file_types=["audio/*"])

                use_cookies_input = gr.Checkbox(label="Use cookies for authenticated download", value=False)
                cookies_input = gr.Textbox(
                    label="Audio Download Cookies",
                    placeholder="Paste your cookies here (JSON format)",
                    lines=3,
                    visible=False
                )

                use_cookies_input.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[use_cookies_input],
                    outputs=[cookies_input]
                )

                diarize_input = gr.Checkbox(label="Enable Speaker Diarization", value=False)
                whisper_model_input = gr.Dropdown(choices=whisper_models, value="medium", label="Whisper Model")

                with gr.Row():
                    custom_prompt_checkbox = gr.Checkbox(label="Use a Custom Prompt",
                                                     value=False,
                                                     visible=True)
                    preset_prompt_checkbox = gr.Checkbox(label="Use a pre-set Prompt",
                                                     value=False,
                                                     visible=True)
                with gr.Row():
                    preset_prompt = gr.Dropdown(label="Select Preset Prompt",
                                                choices=load_preset_prompts(),
                                                visible=False)
                with gr.Row():
                    custom_prompt_input = gr.Textbox(label="Custom Prompt",
                                                     placeholder="Enter custom prompt here",
                                                     lines=3,
                                                     visible=False)
                with gr.Row():
                    system_prompt_input = gr.Textbox(label="System Prompt",
                                                     value="""<s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
**Bulleted Note Creation Guidelines**

**Headings**:
- Based on referenced topics, not categories like quotes or terms
- Surrounded by **bold** formatting 
- Not listed as bullet points
- No space between headings and list items underneath

**Emphasis**:
- **Important terms** set in bold font
- **Text ending in a colon**: also bolded

**Review**:
- Ensure adherence to specified format
- Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]
""",
                                                     lines=3,
                                                     visible=False)

                custom_prompt_checkbox.change(
                    fn=lambda x: (gr.update(visible=x), gr.update(visible=x)),
                    inputs=[custom_prompt_checkbox],
                    outputs=[custom_prompt_input, system_prompt_input]
                )
                preset_prompt_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[preset_prompt_checkbox],
                    outputs=[preset_prompt]
                )

                def update_prompts(preset_name):
                    prompts = update_user_prompt(preset_name)
                    return (
                        gr.update(value=prompts["user_prompt"], visible=True),
                        gr.update(value=prompts["system_prompt"], visible=True)
                    )

                preset_prompt.change(
                    update_prompts,
                    inputs=preset_prompt,
                    outputs=[custom_prompt_input, system_prompt_input]
                )

                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"],
                    value=None,
                    label="API for Summarization (Optional)"
                )
                api_key_input = gr.Textbox(label="API Key (if required)", placeholder="Enter your API key here", type="password")
                custom_keywords_input = gr.Textbox(label="Custom Keywords", placeholder="Enter custom keywords, comma-separated")
                keep_original_input = gr.Checkbox(label="Keep original audio file", value=False)

                chunking_options_checkbox = gr.Checkbox(label="Show Chunking Options", value=False)
                with gr.Row(visible=False) as chunking_options_box:
                    gr.Markdown("### Chunking Options")
                    with gr.Column():
                        chunk_method = gr.Dropdown(choices=['words', 'sentences', 'paragraphs', 'tokens'], label="Chunking Method")
                        max_chunk_size = gr.Slider(minimum=100, maximum=1000, value=300, step=50, label="Max Chunk Size")
                        chunk_overlap = gr.Slider(minimum=0, maximum=100, value=0, step=10, label="Chunk Overlap")
                        use_adaptive_chunking = gr.Checkbox(label="Use Adaptive Chunking")
                        use_multi_level_chunking = gr.Checkbox(label="Use Multi-level Chunking")
                        chunk_language = gr.Dropdown(choices=['english', 'french', 'german', 'spanish'], label="Chunking Language")

                chunking_options_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[chunking_options_checkbox],
                    outputs=[chunking_options_box]
                )

                process_audio_button = gr.Button("Process Audio File(s)")

            with gr.Column():
                audio_progress_output = gr.Textbox(label="Progress")
                audio_transcription_output = gr.Textbox(label="Transcription")
                audio_summary_output = gr.Textbox(label="Summary")
                download_transcription = gr.File(label="Download All Transcriptions as JSON")
                download_summary = gr.File(label="Download All Summaries as Text")

        process_audio_button.click(
            fn=process_audio_files,
            inputs=[audio_url_input, audio_file_input, whisper_model_input, api_name_input, api_key_input,
                    use_cookies_input, cookies_input, keep_original_input, custom_keywords_input, custom_prompt_input,
                    chunk_method, max_chunk_size, chunk_overlap, use_adaptive_chunking, use_multi_level_chunking,
                    chunk_language, diarize_input],
            outputs=[audio_progress_output, audio_transcription_output, audio_summary_output]
        )


def create_podcast_tab():
    with gr.TabItem("Podcast"):
        gr.Markdown("# Podcast Transcription and Ingestion")
        with gr.Row():
            with gr.Column():
                podcast_url_input = gr.Textbox(label="Podcast URL", placeholder="Enter the podcast URL here")
                podcast_title_input = gr.Textbox(label="Podcast Title", placeholder="Will be auto-detected if possible")
                podcast_author_input = gr.Textbox(label="Podcast Author", placeholder="Will be auto-detected if possible")

                podcast_keywords_input = gr.Textbox(
                    label="Keywords",
                    placeholder="Enter keywords here (comma-separated, include series name if applicable)",
                    value="podcast,audio",
                    elem_id="podcast-keywords-input"
                )

                with gr.Row():
                    podcast_custom_prompt_checkbox = gr.Checkbox(label="Use a Custom Prompt",
                                                     value=False,
                                                     visible=True)
                    preset_prompt_checkbox = gr.Checkbox(label="Use a pre-set Prompt",
                                                     value=False,
                                                     visible=True)
                with gr.Row():
                    preset_prompt = gr.Dropdown(label="Select Preset Prompt",
                                                choices=load_preset_prompts(),
                                                visible=False)
                with gr.Row():
                    podcast_custom_prompt_input = gr.Textbox(label="Custom Prompt",
                                                     placeholder="Enter custom prompt here",
                                                     lines=3,
                                                     visible=False)
                with gr.Row():
                    system_prompt_input = gr.Textbox(label="System Prompt",
                                                     value="""<s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
**Bulleted Note Creation Guidelines**

**Headings**:
- Based on referenced topics, not categories like quotes or terms
- Surrounded by **bold** formatting 
- Not listed as bullet points
- No space between headings and list items underneath

**Emphasis**:
- **Important terms** set in bold font
- **Text ending in a colon**: also bolded

**Review**:
- Ensure adherence to specified format
- Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]
""",
                                                     lines=3,
                                                     visible=False)

                podcast_custom_prompt_checkbox.change(
                    fn=lambda x: (gr.update(visible=x), gr.update(visible=x)),
                    inputs=[podcast_custom_prompt_checkbox],
                    outputs=[podcast_custom_prompt_input, system_prompt_input]
                )
                preset_prompt_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[preset_prompt_checkbox],
                    outputs=[preset_prompt]
                )

                def update_prompts(preset_name):
                    prompts = update_user_prompt(preset_name)
                    return (
                        gr.update(value=prompts["user_prompt"], visible=True),
                        gr.update(value=prompts["system_prompt"], visible=True)
                    )

                preset_prompt.change(
                    update_prompts,
                    inputs=preset_prompt,
                    outputs=[podcast_custom_prompt_input, system_prompt_input]
                )

                podcast_api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter", "Llama.cpp",
                             "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"],
                    value=None,
                    label="API Name for Summarization (Optional)"
                )
                podcast_api_key_input = gr.Textbox(label="API Key (if required)", type="password")
                podcast_whisper_model_input = gr.Dropdown(choices=whisper_models, value="medium", label="Whisper Model")

                keep_original_input = gr.Checkbox(label="Keep original audio file", value=False)
                enable_diarization_input = gr.Checkbox(label="Enable speaker diarization", value=False)

                use_cookies_input = gr.Checkbox(label="Use cookies for yt-dlp", value=False)
                cookies_input = gr.Textbox(
                    label="yt-dlp Cookies",
                    placeholder="Paste your cookies here (JSON format)",
                    lines=3,
                    visible=False
                )

                use_cookies_input.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[use_cookies_input],
                    outputs=[cookies_input]
                )

                chunking_options_checkbox = gr.Checkbox(label="Show Chunking Options", value=False)
                with gr.Row(visible=False) as chunking_options_box:
                    gr.Markdown("### Chunking Options")
                    with gr.Column():
                        chunk_method = gr.Dropdown(choices=['words', 'sentences', 'paragraphs', 'tokens'], label="Chunking Method")
                        max_chunk_size = gr.Slider(minimum=100, maximum=1000, value=300, step=50, label="Max Chunk Size")
                        chunk_overlap = gr.Slider(minimum=0, maximum=100, value=0, step=10, label="Chunk Overlap")
                        use_adaptive_chunking = gr.Checkbox(label="Use Adaptive Chunking")
                        use_multi_level_chunking = gr.Checkbox(label="Use Multi-level Chunking")
                        chunk_language = gr.Dropdown(choices=['english', 'french', 'german', 'spanish'], label="Chunking Language")

                chunking_options_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[chunking_options_checkbox],
                    outputs=[chunking_options_box]
                )

                podcast_process_button = gr.Button("Process Podcast")

            with gr.Column():
                podcast_progress_output = gr.Textbox(label="Progress")
                podcast_error_output = gr.Textbox(label="Error Messages")
                podcast_transcription_output = gr.Textbox(label="Transcription")
                podcast_summary_output = gr.Textbox(label="Summary")
                download_transcription = gr.File(label="Download Transcription as JSON")
                download_summary = gr.File(label="Download Summary as Text")

        podcast_process_button.click(
            fn=process_podcast,
            inputs=[podcast_url_input, podcast_title_input, podcast_author_input,
                    podcast_keywords_input, podcast_custom_prompt_input, podcast_api_name_input,
                    podcast_api_key_input, podcast_whisper_model_input, keep_original_input,
                    enable_diarization_input, use_cookies_input, cookies_input,
                    chunk_method, max_chunk_size, chunk_overlap, use_adaptive_chunking,
                    use_multi_level_chunking, chunk_language],
            outputs=[podcast_progress_output, podcast_transcription_output, podcast_summary_output,
                     podcast_title_input, podcast_author_input, podcast_keywords_input, podcast_error_output,
                     download_transcription, download_summary]
        )


def create_website_scraping_tab():
    with gr.TabItem("Website Scraping"):
        gr.Markdown("# Scrape Websites & Summarize Articles using a Headless Chrome Browser!")
        with gr.Row():
            with gr.Column():
                url_input = gr.Textbox(label="Article URLs", placeholder="Enter article URLs here, one per line", lines=5)
                custom_article_title_input = gr.Textbox(label="Custom Article Titles (Optional, one per line)",
                                                        placeholder="Enter custom titles for the articles, one per line",
                                                        lines=5)
                with gr.Row():
                    custom_prompt_checkbox = gr.Checkbox(label="Use a Custom Prompt",
                                                     value=False,
                                                     visible=True)
                    preset_prompt_checkbox = gr.Checkbox(label="Use a pre-set Prompt",
                                                     value=False,
                                                     visible=True)
                with gr.Row():
                    preset_prompt = gr.Dropdown(label="Select Preset Prompt",
                                                choices=load_preset_prompts(),
                                                visible=False)
                with gr.Row():
                    website_custom_prompt_input = gr.Textbox(label="Custom Prompt",
                                                     placeholder="Enter custom prompt here",
                                                     lines=3,
                                                     visible=False)
                with gr.Row():
                    system_prompt_input = gr.Textbox(label="System Prompt",
                                                     value="""<s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
**Bulleted Note Creation Guidelines**

**Headings**:
- Based on referenced topics, not categories like quotes or terms
- Surrounded by **bold** formatting 
- Not listed as bullet points
- No space between headings and list items underneath

**Emphasis**:
- **Important terms** set in bold font
- **Text ending in a colon**: also bolded

**Review**:
- Ensure adherence to specified format
- Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]
""",
                                                     lines=3,
                                                     visible=False)

                custom_prompt_checkbox.change(
                    fn=lambda x: (gr.update(visible=x), gr.update(visible=x)),
                    inputs=[custom_prompt_checkbox],
                    outputs=[website_custom_prompt_input, system_prompt_input]
                )
                preset_prompt_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[preset_prompt_checkbox],
                    outputs=[preset_prompt]
                )

                def update_prompts(preset_name):
                    prompts = update_user_prompt(preset_name)
                    return (
                        gr.update(value=prompts["user_prompt"], visible=True),
                        gr.update(value=prompts["system_prompt"], visible=True)
                    )

                preset_prompt.change(
                    update_prompts,
                    inputs=preset_prompt,
                    outputs=[website_custom_prompt_input, system_prompt_input]
                )

                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"], value=None, label="API Name (Mandatory for Summarization)")
                api_key_input = gr.Textbox(label="API Key (Mandatory if API Name is specified)",
                                           placeholder="Enter your API key here; Ignore if using Local API or Built-in API", type="password")
                keywords_input = gr.Textbox(label="Keywords", placeholder="Enter keywords here (comma-separated)",
                                            value="default,no_keyword_set", visible=True)

                scrape_button = gr.Button("Scrape and Summarize")
            with gr.Column():
                result_output = gr.Textbox(label="Result", lines=20)

                scrape_button.click(
                    fn=scrape_and_summarize_multiple,
                    inputs=[url_input, website_custom_prompt_input, api_name_input, api_key_input, keywords_input,
                            custom_article_title_input, system_prompt_input],
                    outputs=result_output
                )


def create_pdf_ingestion_tab():
    with gr.TabItem("PDF Ingestion"):
        # TODO - Add functionality to extract metadata from pdf as part of conversion process in marker
        gr.Markdown("# Ingest PDF Files and Extract Metadata")
        with gr.Row():
            with gr.Column():
                pdf_file_input = gr.File(label="Uploaded PDF File", file_types=[".pdf"], visible=False)
                pdf_upload_button = gr.UploadButton("Click to Upload PDF", file_types=[".pdf"])
                pdf_title_input = gr.Textbox(label="Title (Optional)")
                pdf_author_input = gr.Textbox(label="Author (Optional)")
                pdf_keywords_input = gr.Textbox(label="Keywords (Optional, comma-separated)")
                with gr.Row():
                    custom_prompt_checkbox = gr.Checkbox(label="Use a Custom Prompt",
                                                     value=False,
                                                     visible=True)
                    preset_prompt_checkbox = gr.Checkbox(label="Use a pre-set Prompt",
                                                     value=False,
                                                     visible=True)
                with gr.Row():
                    preset_prompt = gr.Dropdown(label="Select Preset Prompt",
                                                choices=load_preset_prompts(),
                                                visible=False)
                with gr.Row():
                    custom_prompt_input = gr.Textbox(label="Custom Prompt",
                                                     placeholder="Enter custom prompt here",
                                                     lines=3,
                                                     visible=False)
                with gr.Row():
                    system_prompt_input = gr.Textbox(label="System Prompt",
                                                     value="""
<s>You are a bulleted notes specialist.
[INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
**Bulleted Note Creation Guidelines**

**Headings**:
- Based on referenced topics, not categories like quotes or terms
- Surrounded by **bold** formatting 
- Not listed as bullet points
- No space between headings and list items underneath

**Emphasis**:
- **Important terms** set in bold font
- **Text ending in a colon**: also bolded

**Review**:
- Ensure adherence to specified format
- Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]""",
                                                     lines=3,
                                                     visible=False)

                custom_prompt_checkbox.change(
                    fn=lambda x: (gr.update(visible=x), gr.update(visible=x)),
                    inputs=[custom_prompt_checkbox],
                    outputs=[custom_prompt_input, system_prompt_input]
                )
                preset_prompt_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[preset_prompt_checkbox],
                    outputs=[preset_prompt]
                )

                def update_prompts(preset_name):
                    prompts = update_user_prompt(preset_name)
                    return (
                        gr.update(value=prompts["user_prompt"], visible=True),
                        gr.update(value=prompts["system_prompt"], visible=True)
                    )

                preset_prompt.change(
                    update_prompts,
                    inputs=preset_prompt,
                    outputs=[custom_prompt_input, system_prompt_input]
                )

                pdf_ingest_button = gr.Button("Ingest PDF")

                pdf_upload_button.upload(fn=lambda file: file, inputs=pdf_upload_button, outputs=pdf_file_input)
            with gr.Column():
                pdf_result_output = gr.Textbox(label="Result")

            pdf_ingest_button.click(
                fn=process_and_cleanup_pdf,
                inputs=[pdf_file_input, pdf_title_input, pdf_author_input, pdf_keywords_input],
                outputs=pdf_result_output
            )


def test_pdf_ingestion(pdf_file):
    if pdf_file is None:
        return "No file uploaded", ""

    try:
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a path for the temporary PDF file
            temp_path = os.path.join(temp_dir, "temp.pdf")

            # Copy the contents of the uploaded file to the temporary file
            shutil.copy(pdf_file.name, temp_path)

            # Extract text and convert to Markdown
            markdown_text = extract_text_and_format_from_pdf(temp_path)

            # Extract metadata from PDF
            metadata = extract_metadata_from_pdf(temp_path)

            # Use metadata for title and author if not provided
            title = metadata.get('title', os.path.splitext(os.path.basename(pdf_file.name))[0])
            author = metadata.get('author', 'Unknown')

        result = f"PDF '{title}' by {author} processed successfully."
        return result, markdown_text
    except Exception as e:
        return f"Error ingesting PDF: {str(e)}", ""

def create_pdf_ingestion_test_tab():
    with gr.TabItem("Test PDF Ingestion"):
        with gr.Row():
            with gr.Column():
                pdf_file_input = gr.File(label="Upload PDF for testing")
                test_button = gr.Button("Test PDF Ingestion")
            with gr.Column():
                test_output = gr.Textbox(label="Test Result")
                pdf_content_output = gr.Textbox(label="PDF Content", lines=200)
        test_button.click(
            fn=test_pdf_ingestion,
            inputs=[pdf_file_input],
            outputs=[test_output, pdf_content_output]
        )


#
#
################################################################################################################
# Functions for Re-Summarization
#



def create_resummary_tab():
    with gr.TabItem("Re-Summarize"):
        gr.Markdown("# Re-Summarize Existing Content")
        with gr.Row():
            with gr.Column():
                search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
                search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title", label="Search By")
                search_button = gr.Button("Search")

                items_output = gr.Dropdown(label="Select Item", choices=[], interactive=True)
                item_mapping = gr.State({})

                with gr.Row():
                    api_name_input = gr.Dropdown(
                        choices=["Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"],
                        value="Local-LLM", label="API Name")
                    api_key_input = gr.Textbox(label="API Key", placeholder="Enter your API key here", type="password")

                chunking_options_checkbox = gr.Checkbox(label="Use Chunking", value=False)
                with gr.Row(visible=False) as chunking_options_box:
                    chunk_method = gr.Dropdown(choices=['words', 'sentences', 'paragraphs', 'tokens', 'chapters'],
                                               label="Chunking Method", value='words')
                    max_chunk_size = gr.Slider(minimum=100, maximum=1000, value=300, step=50, label="Max Chunk Size")
                    chunk_overlap = gr.Slider(minimum=0, maximum=100, value=0, step=10, label="Chunk Overlap")

                with gr.Row():
                    custom_prompt_checkbox = gr.Checkbox(label="Use a Custom Prompt",
                                                     value=False,
                                                     visible=True)
                    preset_prompt_checkbox = gr.Checkbox(label="Use a pre-set Prompt",
                                                     value=False,
                                                     visible=True)
                with gr.Row():
                    preset_prompt = gr.Dropdown(label="Select Preset Prompt",
                                                choices=load_preset_prompts(),
                                                visible=False)
                with gr.Row():
                    custom_prompt_input = gr.Textbox(label="Custom Prompt",
                                                     placeholder="Enter custom prompt here",
                                                     lines=3,
                                                     visible=False)
                with gr.Row():
                    system_prompt_input = gr.Textbox(label="System Prompt",
                                                     value="""<s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
**Bulleted Note Creation Guidelines**

**Headings**:
- Based on referenced topics, not categories like quotes or terms
- Surrounded by **bold** formatting 
- Not listed as bullet points
- No space between headings and list items underneath

**Emphasis**:
- **Important terms** set in bold font
- **Text ending in a colon**: also bolded

**Review**:
- Ensure adherence to specified format
- Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]
""",
                                                     lines=3,
                                                     visible=False)

                def update_prompts(preset_name):
                    prompts = update_user_prompt(preset_name)
                    return (
                        gr.update(value=prompts["user_prompt"], visible=True),
                        gr.update(value=prompts["system_prompt"], visible=True)
                    )

                preset_prompt.change(
                    update_prompts,
                    inputs=preset_prompt,
                    outputs=[custom_prompt_input, system_prompt_input]
                )

                resummarize_button = gr.Button("Re-Summarize")
            with gr.Column():
                result_output = gr.Textbox(label="Result")

        custom_prompt_checkbox.change(
            fn=lambda x: (gr.update(visible=x), gr.update(visible=x)),
            inputs=[custom_prompt_checkbox],
            outputs=[custom_prompt_input, system_prompt_input]
        )
        preset_prompt_checkbox.change(
            fn=lambda x: gr.update(visible=x),
            inputs=[preset_prompt_checkbox],
            outputs=[preset_prompt]
        )

    # Connect the UI elements
    search_button.click(
        fn=update_resummarize_dropdown,
        inputs=[search_query_input, search_type_input],
        outputs=[items_output, item_mapping]
    )

    chunking_options_checkbox.change(
        fn=lambda x: gr.update(visible=x),
        inputs=[chunking_options_checkbox],
        outputs=[chunking_options_box]
    )

    custom_prompt_checkbox.change(
        fn=lambda x: (gr.update(visible=x), gr.update(visible=x)),
        inputs=[custom_prompt_checkbox],
        outputs=[custom_prompt_input, system_prompt_input]
    )

    resummarize_button.click(
        fn=resummarize_content_wrapper,
        inputs=[items_output, item_mapping, api_name_input, api_key_input, chunking_options_checkbox, chunk_method,
                max_chunk_size, chunk_overlap, custom_prompt_checkbox, custom_prompt_input],
        outputs=result_output
    )

    return search_query_input, search_type_input, search_button, items_output, item_mapping, api_name_input, api_key_input, chunking_options_checkbox, chunking_options_box, chunk_method, max_chunk_size, chunk_overlap, custom_prompt_checkbox, custom_prompt_input, resummarize_button, result_output


def update_resummarize_dropdown(search_query, search_type):
    if search_type in ['Title', 'URL']:
        results = fetch_items_by_title_or_url(search_query, search_type)
    elif search_type == 'Keyword':
        results = fetch_items_by_keyword(search_query)
    else:  # Content
        results = fetch_items_by_content(search_query)

    item_options = [f"{item[1]} ({item[2]})" for item in results]
    item_mapping = {f"{item[1]} ({item[2]})": item[0] for item in results}
    logging.debug(f"item_options: {item_options}")
    logging.debug(f"item_mapping: {item_mapping}")
    return gr.update(choices=item_options), item_mapping


def resummarize_content_wrapper(selected_item, item_mapping, api_name, api_key=None, chunking_options_checkbox=None, chunk_method=None,
                                max_chunk_size=None, chunk_overlap=None, custom_prompt_checkbox=None, custom_prompt=None):
    logging.debug(f"resummarize_content_wrapper called with item_mapping type: {type(item_mapping)}")
    logging.debug(f"selected_item: {selected_item}")

    if not selected_item or not api_name:
        return "Please select an item and provide API details."

    # Handle potential string representation of item_mapping
    if isinstance(item_mapping, str):
        try:
            item_mapping = json.loads(item_mapping)
        except json.JSONDecodeError:
            return f"Error: item_mapping is a string but not valid JSON. Value: {item_mapping[:100]}..."

    if not isinstance(item_mapping, dict):
        return f"Error: item_mapping is not a dictionary or valid JSON string. Type: {type(item_mapping)}"

    media_id = item_mapping.get(selected_item)
    if not media_id:
        return f"Invalid selection. Selected item: {selected_item}, Available items: {list(item_mapping.keys())[:5]}..."

    content, old_prompt, old_summary = fetch_item_details(media_id)

    if not content:
        return "No content available for re-summarization."

    # Prepare chunking options
    chunk_options = {
        'method': chunk_method,
        'max_size': int(max_chunk_size) if max_chunk_size is not None else None,
        'overlap': int(chunk_overlap) if chunk_overlap is not None else None,
        'language': 'english',
        'adaptive': True,
        'multi_level': False,
    } if chunking_options_checkbox else None

    # Prepare summarization prompt
    summarization_prompt = custom_prompt if custom_prompt_checkbox and custom_prompt else None

    logging.debug(f"Calling resummarize_content with media_id: {media_id}")
    # Call the resummarize_content function
    result = resummarize_content(selected_item, item_mapping, content, api_name, api_key, chunk_options, summarization_prompt)

    return result


# FIXME - should be moved...
def resummarize_content(selected_item, item_mapping, content, api_name, api_key=None, chunk_options=None, summarization_prompt=None):
    logging.debug(f"resummarize_content called with selected_item: {selected_item}")
    # Load configuration
    config = load_comprehensive_config()

    # Chunking logic
    if chunk_options:
        chunks = improved_chunking_process(content, chunk_options)
    else:
        chunks = [{'text': content, 'metadata': {}}]

    # Use default prompt if not provided
    if not summarization_prompt:
        summarization_prompt = config.get('Prompts', 'default_summary_prompt', fallback="""<s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
**Bulleted Note Creation Guidelines**

**Headings**:
- Based on referenced topics, not categories like quotes or terms
- Surrounded by **bold** formatting 
- Not listed as bullet points
- No space between headings and list items underneath

**Emphasis**:
- **Important terms** set in bold font
- **Text ending in a colon**: also bolded

**Review**:
- Ensure adherence to specified format
- Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]""")

    # Summarization logic
    summaries = []
    for chunk in chunks:
        chunk_text = chunk['text']
        try:
            chunk_summary = summarize_chunk(api_name, chunk_text, summarization_prompt, api_key)
            if chunk_summary:
                summaries.append(chunk_summary)
            else:
                logging.warning(f"Summarization failed for chunk: {chunk_text[:100]}...")
        except Exception as e:
            logging.error(f"Error during summarization: {str(e)}")
            return f"Error during summarization: {str(e)}"

    if not summaries:
        return "Summarization failed for all chunks."

    new_summary = " ".join(summaries)

    # Update the database with the new summary

    try:
        update_result = update_media_content(selected_item, item_mapping, content, summarization_prompt, new_summary)
        if "successfully" in update_result.lower():
            return f"Re-summarization complete. New summary: {new_summary}..."
        else:
            return f"Error during database update: {update_result}"
    except Exception as e:
        logging.error(f"Error updating database: {str(e)}")
        return f"Error updating database: {str(e)}"


# End of Re-Summarization Functions
#
############################################################################################################################################################################################################################
#
# Explain/Summarize This Tab

def create_summarize_explain_tab():
    with gr.TabItem("Explain/Summarize Text"):
        gr.Markdown("# Explain or Summarize Text without ingesting it into the DB")
        with gr.Row():
            with gr.Column():
                text_to_work_input = gr.Textbox(label="Text to be Explained or Summarized", placeholder="Enter the text you want explained or summarized here", lines=20)
                with gr.Row():
                    explanation_checkbox = gr.Checkbox(label="Explain Text", value=True)
                    summarization_checkbox = gr.Checkbox(label="Summarize Text", value=True)
                api_endpoint = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"],
                    value=None,
                    label="API for Summarization (Optional)"
                )
                api_key_input = gr.Textbox(label="API Key (if required)", placeholder="Enter your API key here", type="password")
                explain_summarize_button = gr.Button("Explain/Summarize")

            with gr.Column():
                summarization_output = gr.Textbox(label="Summary:", lines=20)
                explanation_output = gr.Textbox(label="Explanation:", lines=50)

        explain_summarize_button.click(
            fn=summarize_explain_text,
            inputs=[text_to_work_input, api_endpoint, api_key_input, summarization_checkbox, explanation_checkbox],
            outputs=[summarization_output, explanation_output]
        )


def summarize_explain_text(message, api_endpoint, api_key, summarization, explanation):
    summarization_response = None
    explanation_response = None
    temp = 0.7
    try:
        logging.info(f"Debug - summarize_explain_text Function - Message: {message}")
        logging.info(f"Debug - summarize_explain_text Function - API Endpoint: {api_endpoint}")

        # Prepare the input for the API
        input_data = f"User: {message}\n"
        # Print first 500 chars
        logging.info(f"Debug - Chat Function - Input Data: {input_data[:500]}...")
        logging.debug(f"Debug - Chat Function - API Key: {api_key[:10]}")
        user_prompt = " "
        if not api_endpoint:
            return "Please select an API endpoint", "Please select an API endpoint"
        try:
            if summarization:
                system_prompt = """<s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
                **Bulleted Note Creation Guidelines**
    
                **Headings**:
                - Based on referenced topics, not categories like quotes or terms
                - Surrounded by **bold** formatting 
                - Not listed as bullet points
                - No space between headings and list items underneath
    
                **Emphasis**:
                - **Important terms** set in bold font
                - **Text ending in a colon**: also bolded
    
                **Review**:
                - Ensure adherence to specified format
                - Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]"""

                # Use the existing API request code based on the selected endpoint
                logging.info(f"Debug - Chat Function - API Endpoint: {api_endpoint}")
                if api_endpoint.lower() == 'openai':
                    summarization_response = summarize_with_openai(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "anthropic":
                    summarization_response = summarize_with_anthropic(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "cohere":
                    summarization_response = summarize_with_cohere(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "groq":
                    summarization_response = summarize_with_groq(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "openrouter":
                    summarization_response = summarize_with_openrouter(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "deepseek":
                    summarization_response = summarize_with_deepseek(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "llama.cpp":
                    summarization_response = summarize_with_llama(input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "kobold":
                    summarization_response = summarize_with_kobold(input_data, api_key, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "ooba":
                    summarization_response = summarize_with_oobabooga(input_data, api_key, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "tabbyapi":
                    summarization_response = summarize_with_tabbyapi(input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "vllm":
                    summarization_response = summarize_with_vllm(input_data, user_prompt, system_prompt)
                elif api_endpoint.lower() == "local-llm":
                    summarization_response = summarize_with_local_llm(input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "huggingface":
                    summarization_response = summarize_with_huggingface(api_key, input_data, user_prompt, temp)#, system_prompt)
                elif api_endpoint.lower() == "ollama":
                    summarization_response = summarize_with_ollama(input_data, user_prompt, temp, system_prompt)
                else:
                    raise ValueError(f"Unsupported API endpoint: {api_endpoint}")
        except Exception as e:
            logging.error(f"Error in summarization: {str(e)}")
            response1 = f"An error occurred during summarization: {str(e)}"

        try:
            if explanation:
                system_prompt = """You are a professional teacher. Please explain the content presented in an easy to digest fashion so that a non-specialist may understand it."""
                # Use the existing API request code based on the selected endpoint
                logging.info(f"Debug - Chat Function - API Endpoint: {api_endpoint}")
                if api_endpoint.lower() == 'openai':
                    explanation_response = summarize_with_openai(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "anthropic":
                    explanation_response = summarize_with_anthropic(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "cohere":
                    explanation_response = summarize_with_cohere(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "groq":
                    explanation_response = summarize_with_groq(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "openrouter":
                    explanation_response = summarize_with_openrouter(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "deepseek":
                    explanation_response = summarize_with_deepseek(api_key, input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "llama.cpp":
                    explanation_response = summarize_with_llama(input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "kobold":
                    explanation_response = summarize_with_kobold(input_data, api_key, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "ooba":
                    explanation_response = summarize_with_oobabooga(input_data, api_key, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "tabbyapi":
                    explanation_response = summarize_with_tabbyapi(input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "vllm":
                    explanation_response = summarize_with_vllm(input_data, user_prompt, system_prompt)
                elif api_endpoint.lower() == "local-llm":
                    explanation_response = summarize_with_local_llm(input_data, user_prompt, temp, system_prompt)
                elif api_endpoint.lower() == "huggingface":
                    explanation_response = summarize_with_huggingface(api_key, input_data, user_prompt, temp)#, system_prompt)
                elif api_endpoint.lower() == "ollama":
                    explanation_response = summarize_with_ollama(input_data, user_prompt, temp, system_prompt)
                else:
                    raise ValueError(f"Unsupported API endpoint: {api_endpoint}")
        except Exception as e:
            logging.error(f"Error in summarization: {str(e)}")
            response2 = f"An error occurred during summarization: {str(e)}"

        if summarization_response:
            response1 = f"Summary: {summarization_response}"
        else:
            response1 = "Summary: No summary requested"

        if explanation_response:
            response2 = f"Explanation: {explanation_response}"
        else:
            response2 = "Explanation: No explanation requested"

        return response1, response2

    except Exception as e:
        logging.error(f"Error in chat function: {str(e)}")
        return f"An error occurred: {str(e)}"


############################################################################################################################################################################################################################
#
# Transcript Comparison Tab

# FIXME - under construction
def get_transcript_options(media_id):
    transcripts = get_transcripts(media_id)
    return [f"{t[0]}: {t[1]} ({t[3]})" for t in transcripts]


def update_transcript_options(media_id):
    options = get_transcript_options(media_id)
    return gr.update(choices=options), gr.update(choices=options)

def compare_transcripts(media_id, transcript1_id, transcript2_id):
    try:
        transcripts = get_transcripts(media_id)
        transcript1 = next((t for t in transcripts if t[0] == int(transcript1_id)), None)
        transcript2 = next((t for t in transcripts if t[0] == int(transcript2_id)), None)

        if not transcript1 or not transcript2:
            return "One or both selected transcripts not found."

        comparison = f"Transcript 1 (Model: {transcript1[1]}, Created: {transcript1[3]}):\n\n"
        comparison += format_transcription(transcript1[2])
        comparison += f"\n\nTranscript 2 (Model: {transcript2[1]}, Created: {transcript2[3]}):\n\n"
        comparison += format_transcription(transcript2[2])

        return comparison
    except Exception as e:
        logging.error(f"Error in compare_transcripts: {str(e)}")
        return f"Error comparing transcripts: {str(e)}"


def create_compare_transcripts_tab():
    with gr.TabItem("Compare Transcripts"):
        gr.Markdown("# Compare Transcripts")

        with gr.Row():
            search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
            search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title", label="Search By")
            search_button = gr.Button("Search")

        with gr.Row():
            media_id_output = gr.Dropdown(label="Select Media Item", choices=[], interactive=True)
            media_mapping = gr.State({})

        media_id_input = gr.Number(label="Media ID", visible=False)
        transcript1_dropdown = gr.Dropdown(label="Transcript 1")
        transcript2_dropdown = gr.Dropdown(label="Transcript 2")
        compare_button = gr.Button("Compare Transcripts")
        comparison_output = gr.Textbox(label="Comparison Result", lines=20)

        def update_media_dropdown(search_query, search_type):
            results = browse_items(search_query, search_type)
            item_options = [f"{item[1]} ({item[2]})" for item in results]
            new_item_mapping = {f"{item[1]} ({item[2]})": item[0] for item in results}
            return gr.update(choices=item_options), new_item_mapping

        search_button.click(
            fn=update_media_dropdown,
            inputs=[search_query_input, search_type_input],
            outputs=[media_id_output, media_mapping]
        )

        def load_selected_media_id(selected_media, media_mapping):
            if selected_media and media_mapping and selected_media in media_mapping:
                media_id = media_mapping[selected_media]
                return media_id
            return None

        media_id_output.change(
            fn=load_selected_media_id,
            inputs=[media_id_output, media_mapping],
            outputs=[media_id_input]
        )

        media_id_input.change(update_transcript_options, inputs=[media_id_input],
                              outputs=[transcript1_dropdown, transcript2_dropdown])
        compare_button.click(compare_transcripts, inputs=[media_id_input, transcript1_dropdown, transcript2_dropdown],
                             outputs=[comparison_output])

### End of under construction section

#
#
###########################################################################################################################################################################################################################
#
# Search Tab

def create_rag_tab():
    with gr.TabItem("RAG Search"):
        gr.Markdown("# Retrieval-Augmented Generation (RAG) Search")

        with gr.Row():
            with gr.Column():
                search_query = gr.Textbox(label="Enter your question", placeholder="What would you like to know?")
                api_choice = gr.Dropdown(
                    choices=["Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter", "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "ollama", "HuggingFace"],
                    label="Select API for RAG",
                    value="OpenAI"
                )
                search_button = gr.Button("Search")

            with gr.Column():
                result_output = gr.Textbox(label="Answer", lines=10)
                context_output = gr.Textbox(label="Context", lines=10, visible=False)

        def perform_rag_search(query, api_choice):
            result = rag_search(query, api_choice)
            return result['answer'], result['context']

        search_button.click(perform_rag_search, inputs=[search_query, api_choice], outputs=[result_output, context_output])

# FIXME - under construction
def create_embeddings_tab():
    with gr.TabItem("Create Embeddings"):
        gr.Markdown("# Create Embeddings for All Content")

        with gr.Row():
            with gr.Column():
                embedding_api_choice = gr.Dropdown(
                    choices=["OpenAI", "Local", "HuggingFace"],
                    label="Select API for Embeddings",
                    value="OpenAI"
                )
                create_button = gr.Button("Create Embeddings")

            with gr.Column():
                status_output = gr.Textbox(label="Status", lines=10)

        def create_embeddings(api_choice):
            try:
                # Assuming you have a function that handles the creation of embeddings
                from App_Function_Libraries.ChromaDB_Library import create_all_embeddings
                status = create_all_embeddings(api_choice)
                return status
            except Exception as e:
                return f"Error: {str(e)}"

        create_button.click(create_embeddings, inputs=[embedding_api_choice], outputs=status_output)

def search_prompts(query):
    try:
        conn = sqlite3.connect('prompts.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name, details, system, user FROM Prompts WHERE name LIKE ? OR details LIKE ?",
                       (f"%{query}%", f"%{query}%"))
        results = cursor.fetchall()
        conn.close()
        return results
    except sqlite3.Error as e:
        print(f"Error searching prompts: {e}")
        return []


def create_search_tab():
    with gr.TabItem("Search / Detailed View"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("# Search across all ingested items in the Database")
                gr.Markdown(" by Title / URL / Keyword / or Content via SQLite Full-Text-Search")
                search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
                search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title", label="Search By")
                search_button = gr.Button("Search")
                items_output = gr.Dropdown(label="Select Item", choices=[])
                item_mapping = gr.State({})
                prompt_summary_output = gr.HTML(label="Prompt & Summary", visible=True)

                search_button.click(
                    fn=update_dropdown,
                    inputs=[search_query_input, search_type_input],
                    outputs=[items_output, item_mapping]
                )
            with gr.Column():
                content_output = gr.Markdown(label="Content", visible=True)
                items_output.change(
                    fn=update_detailed_view,
                    inputs=[items_output, item_mapping],
                    outputs=[prompt_summary_output, content_output]
                )


def display_search_results(query):
    if not query.strip():
        return "Please enter a search query."

    results = search_prompts(query)

    # Debugging: Print the results to the console to see what is being returned
    print(f"Processed search results for query '{query}': {results}")

    if results:
        result_md = "## Search Results:\n"
        for result in results:
            # Debugging: Print each result to see its format
            print(f"Result item: {result}")

            if len(result) == 2:
                name, details = result
                result_md += f"**Title:** {name}\n\n**Description:** {details}\n\n---\n"

            elif len(result) == 4:
                name, details, system, user = result
                result_md += f"**Title:** {name}\n\n"
                result_md += f"**Description:** {details}\n\n"
                result_md += f"**System Prompt:** {system}\n\n"
                result_md += f"**User Prompt:** {user}\n\n"
                result_md += "---\n"
            else:
                result_md += "Error: Unexpected result format.\n\n---\n"
        return result_md
    return "No results found."


def create_viewing_tab():
    with gr.TabItem("View Database"):
        gr.Markdown("# View Database Entries")
        with gr.Row():
            with gr.Column():
                entries_per_page = gr.Dropdown(choices=[10, 20, 50, 100], label="Entries per Page", value=10)
                page_number = gr.Number(value=1, label="Page Number", precision=0)
                view_button = gr.Button("View Page")
                next_page_button = gr.Button("Next Page")
                previous_page_button = gr.Button("Previous Page")
            with gr.Column():
                results_display = gr.HTML()
                pagination_info = gr.Textbox(label="Pagination Info", interactive=False)

        def update_page(page, entries_per_page):
            results, pagination, total_pages = view_database(page, entries_per_page)
            next_disabled = page >= total_pages
            prev_disabled = page <= 1
            return results, pagination, page, gr.update(interactive=not next_disabled), gr.update(interactive=not prev_disabled)

        def go_to_next_page(current_page, entries_per_page):
            next_page = current_page + 1
            return update_page(next_page, entries_per_page)

        def go_to_previous_page(current_page, entries_per_page):
            previous_page = max(1, current_page - 1)
            return update_page(previous_page, entries_per_page)

        view_button.click(
            fn=update_page,
            inputs=[page_number, entries_per_page],
            outputs=[results_display, pagination_info, page_number, next_page_button, previous_page_button]
        )

        next_page_button.click(
            fn=go_to_next_page,
            inputs=[page_number, entries_per_page],
            outputs=[results_display, pagination_info, page_number, next_page_button, previous_page_button]
        )

        previous_page_button.click(
            fn=go_to_previous_page,
            inputs=[page_number, entries_per_page],
            outputs=[results_display, pagination_info, page_number, next_page_button, previous_page_button]
        )


def create_search_summaries_tab():
    with gr.TabItem("Search/View Title+Summary "):
        gr.Markdown("# Search across all ingested items in the Database and review their summaries")
        gr.Markdown("Search by Title / URL / Keyword / or Content via SQLite Full-Text-Search")
        with gr.Row():
            with gr.Column():
                search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
                search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title",
                                             label="Search By")
                entries_per_page = gr.Dropdown(choices=[10, 20, 50, 100], label="Entries per Page", value=10)
                page_number = gr.Number(value=1, label="Page Number", precision=0)
                char_count_input = gr.Number(value=5000, label="Amount of characters to display from the main content",
                                             precision=0)
            with gr.Column():
                search_button = gr.Button("Search")
                next_page_button = gr.Button("Next Page")
                previous_page_button = gr.Button("Previous Page")
                pagination_info = gr.Textbox(label="Pagination Info", interactive=False)
        search_results_output = gr.HTML()


        def update_search_page(query, search_type, page, entries_per_page, char_count):
            # Ensure char_count is a positive integer
            char_count = max(1, int(char_count)) if char_count else 5000
            results, pagination, total_pages = search_and_display_items(query, search_type, page, entries_per_page, char_count)
            next_disabled = page >= total_pages
            prev_disabled = page <= 1
            return results, pagination, page, gr.update(interactive=not next_disabled), gr.update(
                interactive=not prev_disabled)

        def go_to_next_search_page(query, search_type, current_page, entries_per_page, char_count):
            next_page = current_page + 1
            return update_search_page(query, search_type, next_page, entries_per_page, char_count)

        def go_to_previous_search_page(query, search_type, current_page, entries_per_page, char_count):
            previous_page = max(1, current_page - 1)
            return update_search_page(query, search_type, previous_page, entries_per_page, char_count)

        search_button.click(
            fn=update_search_page,
            inputs=[search_query_input, search_type_input, page_number, entries_per_page, char_count_input],
            outputs=[search_results_output, pagination_info, page_number, next_page_button, previous_page_button]
        )

        next_page_button.click(
            fn=go_to_next_search_page,
            inputs=[search_query_input, search_type_input, page_number, entries_per_page, char_count_input],
            outputs=[search_results_output, pagination_info, page_number, next_page_button, previous_page_button]
        )

        previous_page_button.click(
            fn=go_to_previous_search_page,
            inputs=[search_query_input, search_type_input, page_number, entries_per_page, char_count_input],
            outputs=[search_results_output, pagination_info, page_number, next_page_button, previous_page_button]
        )



def create_prompt_view_tab():
    with gr.TabItem("View Prompt Database"):
        gr.Markdown("# View Prompt Database Entries")
        with gr.Row():
            with gr.Column():
                entries_per_page = gr.Dropdown(choices=[10, 20, 50, 100], label="Entries per Page", value=10)
                page_number = gr.Number(value=1, label="Page Number", precision=0)
                view_button = gr.Button("View Page")
                next_page_button = gr.Button("Next Page")
                previous_page_button = gr.Button("Previous Page")
            with gr.Column():
                pagination_info = gr.Textbox(label="Pagination Info", interactive=False)
        results_display = gr.HTML()

        def view_database(page, entries_per_page):
            offset = (page - 1) * entries_per_page
            try:
                with sqlite3.connect('prompts.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT p.name, p.details, p.system, p.user, GROUP_CONCAT(k.keyword, ', ') as keywords
                        FROM Prompts p
                        LEFT JOIN PromptKeywords pk ON p.id = pk.prompt_id
                        LEFT JOIN Keywords k ON pk.keyword_id = k.id
                        GROUP BY p.id
                        ORDER BY p.name
                        LIMIT ? OFFSET ?
                    ''', (entries_per_page, offset))
                    prompts = cursor.fetchall()

                    cursor.execute('SELECT COUNT(*) FROM Prompts')
                    total_prompts = cursor.fetchone()[0]

                results = ""
                for prompt in prompts:
                    # Escape HTML special characters and replace newlines with <br> tags
                    title = html.escape(prompt[0]).replace('\n', '<br>')
                    details = html.escape(prompt[1] or '').replace('\n', '<br>')
                    system_prompt = html.escape(prompt[2] or '')
                    user_prompt = html.escape(prompt[3] or '')
                    keywords = html.escape(prompt[4] or '').replace('\n', '<br>')

                    results += f"""
                    <div style="border: 1px solid #ddd; padding: 10px; margin-bottom: 20px;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                            <div><strong>Title:</strong> {title}</div>
                            <div><strong>Details:</strong> {details}</div>
                        </div>
                        <div style="margin-top: 10px;">
                            <strong>User Prompt:</strong>
                            <pre style="white-space: pre-wrap; word-wrap: break-word;">{user_prompt}</pre>
                        </div>
                        <div style="margin-top: 10px;">
                            <strong>System Prompt:</strong>
                            <pre style="white-space: pre-wrap; word-wrap: break-word;">{system_prompt}</pre>
                        </div>
                        <div style="margin-top: 10px;">
                            <strong>Keywords:</strong> {keywords}
                        </div>
                    </div>
                    """

                total_pages = (total_prompts + entries_per_page - 1) // entries_per_page
                pagination = f"Page {page} of {total_pages} (Total prompts: {total_prompts})"

                return results, pagination, total_pages
            except sqlite3.Error as e:
                return f"<p>Error fetching prompts: {e}</p>", "Error", 0

        def update_page(page, entries_per_page):
            results, pagination, total_pages = view_database(page, entries_per_page)
            next_disabled = page >= total_pages
            prev_disabled = page <= 1
            return results, pagination, page, gr.update(interactive=not next_disabled), gr.update(
                interactive=not prev_disabled)

        def go_to_next_page(current_page, entries_per_page):
            next_page = current_page + 1
            return update_page(next_page, entries_per_page)

        def go_to_previous_page(current_page, entries_per_page):
            previous_page = max(1, current_page - 1)
            return update_page(previous_page, entries_per_page)

        view_button.click(
            fn=update_page,
            inputs=[page_number, entries_per_page],
            outputs=[results_display, pagination_info, page_number, next_page_button, previous_page_button]
        )

        next_page_button.click(
            fn=go_to_next_page,
            inputs=[page_number, entries_per_page],
            outputs=[results_display, pagination_info, page_number, next_page_button, previous_page_button]
        )

        previous_page_button.click(
            fn=go_to_previous_page,
            inputs=[page_number, entries_per_page],
            outputs=[results_display, pagination_info, page_number, next_page_button, previous_page_button]
        )



def create_prompt_search_tab():
    with gr.TabItem("Search Prompts"):
        gr.Markdown("# Search and View Prompt Details")
        gr.Markdown("Currently has all of the https://github.com/danielmiessler/fabric prompts already available")
        with gr.Row():
            with gr.Column():
                search_query_input = gr.Textbox(label="Search Prompts", placeholder="Enter your search query...")
                entries_per_page = gr.Dropdown(choices=[10, 20, 50, 100], label="Entries per Page", value=10)
                page_number = gr.Number(value=1, label="Page Number", precision=0)
            with gr.Column():
                search_button = gr.Button("Search Prompts")
                next_page_button = gr.Button("Next Page")
                previous_page_button = gr.Button("Previous Page")
                pagination_info = gr.Textbox(label="Pagination Info", interactive=False)
        search_results_output = gr.HTML()

        def search_and_display_prompts(query, page, entries_per_page):
            offset = (page - 1) * entries_per_page
            try:
                with sqlite3.connect('prompts.db') as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT p.name, p.details, p.system, p.user, GROUP_CONCAT(k.keyword, ', ') as keywords
                        FROM Prompts p
                        LEFT JOIN PromptKeywords pk ON p.id = pk.prompt_id
                        LEFT JOIN Keywords k ON pk.keyword_id = k.id
                        WHERE p.name LIKE ? OR p.details LIKE ? OR p.system LIKE ? OR p.user LIKE ? OR k.keyword LIKE ?
                        GROUP BY p.id
                        ORDER BY p.name
                        LIMIT ? OFFSET ?
                    ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', entries_per_page, offset))
                    prompts = cursor.fetchall()

                    cursor.execute('''
                        SELECT COUNT(DISTINCT p.id)
                        FROM Prompts p
                        LEFT JOIN PromptKeywords pk ON p.id = pk.prompt_id
                        LEFT JOIN Keywords k ON pk.keyword_id = k.id
                        WHERE p.name LIKE ? OR p.details LIKE ? OR p.system LIKE ? OR p.user LIKE ? OR k.keyword LIKE ?
                    ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
                    total_prompts = cursor.fetchone()[0]

                results = ""
                for prompt in prompts:
                    title = html.escape(prompt[0]).replace('\n', '<br>')
                    details = html.escape(prompt[1] or '').replace('\n', '<br>')
                    system_prompt = html.escape(prompt[2] or '')
                    user_prompt = html.escape(prompt[3] or '')
                    keywords = html.escape(prompt[4] or '').replace('\n', '<br>')

                    results += f"""
                    <div style="border: 1px solid #ddd; padding: 10px; margin-bottom: 20px;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                            <div><strong>Title:</strong> {title}</div>
                            <div><strong>Details:</strong> {details}</div>
                        </div>
                        <div style="margin-top: 10px;">
                            <strong>User Prompt:</strong>
                            <pre style="white-space: pre-wrap; word-wrap: break-word;">{user_prompt}</pre>
                        </div>
                        <div style="margin-top: 10px;">
                            <strong>System Prompt:</strong>
                            <pre style="white-space: pre-wrap; word-wrap: break-word;">{system_prompt}</pre>
                        </div>
                        <div style="margin-top: 10px;">
                            <strong>Keywords:</strong> {keywords}
                        </div>
                    </div>
                    """

                total_pages = (total_prompts + entries_per_page - 1) // entries_per_page
                pagination = f"Page {page} of {total_pages} (Total prompts: {total_prompts})"

                return results, pagination, total_pages
            except sqlite3.Error as e:
                return f"<p>Error searching prompts: {e}</p>", "Error", 0

        def update_search_page(query, page, entries_per_page):
            results, pagination, total_pages = search_and_display_prompts(query, page, entries_per_page)
            next_disabled = page >= total_pages
            prev_disabled = page <= 1
            return results, pagination, page, gr.update(interactive=not next_disabled), gr.update(interactive=not prev_disabled)

        def go_to_next_search_page(query, current_page, entries_per_page):
            next_page = current_page + 1
            return update_search_page(query, next_page, entries_per_page)

        def go_to_previous_search_page(query, current_page, entries_per_page):
            previous_page = max(1, current_page - 1)
            return update_search_page(query, previous_page, entries_per_page)

        search_button.click(
            fn=update_search_page,
            inputs=[search_query_input, page_number, entries_per_page],
            outputs=[search_results_output, pagination_info, page_number, next_page_button, previous_page_button]
        )

        next_page_button.click(
            fn=go_to_next_search_page,
            inputs=[search_query_input, page_number, entries_per_page],
            outputs=[search_results_output, pagination_info, page_number, next_page_button, previous_page_button]
        )

        previous_page_button.click(
            fn=go_to_previous_search_page,
            inputs=[search_query_input, page_number, entries_per_page],
            outputs=[search_results_output, pagination_info, page_number, next_page_button, previous_page_button]
        )


# End of Search Tab Functions
#
##############################################################################################################################################################################################################################
#
# Llamafile Tab


def start_llamafile(*args):
    # Unpack arguments
    (am_noob, verbose_checked, threads_checked, threads_value, http_threads_checked, http_threads_value,
     model_checked, model_value, hf_repo_checked, hf_repo_value, hf_file_checked, hf_file_value,
     ctx_size_checked, ctx_size_value, ngl_checked, ngl_value, host_checked, host_value, port_checked,
     port_value) = args

    # Construct command based on checked values
    command = []
    if am_noob:
        am_noob = True
    if verbose_checked is not None and verbose_checked:
        command.append('-v')
    if threads_checked and threads_value is not None:
        command.extend(['-t', str(threads_value)])
    if http_threads_checked and http_threads_value is not None:
        command.extend(['--threads', str(http_threads_value)])
    if model_checked and model_value is not None:
        model_path = model_value.name
        command.extend(['-m', model_path])
    if hf_repo_checked and hf_repo_value is not None:
        command.extend(['-hfr', hf_repo_value])
    if hf_file_checked and hf_file_value is not None:
        command.extend(['-hff', hf_file_value])
    if ctx_size_checked and ctx_size_value is not None:
        command.extend(['-c', str(ctx_size_value)])
    if ngl_checked and ngl_value is not None:
        command.extend(['-ngl', str(ngl_value)])
    if host_checked and host_value is not None:
        command.extend(['--host', host_value])
    if port_checked and port_value is not None:
        command.extend(['--port', str(port_value)])

    # Code to start llamafile with the provided configuration
    local_llm_gui_function(am_noob, verbose_checked, threads_checked, threads_value,
                           http_threads_checked, http_threads_value, model_checked,
                           model_value, hf_repo_checked, hf_repo_value, hf_file_checked,
                           hf_file_value, ctx_size_checked, ctx_size_value, ngl_checked,
                           ngl_value, host_checked, host_value, port_checked, port_value, )

    # Example command output to verify
    return f"Command built and ran: {' '.join(command)} \n\nLlamafile started successfully."

def stop_llamafile():
    # Code to stop llamafile
    # ...
    return "Llamafile stopped"




def create_chat_with_llamafile_tab():
    def get_model_files(directory):
        pattern = os.path.join(directory, "*.{gguf,llamafile}")
        return [os.path.basename(f) for f in glob.glob(pattern)]

    def update_dropdowns():
        current_dir_models = get_model_files(".")
        parent_dir_models = get_model_files("..")
        return (
            {"choices": current_dir_models, "value": None},
            {"choices": parent_dir_models, "value": None}
        )

    with gr.TabItem("Local LLM with Llamafile"):
        gr.Markdown("# Settings for Llamafile")
        with gr.Row():
            with gr.Column():
                am_noob = gr.Checkbox(label="Check this to enable sane defaults", value=False, visible=True)
                # FIXME - these get deleted at some point?
                advanced_mode_toggle = gr.Checkbox(label="Advanced Mode - Enable to show all settings", value=False)


            with gr.Column():
                # FIXME - make this actually work
                model_checked = gr.Checkbox(label="Enable Setting Local LLM Model Path", value=False, visible=True)
                current_dir_dropdown = gr.Dropdown(
                    label="Select Model from Current Directory (.)",
                    choices=[],  # Start with an empty list
                    visible=True
                )
                parent_dir_dropdown = gr.Dropdown(
                    label="Select Model from Parent Directory (..)",
                    choices=[],  # Start with an empty list
                    visible=True
                )
                refresh_button = gr.Button("Refresh Model Lists")
                model_value = gr.Textbox(label="Selected Model File", value="", visible=True)
        with gr.Row():
            with gr.Column():
                ngl_checked = gr.Checkbox(label="Enable Setting GPU Layers", value=False, visible=True)
                ngl_value = gr.Number(label="Number of GPU Layers", value=None, precision=0, visible=True)
                advanced_inputs = create_llamafile_advanced_inputs()
            with gr.Column():
                start_button = gr.Button("Start Llamafile")
                stop_button = gr.Button("Stop Llamafile (doesn't work)")
                output_display = gr.Markdown()


        def update_model_value(current_dir_model, parent_dir_model):
            if current_dir_model:
                return current_dir_model
            elif parent_dir_model:
                return os.path.join("..", parent_dir_model)
            else:
                return ""

        current_dir_dropdown.change(
            fn=update_model_value,
            inputs=[current_dir_dropdown, parent_dir_dropdown],
            outputs=model_value
        )
        parent_dir_dropdown.change(
            fn=update_model_value,
            inputs=[current_dir_dropdown, parent_dir_dropdown],
            outputs=model_value
        )

        refresh_button.click(
            fn=update_dropdowns,
            inputs=[],
            outputs=[current_dir_dropdown, parent_dir_dropdown]
        )

        start_button.click(
            fn=start_llamafile,
            inputs=[am_noob, model_checked, model_value, ngl_checked, ngl_value] + advanced_inputs,
            outputs=output_display
        )


def create_llamafile_advanced_inputs():
    verbose_checked = gr.Checkbox(label="Enable Verbose Output", value=False, visible=False)
    threads_checked = gr.Checkbox(label="Set CPU Threads", value=False, visible=False)
    threads_value = gr.Number(label="Number of CPU Threads", value=None, precision=0, visible=False)
    http_threads_checked = gr.Checkbox(label="Set HTTP Server Threads", value=False, visible=False)
    http_threads_value = gr.Number(label="Number of HTTP Server Threads", value=None, precision=0, visible=False)
    hf_repo_checked = gr.Checkbox(label="Use Huggingface Repo Model", value=False, visible=False)
    hf_repo_value = gr.Textbox(label="Huggingface Repo Name", value="", visible=False)
    hf_file_checked = gr.Checkbox(label="Set Huggingface Model File", value=False, visible=False)
    hf_file_value = gr.Textbox(label="Huggingface Model File", value="", visible=False)
    ctx_size_checked = gr.Checkbox(label="Set Prompt Context Size", value=False, visible=False)
    ctx_size_value = gr.Number(label="Prompt Context Size", value=8124, precision=0, visible=False)
    host_checked = gr.Checkbox(label="Set IP to Listen On", value=False, visible=False)
    host_value = gr.Textbox(label="Host IP Address", value="", visible=False)
    port_checked = gr.Checkbox(label="Set Server Port", value=False, visible=False)
    port_value = gr.Number(label="Port Number", value=None, precision=0, visible=False)

    return [verbose_checked, threads_checked, threads_value, http_threads_checked, http_threads_value,
            hf_repo_checked, hf_repo_value, hf_file_checked, hf_file_value, ctx_size_checked, ctx_size_value,
            host_checked, host_value, port_checked, port_value]

#
# End of Llamafile Tab Functions
##############################################################################################################################################################################################################################
#
# Chat Interface Tab Functions

def chat(message, history, media_content, selected_parts, api_endpoint, api_key, prompt, temperature,
         system_message=None):
    try:
        logging.info(f"Debug - Chat Function - Message: {message}")
        logging.info(f"Debug - Chat Function - Media Content: {media_content}")
        logging.info(f"Debug - Chat Function - Selected Parts: {selected_parts}")
        logging.info(f"Debug - Chat Function - API Endpoint: {api_endpoint}")
        #logging.info(f"Debug - Chat Function - Prompt: {prompt}")

        # Ensure selected_parts is a list
        if not isinstance(selected_parts, (list, tuple)):
            selected_parts = [selected_parts] if selected_parts else []

        #logging.debug(f"Debug - Chat Function - Selected Parts (after check): {selected_parts}")

        # Combine the selected parts of the media content
        combined_content = "\n\n".join([f"{part.capitalize()}: {media_content.get(part, '')}" for part in selected_parts if part in media_content])
        # Print first 500 chars
        #logging.debug(f"Debug - Chat Function - Combined Content: {combined_content[:500]}...")

        # Prepare the input for the API
        if not history:
            input_data = f"{combined_content}\n\nUser: {message}\n"
        else:
            input_data = f"User: {message}\n"
        # Print first 500 chars
        #logging.info(f"Debug - Chat Function - Input Data: {input_data[:500]}...")

        if system_message:
            print(f"System message: {system_message}")
            logging.debug(f"Debug - Chat Function - System Message: {system_message}")
        temperature = float(temperature) if temperature else 0.7
        temp = temperature
        
        logging.debug("Debug - Chat Function - Temperature: {temperature}")
        logging.debug(f"Debug - Chat Function - API Key: {api_key[:10]}")
        logging.debug(f"Debug - Chat Function - Prompt: {prompt}")

        # Use the existing API request code based on the selected endpoint
        logging.info(f"Debug - Chat Function - API Endpoint: {api_endpoint}")
        if api_endpoint.lower() == 'openai':
            response = chat_with_openai(api_key, input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "anthropic":
            response = chat_with_anthropic(api_key, input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "cohere":
            response = chat_with_cohere(api_key, input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "groq":
            response = chat_with_groq(api_key, input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "openrouter":
            response = chat_with_openrouter(api_key, input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "deepseek":
            response = chat_with_deepseek(api_key, input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "mistral":
            response = chat_with_mistral(api_key, input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "llama.cpp":
            response = chat_with_llama(input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "kobold":
            response = chat_with_kobold(input_data, api_key, prompt, temp, system_message)
        elif api_endpoint.lower() == "ooba":
            response = chat_with_oobabooga(input_data, api_key, prompt, temp, system_message)
        elif api_endpoint.lower() == "tabbyapi":
            response = chat_with_tabbyapi(input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "vllm":
            response = chat_with_vllm(input_data, prompt, system_message)
        elif api_endpoint.lower() == "local-llm":
            response = chat_with_local_llm(input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "huggingface":
            response = chat_with_huggingface(api_key, input_data, prompt, temp)#, system_message)
        elif api_endpoint.lower() == "ollama":
            response = chat_with_ollama(input_data, prompt, temp, system_message)
        elif api_endpoint.lower() == "aphrodite":
            response = chat_with_aphrodite(input_data, prompt, temp, system_message)
        else:
            raise ValueError(f"Unsupported API endpoint: {api_endpoint}")

        return response

    except Exception as e:
        logging.error(f"Error in chat function: {str(e)}")
        return f"An error occurred: {str(e)}"


def save_chat_history_to_db_wrapper(chatbot, conversation_id, media_content):
    logging.info(f"Attempting to save chat history. Media content type: {type(media_content)}")
    try:
        # Extract the media_id and media_name from the media_content
        media_id = None
        media_name = None
        if isinstance(media_content, dict):
            logging.debug(f"Media content keys: {media_content.keys()}")
            if 'content' in media_content:
                try:
                    content = media_content['content']
                    if isinstance(content, str):
                        content_json = json.loads(content)
                    elif isinstance(content, dict):
                        content_json = content
                    else:
                        raise ValueError(f"Unexpected content type: {type(content)}")

                    # Use the webpage_url as the media_id
                    media_id = content_json.get('webpage_url')
                    # Use the title as the media_name
                    media_name = content_json.get('title')

                    logging.info(f"Extracted media_id: {media_id}, media_name: {media_name}")
                except json.JSONDecodeError:
                    logging.error("Failed to decode JSON from media_content['content']")
                except Exception as e:
                    logging.error(f"Error processing media_content: {str(e)}")
            else:
                logging.warning("'content' key not found in media_content")
        else:
            logging.warning(f"media_content is not a dictionary. Type: {type(media_content)}")

        if media_id is None:
            # If we couldn't find a media_id, we'll use a placeholder
            media_id = "unknown_media"
            logging.warning(f"Unable to extract media_id from media_content. Using placeholder: {media_id}")

        if media_name is None:
            media_name = "Unnamed Media"
            logging.warning(f"Unable to extract media_name from media_content. Using placeholder: {media_name}")

        # Generate a unique conversation name using media_id and current timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        conversation_name = f"Chat_{media_id}_{timestamp}"

        new_conversation_id = save_chat_history_to_database(chatbot, conversation_id, media_id, media_name, conversation_name)
        return new_conversation_id, f"Chat history saved successfully as {conversation_name}!"
    except Exception as e:
        error_message = f"Failed to save chat history: {str(e)}"
        logging.error(error_message, exc_info=True)
        return conversation_id, error_message


def save_chat_history(history, conversation_id, media_content):
    try:
        content, conversation_name = generate_chat_history_content(history, conversation_id, media_content)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_conversation_name = re.sub(r'[^a-zA-Z0-9_-]', '_', conversation_name)
        base_filename = f"{safe_conversation_name}_{timestamp}.json"

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        # Generate a unique filename
        unique_filename = generate_unique_filename(os.path.dirname(temp_file_path), base_filename)
        final_path = os.path.join(os.path.dirname(temp_file_path), unique_filename)

        # Rename the temporary file to the unique filename
        os.rename(temp_file_path, final_path)

        return final_path
    except Exception as e:
        logging.error(f"Error saving chat history: {str(e)}")
        return None


def generate_chat_history_content(history, conversation_id, media_content):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    conversation_name = get_conversation_name(conversation_id)

    if not conversation_name:
        media_name = extract_media_name(media_content)
        if media_name:
            conversation_name = f"{media_name}-chat"
        else:
            conversation_name = f"chat-{timestamp}"  # Fallback name

    chat_data = {
        "conversation_id": conversation_id,
        "conversation_name": conversation_name,
        "timestamp": timestamp,
        "history": [
            {
                "role": "user" if i % 2 == 0 else "bot",
                "content": msg[0] if isinstance(msg, tuple) else msg
            }
            for i, msg in enumerate(history)
        ]
    }

    return json.dumps(chat_data, indent=2), conversation_name


def extract_media_name(media_content):
    if isinstance(media_content, dict):
        content = media_content.get('content', {})
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except json.JSONDecodeError:
                logging.warning("Failed to parse media_content JSON string")
                return None

        # Try to extract title from the content
        if isinstance(content, dict):
            return content.get('title') or content.get('name')

    logging.warning(f"Unexpected media_content format: {type(media_content)}")
    return None

def show_edit_message(selected):
    if selected:
        return gr.update(value=selected[0], visible=True), gr.update(value=selected[1], visible=True), gr.update(visible=True)
    return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

def show_delete_message(selected):
    if selected:
        return gr.update(value=selected[1], visible=True), gr.update(visible=True)
    return gr.update(visible=False), gr.update(visible=False)


def update_chat_content(selected_item, use_content, use_summary, use_prompt, item_mapping):
    logging.debug(f"Debug - Update Chat Content - Selected Item: {selected_item}\n")
    logging.debug(f"Debug - Update Chat Content - Use Content: {use_content}\n\n\n\n")
    logging.debug(f"Debug - Update Chat Content - Use Summary: {use_summary}\n\n")
    logging.debug(f"Debug - Update Chat Content - Use Prompt: {use_prompt}\n\n")
    logging.debug(f"Debug - Update Chat Content - Item Mapping: {item_mapping}\n\n")

    if selected_item and selected_item in item_mapping:
        media_id = item_mapping[selected_item]
        content = load_media_content(media_id)
        selected_parts = []
        if use_content and "content" in content:
            selected_parts.append("content")
        if use_summary and "summary" in content:
            selected_parts.append("summary")
        if use_prompt and "prompt" in content:
            selected_parts.append("prompt")

        # Modified debug print
        if isinstance(content, dict):
            print(f"Debug - Update Chat Content - Content keys: {list(content.keys())}")
            for key, value in content.items():
                print(f"Debug - Update Chat Content - {key} (first 500 char): {str(value)[:500]}\n\n\n\n")
        else:
            print(f"Debug - Update Chat Content - Content(first 500 char): {str(content)[:500]}\n\n\n\n")

        print(f"Debug - Update Chat Content - Selected Parts: {selected_parts}")
        return content, selected_parts
    else:
        print(f"Debug - Update Chat Content - No item selected or item not in mapping")
        return {}, []


def debug_output(media_content, selected_parts):
    print(f"Debug - Media Content: {media_content}")
    print(f"Debug - Selected Parts: {selected_parts}")
    return ""


def update_selected_parts(use_content, use_summary, use_prompt):
    selected_parts = []
    if use_content:
        selected_parts.append("content")
    if use_summary:
        selected_parts.append("summary")
    if use_prompt:
        selected_parts.append("prompt")
    print(f"Debug - Update Selected Parts: {selected_parts}")
    return selected_parts


# Old update_user_prompt shim for backwards compatibility
def get_system_prompt(preset_name):
    # For backwards compatibility
    prompts = update_user_prompt(preset_name)
    return prompts["system_prompt"]


def update_user_prompt(preset_name):
    details = fetch_prompt_details(preset_name)
    if details:
        # Return a dictionary with all details
        return {
            "title": details[0],
            "details": details[1],
            "system_prompt": details[2],
            "user_prompt": details[3] if len(details) > 3 else ""
        }
    return {"title": "", "details": "", "system_prompt": "", "user_prompt": ""}


def clear_chat():
    # Return empty list for chatbot and None for conversation_id
    return gr.update(value=[]), None


# FIXME - add additional features....
def chat_wrapper(message, history, media_content, selected_parts, api_endpoint, api_key, custom_prompt, conversation_id, save_conversation, temperature, system_prompt, max_tokens=None, top_p=None, frequency_penalty=None, presence_penalty=None, stop_sequence=None):
    try:
        if save_conversation:
            if conversation_id is None:
                # Create a new conversation
                media_id = media_content.get('id', None)
                conversation_name = f"Chat about {media_content.get('title', 'Unknown Media')} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                conversation_id = create_chat_conversation(media_id, conversation_name)

            # Add user message to the database
            user_message_id = add_chat_message(conversation_id, "user", message)

        # Include the selected parts and custom_prompt only for the first message
        if not history and selected_parts:
            message_body = "\n".join(selected_parts)
            full_message = f"{custom_prompt}\n\n{message}\n\n{message_body}"
        elif custom_prompt:
            full_message = f"{custom_prompt}\n\n{message}"
        else:
            full_message = message

        # Generate bot response
        bot_message = chat(full_message, history, media_content, selected_parts, api_endpoint, api_key, custom_prompt, temperature, system_prompt)

        if save_conversation:
            # Add assistant message to the database
            add_chat_message(conversation_id, "assistant", bot_message)

        # Update history
        history.append((message, bot_message))

        return bot_message, history, conversation_id
    except Exception as e:
        logging.error(f"Error in chat wrapper: {str(e)}")
        return "An error occurred.", history, conversation_id



def search_conversations(query):
    try:
        conversations = search_chat_conversations(query)
        if not conversations:
            print(f"Debug - Search Conversations - No results found for query: {query}")
            return gr.update(choices=[])

        conversation_options = [
            (f"{c['conversation_name']} (Media: {c['media_title']}, ID: {c['id']})", c['id'])
            for c in conversations
        ]
        print(f"Debug - Search Conversations - Options: {conversation_options}")
        return gr.update(choices=conversation_options)
    except Exception as e:
        print(f"Debug - Search Conversations - Error: {str(e)}")
        return gr.update(choices=[])


def load_conversation(conversation_id):
    if not conversation_id:
        return [], None

    messages = get_chat_messages(conversation_id)
    history = [
        (msg['message'], None) if msg['sender'] == 'user' else (None, msg['message'])
        for msg in messages
    ]
    return history, conversation_id


def update_message_in_chat(message_id, new_text, history):
    update_chat_message(message_id, new_text)
    updated_history = [(msg1, msg2) if msg1[1] != message_id and msg2[1] != message_id
                       else ((new_text, msg1[1]) if msg1[1] == message_id else (new_text, msg2[1]))
                       for msg1, msg2 in history]
    return updated_history


def delete_message_from_chat(message_id, history):
    delete_chat_message(message_id)
    updated_history = [(msg1, msg2) for msg1, msg2 in history if msg1[1] != message_id and msg2[1] != message_id]
    return updated_history


def create_chat_interface():
    custom_css = """
    .chatbot-container .message-wrap .message {
        font-size: 14px !important;
    }
    """
    with gr.TabItem("Remote LLM Chat (Horizontal)"):
        gr.Markdown("# Chat with a designated LLM Endpoint, using your selected item as starting context")
        chat_history = gr.State([])
        media_content = gr.State({})
        selected_parts = gr.State([])
        conversation_id = gr.State(None)

        with gr.Row():
            with gr.Column(scale=1):
                search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
                search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title", label="Search By")
                search_button = gr.Button("Search")
                items_output = gr.Dropdown(label="Select Item", choices=[], interactive=True)
                item_mapping = gr.State({})
                with gr.Row():
                    use_content = gr.Checkbox(label="Use Content")
                    use_summary = gr.Checkbox(label="Use Summary")
                    use_prompt = gr.Checkbox(label="Use Prompt")
                    save_conversation = gr.Checkbox(label="Save Conversation", value=False, visible=True)
                with gr.Row():
                    temperature = gr.Slider(label="Temperature", minimum=0.00, maximum=1.0, step=0.05, value=0.7)
                with gr.Row():
                    conversation_search = gr.Textbox(label="Search Conversations")
                with gr.Row():
                    search_conversations_btn = gr.Button("Search Conversations")
                with gr.Row():
                    previous_conversations = gr.Dropdown(label="Select Conversation", choices=[], interactive=True)
                with gr.Row():
                    load_conversations_btn = gr.Button("Load Selected Conversation")

                api_endpoint = gr.Dropdown(label="Select API Endpoint", choices=["Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"])
                api_key = gr.Textbox(label="API Key (if required)", type="password")
                custom_prompt_checkbox = gr.Checkbox(label="Use a Custom Prompt",
                                                     value=False,
                                                     visible=True)
                preset_prompt_checkbox = gr.Checkbox(label="Use a pre-set Prompt",
                                                     value=False,
                                                     visible=True)
                preset_prompt = gr.Dropdown(label="Select Preset Prompt",
                                            choices=load_preset_prompts(),
                                            visible=False)
                user_prompt = gr.Textbox(label="Custom Prompt",
                                                 placeholder="Enter custom prompt here",
                                                 lines=3,
                                                 visible=False)
                system_prompt_input = gr.Textbox(label="System Prompt",
                                                 value="You are a helpful AI assitant",
                                                 lines=3,
                                                 visible=False)
            with gr.Column():
                chatbot = gr.Chatbot(height=600, elem_classes="chatbot-container")
                msg = gr.Textbox(label="Enter your message")
                submit = gr.Button("Submit")
                clear_chat_button = gr.Button("Clear Chat")

                edit_message_id = gr.Number(label="Message ID to Edit", visible=False)
                edit_message_text = gr.Textbox(label="Edit Message", visible=False)
                update_message_button = gr.Button("Update Message", visible=False)

                delete_message_id = gr.Number(label="Message ID to Delete", visible=False)
                delete_message_button = gr.Button("Delete Message", visible=False)

                save_chat_history_to_db = gr.Button("Save Chat History to DataBase")
                save_chat_history_as_file = gr.Button("Save Chat History as File")
                download_file = gr.File(label="Download Chat History")
                save_status = gr.Textbox(label="Save Status", interactive=False)

        # Restore original functionality
        search_button.click(
            fn=update_dropdown,
            inputs=[search_query_input, search_type_input],
            outputs=[items_output, item_mapping]
        )

        def save_chat_wrapper(history, conversation_id, media_content):
            file_path = save_chat_history(history, conversation_id, media_content)
            if file_path:
                return file_path, f"Chat history saved successfully as {os.path.basename(file_path)}!"
            else:
                return None, "Error saving chat history. Please check the logs and try again."

        save_chat_history_as_file.click(
            save_chat_wrapper,
            inputs=[chatbot, conversation_id, media_content],
            outputs=[download_file, save_status]
        )

        def update_prompts(preset_name):
            prompts = update_user_prompt(preset_name)
            return (
                gr.update(value=prompts["user_prompt"], visible=True),
                gr.update(value=prompts["system_prompt"], visible=True)
            )

        def clear_chat():
            return [], None  # Return empty list for chatbot and None for conversation_id

        clear_chat_button.click(
            clear_chat,
            outputs=[chatbot, conversation_id]
        )
        preset_prompt.change(
            update_prompts,
            inputs=preset_prompt,
            outputs=[user_prompt, system_prompt_input]
        )
        custom_prompt_checkbox.change(
            fn=lambda x: (gr.update(visible=x), gr.update(visible=x)),
            inputs=[custom_prompt_checkbox],
            outputs=[user_prompt, system_prompt_input]
        )
        preset_prompt_checkbox.change(
            fn=lambda x: gr.update(visible=x),
            inputs=[preset_prompt_checkbox],
            outputs=[preset_prompt]
        )

        submit.click(
            chat_wrapper,
            inputs=[msg, chatbot, media_content, selected_parts, api_endpoint, api_key, user_prompt,
                    conversation_id, save_conversation, temperature, system_prompt_input],
            outputs=[msg, chatbot, conversation_id]
        ).then(# Clear the message box after submission
            lambda x: gr.update(value=""),
            inputs=[chatbot],
            outputs=[msg]
        ).then(# Clear the user prompt after the first message
            lambda: (gr.update(value=""), gr.update(value="")),
            outputs=[user_prompt, system_prompt_input]
        )

        items_output.change(
            update_chat_content,
            inputs=[items_output, use_content, use_summary, use_prompt, item_mapping],
            outputs=[media_content, selected_parts]
        )
        use_content.change(update_selected_parts, inputs=[use_content, use_summary, use_prompt],
                           outputs=[selected_parts])
        use_summary.change(update_selected_parts, inputs=[use_content, use_summary, use_prompt],
                           outputs=[selected_parts])
        use_prompt.change(update_selected_parts, inputs=[use_content, use_summary, use_prompt],
                          outputs=[selected_parts])
        items_output.change(debug_output, inputs=[media_content, selected_parts], outputs=[])

        search_conversations_btn.click(
            search_conversations,
            inputs=[conversation_search],
            outputs=[previous_conversations]
        )

        load_conversations_btn.click(
            clear_chat,
            outputs=[chatbot, chat_history]
        ).then(
            load_conversation,
            inputs=[previous_conversations],
            outputs=[chatbot, conversation_id]
        )

        previous_conversations.change(
            load_conversation,
            inputs=[previous_conversations],
            outputs=[chat_history]
        )

        update_message_button.click(
            update_message_in_chat,
            inputs=[edit_message_id, edit_message_text, chat_history],
            outputs=[chatbot]
        )

        delete_message_button.click(
            delete_message_from_chat,
            inputs=[delete_message_id, chat_history],
            outputs=[chatbot]
        )

        save_chat_history_as_file.click(
            save_chat_history,
            inputs=[chatbot, conversation_id],
            outputs=[download_file]
        )

        save_chat_history_to_db.click(
            save_chat_history_to_db_wrapper,
            inputs=[chatbot, conversation_id, media_content],
            outputs=[conversation_id, gr.Textbox(label="Save Status")]
        )

        chatbot.select(show_edit_message, None, [edit_message_text, edit_message_id, update_message_button])
        chatbot.select(show_delete_message, None, [delete_message_id, delete_message_button])


def create_chat_interface_stacked():
    custom_css = """
    .chatbot-container .message-wrap .message {
        font-size: 14px !important;
    }
    """
    with gr.TabItem("Remote LLM Chat - Stacked"):
        gr.Markdown("# Stacked Chat")
        chat_history = gr.State([])
        media_content = gr.State({})
        selected_parts = gr.State([])
        conversation_id = gr.State(None)

        with gr.Row():
            with gr.Column():
                search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
                search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title", label="Search By")
                search_button = gr.Button("Search")
                items_output = gr.Dropdown(label="Select Item", choices=[], interactive=True)
                item_mapping = gr.State({})
                with gr.Row():
                    use_content = gr.Checkbox(label="Use Content")
                    use_summary = gr.Checkbox(label="Use Summary")
                    use_prompt = gr.Checkbox(label="Use Prompt")
                    save_conversation = gr.Checkbox(label="Save Conversation", value=False, visible=True)
                    temp = gr.Slider(label="Temperature", minimum=0.00, maximum=1.0, step=0.05, value=0.7)
                with gr.Row():
                    conversation_search = gr.Textbox(label="Search Conversations")
                with gr.Row():
                    previous_conversations = gr.Dropdown(label="Select Conversation", choices=[], interactive=True)
                with gr.Row():
                    search_conversations_btn = gr.Button("Search Conversations")
                    load_conversations_btn = gr.Button("Load Selected Conversation")
            with gr.Column():
                api_endpoint = gr.Dropdown(label="Select API Endpoint", choices=["Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter", "Mistral", "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"])
                api_key = gr.Textbox(label="API Key (if required)", type="password")
                preset_prompt = gr.Dropdown(label="Select Preset Prompt",
                                            choices=load_preset_prompts(),
                                            visible=True)
                system_prompt = gr.Textbox(label="System Prompt",
                                           value="You are a helpful AI assistant.",
                                           lines=3,
                                           visible=True)
                user_prompt = gr.Textbox(label="Custom User Prompt",
                                         placeholder="Enter custom prompt here",
                                         lines=3,
                                         visible=True)
                gr.Markdown("Scroll down for the chat window...")
        with gr.Row():
            with gr.Column(scale=1):
                chatbot = gr.Chatbot(height=600, elem_classes="chatbot-container")
                msg = gr.Textbox(label="Enter your message")
        with gr.Row():
            with gr.Column():
                submit = gr.Button("Submit")
                clear_chat_button = gr.Button("Clear Chat")

                edit_message_id = gr.Number(label="Message ID to Edit", visible=False)
                edit_message_text = gr.Textbox(label="Edit Message", visible=False)
                update_message_button = gr.Button("Update Message", visible=False)

                delete_message_id = gr.Number(label="Message ID to Delete", visible=False)
                delete_message_button = gr.Button("Delete Message", visible=False)
                save_chat_history_to_db = gr.Button("Save Chat History to DataBase")
                save_chat_history_as_file = gr.Button("Save Chat History as File")
            with gr.Column():
                download_file = gr.File(label="Download Chat History")

        # Restore original functionality
        search_button.click(
            fn=update_dropdown,
            inputs=[search_query_input, search_type_input],
            outputs=[items_output, item_mapping]
        )

        def update_prompts(preset_name):
            prompts = update_user_prompt(preset_name)
            return (
                gr.update(value=prompts["user_prompt"], visible=True),
                gr.update(value=prompts["system_prompt"], visible=True)
            )

        clear_chat_button.click(
            clear_chat,
            outputs=[chatbot, conversation_id]
        )
        preset_prompt.change(
            update_prompts,
            inputs=preset_prompt,
            outputs=[user_prompt, system_prompt]
        )

        submit.click(
            chat_wrapper,
            inputs=[msg, chatbot, media_content, selected_parts, api_endpoint, api_key, user_prompt,
                    conversation_id, save_conversation, temp, system_prompt],
            outputs=[msg, chatbot, conversation_id]
        ).then(# Clear the message box after submission
            lambda x: gr.update(value=""),
            inputs=[chatbot],
            outputs=[msg]
        ).then(# Clear the user prompt after the first message
            lambda: gr.update(value=""),
            outputs=[user_prompt, system_prompt]
        )

        items_output.change(
            update_chat_content,
            inputs=[items_output, use_content, use_summary, use_prompt, item_mapping],
            outputs=[media_content, selected_parts]
        )
        use_content.change(update_selected_parts, inputs=[use_content, use_summary, use_prompt],
                           outputs=[selected_parts])
        use_summary.change(update_selected_parts, inputs=[use_content, use_summary, use_prompt],
                           outputs=[selected_parts])
        use_prompt.change(update_selected_parts, inputs=[use_content, use_summary, use_prompt],
                          outputs=[selected_parts])
        items_output.change(debug_output, inputs=[media_content, selected_parts], outputs=[])

        search_conversations_btn.click(
            search_conversations,
            inputs=[conversation_search],
            outputs=[previous_conversations]
        )

        load_conversations_btn.click(
            clear_chat,
            outputs=[chatbot, chat_history]
        ).then(
            load_conversation,
            inputs=[previous_conversations],
            outputs=[chatbot, conversation_id]
        )

        previous_conversations.change(
            load_conversation,
            inputs=[previous_conversations],
            outputs=[chat_history]
        )

        update_message_button.click(
            update_message_in_chat,
            inputs=[edit_message_id, edit_message_text, chat_history],
            outputs=[chatbot]
        )

        delete_message_button.click(
            delete_message_from_chat,
            inputs=[delete_message_id, chat_history],
            outputs=[chatbot]
        )

        save_chat_history_as_file.click(
            save_chat_history,
            inputs=[chatbot, conversation_id],
            outputs=[download_file]
        )

        save_chat_history_to_db.click(
            save_chat_history_to_db_wrapper,
            inputs=[chatbot, conversation_id, media_content],
            outputs=[conversation_id, gr.Textbox(label="Save Status")]
        )

        chatbot.select(show_edit_message, None, [edit_message_text, edit_message_id, update_message_button])
        chatbot.select(show_delete_message, None, [delete_message_id, delete_message_button])


# FIXME - System prompts
def create_chat_interface_multi_api():
    custom_css = """
    .chatbot-container .message-wrap .message {
        font-size: 14px !important;
    }
    .chat-window {
        height: 400px;
        overflow-y: auto;
    }
    """
    with gr.TabItem("One Prompt - Multiple APIs"):
        gr.Markdown("# One Prompt but Multiple API Chat Interface")

        with gr.Row():
            with gr.Column(scale=1):
                search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
                search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title",
                                             label="Search By")
                search_button = gr.Button("Search")
                items_output = gr.Dropdown(label="Select Item", choices=[], interactive=True)
                item_mapping = gr.State({})
                with gr.Row():
                    use_content = gr.Checkbox(label="Use Content")
                    use_summary = gr.Checkbox(label="Use Summary")
                    use_prompt = gr.Checkbox(label="Use Prompt")
            with gr.Column():
                preset_prompt = gr.Dropdown(label="Select Preset Prompt", choices=load_preset_prompts(), visible=True)
                system_prompt = gr.Textbox(label="System Prompt", value="You are a helpful AI assistant.", lines=5)
                user_prompt = gr.Textbox(label="Modify Prompt", lines=5, value=".")

        with gr.Row():
            chatbots = []
            api_endpoints = []
            api_keys = []
            temperatures = []
            for i in range(3):
                with gr.Column():
                    gr.Markdown(f"### Chat Window {i + 1}")
                    api_endpoint = gr.Dropdown(label=f"API Endpoint {i + 1}",
                                               choices=["Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq",
                                                        "DeepSeek", "Mistral", "OpenRouter", "Llama.cpp", "Kobold", "Ooba",
                                                        "Tabbyapi", "VLLM","ollama", "HuggingFace"])
                    api_key = gr.Textbox(label=f"API Key {i + 1} (if required)", type="password")
                    temperature = gr.Slider(label=f"Temperature {i + 1}", minimum=0.0, maximum=1.0, step=0.05, value=0.7)
                    chatbot = gr.Chatbot(height=800, elem_classes="chat-window")
                    chatbots.append(chatbot)
                    api_endpoints.append(api_endpoint)
                    api_keys.append(api_key)
                    temperatures.append(temperature)

        with gr.Row():
            msg = gr.Textbox(label="Enter your message", scale=4)
            submit = gr.Button("Submit", scale=1)
            # FIXME - clear chat
        #     clear_chat_button = gr.Button("Clear Chat")
        #
        # clear_chat_button.click(
        #     clear_chat,
        #     outputs=[chatbot]
        # )

        # State variables
        chat_history = [gr.State([]) for _ in range(3)]
        media_content = gr.State({})
        selected_parts = gr.State([])
        conversation_id = gr.State(None)

        # Event handlers
        search_button.click(
            fn=update_dropdown,
            inputs=[search_query_input, search_type_input],
            outputs=[items_output, item_mapping]
        )

        preset_prompt.change(update_user_prompt, inputs=preset_prompt, outputs=user_prompt)

        def chat_wrapper_multi(message, custom_prompt, system_prompt, *args):
            chat_histories = args[:3]
            chatbots = args[3:6]
            api_endpoints = args[6:9]
            api_keys = args[9:12]
            temperatures = args[12:15]
            media_content = args[15]
            selected_parts = args[16]

            new_chat_histories = []
            new_chatbots = []

            for i in range(3):
                # Call chat_wrapper with dummy values for conversation_id and save_conversation
                bot_message, new_history, _ = chat_wrapper(
                    message, chat_histories[i], media_content, selected_parts,
                    api_endpoints[i], api_keys[i], custom_prompt, None,  # None for conversation_id
                    False,  # False for save_conversation
                    temperature=temperatures[i],
                    system_prompt=system_prompt
                )

                new_chatbot = chatbots[i] + [(message, bot_message)]

                new_chat_histories.append(new_history)
                new_chatbots.append(new_chatbot)

            return [gr.update(value="")] + new_chatbots + new_chat_histories

        # In the create_chat_interface_multi_api function:
        submit.click(
            chat_wrapper_multi,
            inputs=[msg, user_prompt, system_prompt] + chat_history + chatbots + api_endpoints + api_keys + temperatures +
                   [media_content, selected_parts],
            outputs=[msg] + chatbots + chat_history
        ).then(
            lambda: (gr.update(value=""), gr.update(value="")),
            outputs=[msg, user_prompt]
        )

        items_output.change(
            update_chat_content,
            inputs=[items_output, use_content, use_summary, use_prompt, item_mapping],
            outputs=[media_content, selected_parts]
        )

        for checkbox in [use_content, use_summary, use_prompt]:
            checkbox.change(
                update_selected_parts,
                inputs=[use_content, use_summary, use_prompt],
                outputs=[selected_parts]
            )


def create_chat_interface_four():
    custom_css = """
    .chatbot-container .message-wrap .message {
        font-size: 14px !important;
    }
    .chat-window {
        height: 400px;
        overflow-y: auto;
    }
    """
    with gr.TabItem("Four Independent API Chats"):
        gr.Markdown("# Four Independent API Chat Interfaces")

        with gr.Row():
            with gr.Column():
                preset_prompt = gr.Dropdown(label="Select Preset Prompt", choices=load_preset_prompts(), visible=True)
                user_prompt = gr.Textbox(label="Modify Prompt", lines=3, value=".")
            with gr.Column():
                gr.Markdown("Scroll down for the chat windows...")
        chat_interfaces = []
        for row in range(2):
            with gr.Row():
                for col in range(2):
                    i = row * 2 + col
                    with gr.Column():
                        gr.Markdown(f"### Chat Window {i + 1}")
                        api_endpoint = gr.Dropdown(label=f"API Endpoint {i + 1}",
                                                   choices=["Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq",
                                                            "DeepSeek", "Mistral", "OpenRouter", "Llama.cpp", "Kobold", "Ooba",
                                                            "Tabbyapi", "VLLM","ollama", "HuggingFace"])
                        api_key = gr.Textbox(label=f"API Key {i + 1} (if required)", type="password")
                        temperature = gr.Slider(label=f"Temperature {i + 1}", minimum=0.0, maximum=1.0, step=0.05, value=0.7)
                        chatbot = gr.Chatbot(height=400, elem_classes="chat-window")
                        msg = gr.Textbox(label=f"Enter your message for Chat {i + 1}")
                        submit = gr.Button(f"Submit to Chat {i + 1}")

                        chat_interfaces.append({
                            'api_endpoint': api_endpoint,
                            'api_key': api_key,
                            'temperature': temperature,
                            'chatbot': chatbot,
                            'msg': msg,
                            'submit': submit,
                            'chat_history': gr.State([])
                        })

        preset_prompt.change(update_user_prompt, inputs=preset_prompt, outputs=user_prompt)

        def chat_wrapper_single(message, chat_history, api_endpoint, api_key, temperature, user_prompt):
            logging.debug(f"Chat Wrapper Single - Message: {message}, Chat History: {chat_history}")
            new_msg, new_history, _ = chat_wrapper(
                message, chat_history, {}, [],  # Empty media_content and selected_parts
                api_endpoint, api_key, user_prompt, None,  # No conversation_id
                False,  # Not saving conversation
                temperature=temperature, system_prompt=""
            )
            chat_history.append((message, new_msg))
            return "", chat_history, chat_history

        for interface in chat_interfaces:
            logging.debug(f"Chat Interface - Clicked Submit for Chat {interface['chatbot']}"),
            interface['submit'].click(
                chat_wrapper_single,
                inputs=[
                    interface['msg'],
                    interface['chat_history'],
                    interface['api_endpoint'],
                    interface['api_key'],
                    interface['temperature'],
                    user_prompt
                ],
                outputs=[
                    interface['msg'],
                    interface['chatbot'],
                    interface['chat_history']
                ]
            )

def chat_wrapper_single(message, chat_history, chatbot, api_endpoint, api_key, temperature, media_content,
                       selected_parts, conversation_id, save_conversation, user_prompt):
    new_msg, new_history, new_conv_id = chat_wrapper(
        message, chat_history, media_content, selected_parts,
        api_endpoint, api_key, user_prompt, conversation_id,
        save_conversation, temperature, system_prompt=""
    )

    if new_msg:
        updated_chatbot = chatbot + [(message, new_msg)]
    else:
        updated_chatbot = chatbot

    return new_msg, updated_chatbot, new_history, new_conv_id


# FIXME - Finish implementing functions + testing/valdidation
def create_chat_management_tab():
    with gr.TabItem("Chat Management"):
        gr.Markdown("# Chat Management")

        with gr.Row():
            search_query = gr.Textbox(label="Search Conversations")
            search_button = gr.Button("Search")

        conversation_list = gr.Dropdown(label="Select Conversation", choices=[])
        conversation_mapping = gr.State({})

        with gr.Tabs():
            with gr.TabItem("Edit"):
                chat_content = gr.TextArea(label="Chat Content (JSON)", lines=20, max_lines=50)
                save_button = gr.Button("Save Changes")

            with gr.TabItem("Preview"):
                chat_preview = gr.HTML(label="Chat Preview")
        result_message = gr.Markdown("")

        def search_conversations(query):
            conversations = search_chat_conversations(query)
            choices = [f"{conv['conversation_name']} (Media: {conv['media_title']}, ID: {conv['id']})" for conv in
                       conversations]
            mapping = {choice: conv['id'] for choice, conv in zip(choices, conversations)}
            return gr.update(choices=choices), mapping

        def load_conversations(selected, conversation_mapping):
            logging.info(f"Selected: {selected}")
            logging.info(f"Conversation mapping: {conversation_mapping}")

            try:
                if selected and selected in conversation_mapping:
                    conversation_id = conversation_mapping[selected]
                    messages = get_chat_messages(conversation_id)
                    conversation_data = {
                        "conversation_id": conversation_id,
                        "messages": messages
                    }
                    json_content = json.dumps(conversation_data, indent=2)

                    # Create HTML preview
                    html_preview = "<div style='max-height: 500px; overflow-y: auto;'>"
                    for msg in messages:
                        sender_style = "background-color: #e6f3ff;" if msg[
                                                                           'sender'] == 'user' else "background-color: #f0f0f0;"
                        html_preview += f"<div style='margin-bottom: 10px; padding: 10px; border-radius: 5px; {sender_style}'>"
                        html_preview += f"<strong>{msg['sender']}:</strong> {html.escape(msg['message'])}<br>"
                        html_preview += f"<small>Timestamp: {msg['timestamp']}</small>"
                        html_preview += "</div>"
                    html_preview += "</div>"

                    logging.info("Returning json_content and html_preview")
                    return json_content, html_preview
                else:
                    logging.warning("No conversation selected or not in mapping")
                    return "", "<p>No conversation selected</p>"
            except Exception as e:
                logging.error(f"Error in load_conversations: {str(e)}")
                return f"Error: {str(e)}", "<p>Error loading conversation</p>"

        def validate_conversation_json(content):
            try:
                data = json.loads(content)
                if not isinstance(data, dict):
                    return False, "Invalid JSON structure: root should be an object"
                if "conversation_id" not in data or not isinstance(data["conversation_id"], int):
                    return False, "Missing or invalid conversation_id"
                if "messages" not in data or not isinstance(data["messages"], list):
                    return False, "Missing or invalid messages array"
                for msg in data["messages"]:
                    if not all(key in msg for key in ["sender", "message"]):
                        return False, "Invalid message structure: missing required fields"
                return True, data
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON: {str(e)}"

        def save_conversation(selected, conversation_mapping, content):
            if not selected or selected not in conversation_mapping:
                return "Please select a conversation before saving.", "<p>No changes made</p>"

            conversation_id = conversation_mapping[selected]
            is_valid, result = validate_conversation_json(content)

            if not is_valid:
                return f"Error: {result}", "<p>No changes made due to error</p>"

            conversation_data = result
            if conversation_data["conversation_id"] != conversation_id:
                return "Error: Conversation ID mismatch.", "<p>No changes made due to ID mismatch</p>"

            try:
                with db.get_connection() as conn:
                    conn.execute("BEGIN TRANSACTION")
                    cursor = conn.cursor()

                    # Backup original conversation
                    cursor.execute("SELECT * FROM ChatMessages WHERE conversation_id = ?", (conversation_id,))
                    original_messages = cursor.fetchall()
                    backup_data = json.dumps({"conversation_id": conversation_id, "messages": original_messages})

                    # You might want to save this backup_data somewhere

                    # Delete existing messages
                    cursor.execute("DELETE FROM ChatMessages WHERE conversation_id = ?", (conversation_id,))

                    # Insert updated messages
                    for message in conversation_data["messages"]:
                        cursor.execute('''
                            INSERT INTO ChatMessages (conversation_id, sender, message, timestamp)
                            VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                        ''', (conversation_id, message["sender"], message["message"], message.get("timestamp")))

                    conn.commit()

                    # Create updated HTML preview
                    html_preview = "<div style='max-height: 500px; overflow-y: auto;'>"
                    for msg in conversation_data["messages"]:
                        sender_style = "background-color: #e6f3ff;" if msg['sender'] == 'user' else "background-color: #f0f0f0;"
                        html_preview += f"<div style='margin-bottom: 10px; padding: 10px; border-radius: 5px; {sender_style}'>"
                        html_preview += f"<strong>{msg['sender']}:</strong> {html.escape(msg['message'])}<br>"
                        html_preview += f"<small>Timestamp: {msg.get('timestamp', 'N/A')}</small>"
                        html_preview += "</div>"
                    html_preview += "</div>"

                    return "Conversation updated successfully.", html_preview
            except sqlite3.Error as e:
                conn.rollback()
                logging.error(f"Database error in save_conversation: {e}")
                return f"Error updating conversation: {str(e)}", "<p>Error occurred while saving</p>"
            except Exception as e:
                conn.rollback()
                logging.error(f"Unexpected error in save_conversation: {e}")
                return f"Unexpected error: {str(e)}", "<p>Unexpected error occurred</p>"

        def parse_formatted_content(formatted_content):
            lines = formatted_content.split('\n')
            conversation_id = int(lines[0].split(': ')[1])
            timestamp = lines[1].split(': ')[1]
            history = []
            current_role = None
            current_content = None
            for line in lines[3:]:
                if line.startswith("Role: "):
                    if current_role is not None:
                        history.append({"role": current_role, "content": ["", current_content]})
                    current_role = line.split(': ')[1]
                elif line.startswith("Content: "):
                    current_content = line.split(': ', 1)[1]
            if current_role is not None:
                history.append({"role": current_role, "content": ["", current_content]})
            return json.dumps({
                "conversation_id": conversation_id,
                "timestamp": timestamp,
                "history": history
            }, indent=2)

        search_button.click(
            search_conversations,
            inputs=[search_query],
            outputs=[conversation_list, conversation_mapping]
        )

        conversation_list.change(
            load_conversations,
            inputs=[conversation_list, conversation_mapping],
            outputs=[chat_content, chat_preview]
        )

        save_button.click(
            save_conversation,
            inputs=[conversation_list, conversation_mapping, chat_content],
            outputs=[result_message, chat_preview]
        )

    return search_query, search_button, conversation_list, conversation_mapping, chat_content, save_button, result_message, chat_preview


# FIXME - busted and incomplete
# Mock function to simulate LLM processing
def process_with_llm(workflow, context, prompt):
    return f"LLM output for {workflow} with context: {context[:30]}... and prompt: {prompt[:30]}..."


# Load workflows from a JSON file
json_path = Path('./Helper_Scripts/Workflows/Workflows.json')
with json_path.open('r') as f:
    workflows = json.load(f)


# FIXME - broken Completely. Doesn't work.
def chat_workflows_tab():
    with gr.TabItem("Chat Workflows"):
        with gr.Blocks() as chat_workflows_block:
            gr.Markdown("# Workflows using LLMs")

            workflow_selector = gr.Dropdown(label="Select Workflow", choices=[wf['name'] for wf in workflows])
            context_input = gr.Textbox(label="Context", lines=5)

            # Create lists to hold UI components
            prompt_inputs = []
            process_buttons = []
            output_boxes = []
            max_prompts = max(len(wf['prompts']) for wf in workflows)

            # Pre-create the maximum number of prompt sections
            for i in range(max_prompts):
                prompt_input = gr.Textbox(label=f"Prompt {i + 1}", lines=2, visible=False)
                output_box = gr.Textbox(label=f"Output {i + 1}", lines=5, visible=False)
                process_button = gr.Button(f"Process Prompt {i + 1}", visible=False)

                prompt_inputs.append(prompt_input)
                output_boxes.append(output_box)
                process_buttons.append(process_button)

                process_button.click(
                    fn=lambda context, prompt, workflow_name, step=i: process(context, prompt, workflow_name, step),
                    inputs=[context_input, prompt_input, workflow_selector],
                    outputs=[output_box]
                )

            def process(context, prompt, workflow_name, step):
                selected_workflow = next(wf for wf in workflows if wf['name'] == workflow_name)
                # Update context with previous outputs
                for j in range(step):
                    context += f"\n\n{output_boxes[j].value}"
                result = process_with_llm(selected_workflow['name'], context, prompt)
                return result

            def update_prompt_sections(workflow_name):
                selected_workflow = next(wf for wf in workflows if wf['name'] == workflow_name)
                num_prompts = len(selected_workflow['prompts'])

                for i in range(max_prompts):
                    if i < num_prompts:
                        prompt_inputs[i].visible = True
                        prompt_inputs[i].value = selected_workflow['prompts'][i]
                        process_buttons[i].visible = True
                        output_boxes[i].visible = True
                    else:
                        prompt_inputs[i].visible = False
                        process_buttons[i].visible = False
                        output_boxes[i].visible = False

            # Bind the workflow selector to update the UI
            workflow_selector.change(update_prompt_sections, inputs=[workflow_selector], outputs=[])

        return chat_workflows_block




#
# End of Chat Interface Tab Functions
################################################################################################################################################################################################################################
#
# Media Edit Tab Functions



def create_media_edit_tab():
    with gr.TabItem("Edit Existing Items"):
        gr.Markdown("# Search and Edit Media Items")

        with gr.Row():
            search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
            search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title", label="Search By")
            search_button = gr.Button("Search")

        with gr.Row():
            items_output = gr.Dropdown(label="Select Item", choices=[], interactive=True)
            item_mapping = gr.State({})

        content_input = gr.Textbox(label="Edit Content", lines=10)
        prompt_input = gr.Textbox(label="Edit Prompt", lines=3)
        summary_input = gr.Textbox(label="Edit Summary", lines=5)

        update_button = gr.Button("Update Media Content")
        status_message = gr.Textbox(label="Status", interactive=False)

        search_button.click(
            fn=update_dropdown,
            inputs=[search_query_input, search_type_input],
            outputs=[items_output, item_mapping]
        )

        def load_selected_media_content(selected_item, item_mapping):
            if selected_item and item_mapping and selected_item in item_mapping:
                media_id = item_mapping[selected_item]
                content, prompt, summary = fetch_item_details(media_id)
                return content, prompt, summary
            return "No item selected or invalid selection", "", ""

        items_output.change(
            fn=load_selected_media_content,
            inputs=[items_output, item_mapping],
            outputs=[content_input, prompt_input, summary_input]
        )

        update_button.click(
            fn=update_media_content,
            inputs=[items_output, item_mapping, content_input, prompt_input, summary_input],
            outputs=status_message
        )


def create_media_edit_and_clone_tab():
    with gr.TabItem("Clone and Edit Existing Items"):
        gr.Markdown("# Search, Edit, and Clone Existing Items")

        with gr.Row():
            with gr.Column():
                search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
                search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title",
                                         label="Search By")
            with gr.Column():
                search_button = gr.Button("Search")
                clone_button = gr.Button("Clone Item")
            save_clone_button = gr.Button("Save Cloned Item", visible=False)
        with gr.Row():
            items_output = gr.Dropdown(label="Select Item", choices=[], interactive=True)
            item_mapping = gr.State({})

        content_input = gr.Textbox(label="Edit Content", lines=10)
        prompt_input = gr.Textbox(label="Edit Prompt", lines=3)
        summary_input = gr.Textbox(label="Edit Summary", lines=5)
        new_title_input = gr.Textbox(label="New Title (for cloning)", visible=False)
        status_message = gr.Textbox(label="Status", interactive=False)

        search_button.click(
            fn=update_dropdown,
            inputs=[search_query_input, search_type_input],
            outputs=[items_output, item_mapping]
        )

        def load_selected_media_content(selected_item, item_mapping):
            if selected_item and item_mapping and selected_item in item_mapping:
                media_id = item_mapping[selected_item]
                content, prompt, summary = fetch_item_details(media_id)
                return content, prompt, summary, gr.update(visible=True), gr.update(visible=False)
            return "No item selected or invalid selection", "", "", gr.update(visible=False), gr.update(visible=False)

        items_output.change(
            fn=load_selected_media_content,
            inputs=[items_output, item_mapping],
            outputs=[content_input, prompt_input, summary_input, clone_button, save_clone_button]
        )

        def prepare_for_cloning(selected_item):
            return gr.update(value=f"Copy of {selected_item}", visible=True), gr.update(visible=True)

        clone_button.click(
            fn=prepare_for_cloning,
            inputs=[items_output],
            outputs=[new_title_input, save_clone_button]
        )

        def save_cloned_item(selected_item, item_mapping, content, prompt, summary, new_title):
            if selected_item and item_mapping and selected_item in item_mapping:
                original_media_id = item_mapping[selected_item]
                try:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()

                        # Fetch the original item's details
                        cursor.execute("SELECT type, url FROM Media WHERE id = ?", (original_media_id,))
                        original_type, original_url = cursor.fetchone()

                        # Generate a new unique URL
                        new_url = f"{original_url}_clone_{uuid.uuid4().hex[:8]}"

                        # Insert new item into Media table
                        cursor.execute("""
                            INSERT INTO Media (title, content, url, type)
                            VALUES (?, ?, ?, ?)
                        """, (new_title, content, new_url, original_type))

                        new_media_id = cursor.lastrowid

                        # Insert new item into MediaModifications table
                        cursor.execute("""
                            INSERT INTO MediaModifications (media_id, prompt, summary, modification_date)
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """, (new_media_id, prompt, summary))

                        # Copy keywords from the original item
                        cursor.execute("""
                            INSERT INTO MediaKeywords (media_id, keyword_id)
                            SELECT ?, keyword_id
                            FROM MediaKeywords
                            WHERE media_id = ?
                        """, (new_media_id, original_media_id))

                        # Update full-text search index
                        cursor.execute("""
                            INSERT INTO media_fts (rowid, title, content)
                            VALUES (?, ?, ?)
                        """, (new_media_id, new_title, content))

                        conn.commit()

                    return f"Cloned item saved successfully with ID: {new_media_id}", gr.update(
                        visible=False), gr.update(visible=False)
                except Exception as e:
                    logging.error(f"Error saving cloned item: {e}")
                    return f"Error saving cloned item: {str(e)}", gr.update(visible=True), gr.update(visible=True)
            else:
                return "No item selected or invalid selection", gr.update(visible=True), gr.update(visible=True)

        save_clone_button.click(
            fn=save_cloned_item,
            inputs=[items_output, item_mapping, content_input, prompt_input, summary_input, new_title_input],
            outputs=[status_message, new_title_input, save_clone_button]
        )


def create_prompt_edit_tab():
    with gr.TabItem("Edit Prompts"):
        with gr.Row():
            with gr.Column():
                prompt_dropdown = gr.Dropdown(
                    label="Select Prompt",
                    choices=[],
                    interactive=True
                )
                prompt_list_button = gr.Button("List Prompts")

            with gr.Column():
                title_input = gr.Textbox(label="Title", placeholder="Enter the prompt title")
                description_input = gr.Textbox(label="Description", placeholder="Enter the prompt description", lines=3)
                system_prompt_input = gr.Textbox(label="System Prompt", placeholder="Enter the system prompt", lines=3)
                user_prompt_input = gr.Textbox(label="User Prompt", placeholder="Enter the user prompt", lines=3)
                add_prompt_button = gr.Button("Add/Update Prompt")
                add_prompt_output = gr.HTML()

        # Event handlers
        prompt_list_button.click(
            fn=update_prompt_dropdown,
            outputs=prompt_dropdown
        )

        add_prompt_button.click(
            fn=add_or_update_prompt,
            inputs=[title_input, description_input, system_prompt_input, user_prompt_input],
            outputs=add_prompt_output
        )

        # Load prompt details when selected
        prompt_dropdown.change(
            fn=load_prompt_details,
            inputs=[prompt_dropdown],
            outputs=[title_input, description_input, system_prompt_input, user_prompt_input]
        )


def create_prompt_clone_tab():
    with gr.TabItem("Clone and Edit Prompts"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("# Clone and Edit Prompts")
                prompt_dropdown = gr.Dropdown(
                    label="Select Prompt",
                    choices=[],
                    interactive=True
                )
                prompt_list_button = gr.Button("List Prompts")

            with gr.Column():
                title_input = gr.Textbox(label="Title", placeholder="Enter the prompt title")
                description_input = gr.Textbox(label="Description", placeholder="Enter the prompt description", lines=3)
                system_prompt_input = gr.Textbox(label="System Prompt", placeholder="Enter the system prompt", lines=3)
                user_prompt_input = gr.Textbox(label="User Prompt", placeholder="Enter the user prompt", lines=3)
                clone_prompt_button = gr.Button("Clone Selected Prompt")
                save_cloned_prompt_button = gr.Button("Save Cloned Prompt", visible=False)
                add_prompt_output = gr.HTML()

        # Event handlers
        prompt_list_button.click(
            fn=update_prompt_dropdown,
            outputs=prompt_dropdown
        )

        # Load prompt details when selected
        prompt_dropdown.change(
            fn=load_prompt_details,
            inputs=[prompt_dropdown],
            outputs=[title_input, description_input, system_prompt_input, user_prompt_input]
        )

        def prepare_for_cloning(selected_prompt):
            if selected_prompt:
                return gr.update(value=f"Copy of {selected_prompt}"), gr.update(visible=True)
            return gr.update(), gr.update(visible=False)

        clone_prompt_button.click(
            fn=prepare_for_cloning,
            inputs=[prompt_dropdown],
            outputs=[title_input, save_cloned_prompt_button]
        )

        def save_cloned_prompt(title, description, system_prompt, user_prompt):
            try:
                result = add_prompt(title, description, system_prompt, user_prompt)
                if result == "Prompt added successfully.":
                    return result, gr.update(choices=update_prompt_dropdown())
                else:
                    return result, gr.update()
            except Exception as e:
                return f"Error saving cloned prompt: {str(e)}", gr.update()

        save_cloned_prompt_button.click(
            fn=save_cloned_prompt,
            inputs=[title_input, description_input, system_prompt_input, user_prompt_input],
            outputs=[add_prompt_output, prompt_dropdown]
        )


##### Trash Tab
def delete_item(media_id, force):
    return user_delete_item(media_id, force)

def list_trash():
    items = get_trashed_items()
    return "\n".join(
        [f"ID: {item['id']}, Title: {item['title']}, Trashed on: {item['trash_date']}" for item in items])

def empty_trash_ui(days):
    deleted, remaining = empty_trash(days)
    return f"Deleted {deleted} items. {remaining} items remain in trash."

def create_view_trash_tab():
    with gr.TabItem("View Trash"):
        view_button = gr.Button("View Trash")
        trash_list = gr.Textbox(label="Trashed Items")
        view_button.click(list_trash, inputs=[], outputs=trash_list)


def search_prompts_for_deletion(query):
    try:
        with sqlite3.connect('prompts.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, details
                FROM Prompts
                WHERE name LIKE ? OR details LIKE ?
                LIMIT 10
            ''', (f'%{query}%', f'%{query}%'))
            results = cursor.fetchall()

            if not results:
                return "No matching prompts found."

            output = "<h3>Matching Prompts:</h3>"
            for row in results:
                output += f"<p><strong>ID:</strong> {row[0]} | <strong>Name:</strong> {html.escape(row[1])} | <strong>Details:</strong> {html.escape(row[2][:100])}...</p>"
            return output
    except sqlite3.Error as e:
        return f"An error occurred while searching prompts: {e}"


def search_media_for_deletion(query):
    try:
        with sqlite3.connect('media.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, title, description
                FROM media
                WHERE title LIKE ? OR description LIKE ?
                LIMIT 10
            ''', (f'%{query}%', f'%{query}%'))
            results = cursor.fetchall()

            if not results:
                return "No matching media found."

            output = "<h3>Matching Media:</h3>"
            for row in results:
                output += f"<p><strong>ID:</strong> {row[0]} | <strong>Title:</strong> {html.escape(row[1])} | <strong>Description:</strong> {html.escape(row[2][:100])}...</p>"
            return output
    except sqlite3.Error as e:
        return f"An error occurred while searching media: {e}"


def create_delete_trash_tab():
    with gr.TabItem("Delete DB Item"):
        gr.Markdown("# Search and Delete Items from Databases")

        with gr.Row():
            with gr.Column():
                gr.Markdown("## Search and Delete Prompts")
                prompt_search_input = gr.Textbox(label="Search Prompts")
                prompt_search_button = gr.Button("Search Prompts")
                prompt_search_results = gr.HTML()
                prompt_id_input = gr.Number(label="Prompt ID")
                prompt_delete_button = gr.Button("Delete Prompt")
                prompt_delete_output = gr.Textbox(label="Delete Result")

            with gr.Column():
                gr.Markdown("## Search and Delete Media")
                media_search_input = gr.Textbox(label="Search Media")
                media_search_button = gr.Button("Search Media")
                media_search_results = gr.HTML()
                media_id_input = gr.Number(label="Media ID")
                media_force_checkbox = gr.Checkbox(label="Force Delete")
                media_delete_button = gr.Button("Delete Media")
                media_delete_output = gr.Textbox(label="Delete Result")

        prompt_search_button.click(
            search_prompts_for_deletion,
            inputs=[prompt_search_input],
            outputs=prompt_search_results
        )

        prompt_delete_button.click(
            delete_prompt,
            inputs=[prompt_id_input],
            outputs=prompt_delete_output
        )

        media_search_button.click(
            search_media_for_deletion,
            inputs=[media_search_input],
            outputs=media_search_results
        )

        media_delete_button.click(
            delete_item,
            inputs=[media_id_input, media_force_checkbox],
            outputs=media_delete_output
        )

def create_empty_trash_tab():
    with gr.TabItem("Empty Trash"):
        days_input = gr.Slider(minimum=15, maximum=90, step=5, label="Delete items older than (days)")
        empty_button = gr.Button("Empty Trash")
        empty_output = gr.Textbox(label="Result")
        empty_button.click(empty_trash_ui, inputs=[days_input], outputs=empty_output)


#
# End of Media Edit Tab Functions
################################################################################################################
#
# Import Items Tab Functions

def scan_obsidian_vault(vault_path):
    markdown_files = []
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith('.md'):
                markdown_files.append(os.path.join(root, file))
    return markdown_files


def parse_obsidian_note(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    frontmatter = {}
    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if frontmatter_match:
        frontmatter_text = frontmatter_match.group(1)
        import yaml
        frontmatter = yaml.safe_load(frontmatter_text)
        content = content[frontmatter_match.end():]

    tags = re.findall(r'#(\w+)', content)
    links = re.findall(r'\[\[(.*?)\]\]', content)

    return {
        'title': os.path.basename(file_path).replace('.md', ''),
        'content': content,
        'frontmatter': frontmatter,
        'tags': tags,
        'links': links,
        'file_path': file_path  # Add this line
    }


def import_obsidian_vault(vault_path, progress=gr.Progress()):
    try:
        markdown_files = scan_obsidian_vault(vault_path)
        total_files = len(markdown_files)
        imported_files = 0
        errors = []

        for i, file_path in enumerate(markdown_files):
            try:
                note_data = parse_obsidian_note(file_path)
                success, error_msg = import_obsidian_note_to_db(note_data)
                if success:
                    imported_files += 1
                else:
                    errors.append(error_msg)
            except Exception as e:
                error_msg = f"Error processing {file_path}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

            progress((i + 1) / total_files, f"Imported {imported_files} of {total_files} files")
            sleep(0.1)  # Small delay to prevent UI freezing

        return imported_files, total_files, errors
    except Exception as e:
        error_msg = f"Error scanning vault: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return 0, 0, [error_msg]


def process_obsidian_zip(zip_file):
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            imported_files, total_files, errors = import_obsidian_vault(temp_dir)

            return imported_files, total_files, errors
        except zipfile.BadZipFile:
            error_msg = "The uploaded file is not a valid zip file."
            logger.error(error_msg)
            return 0, 0, [error_msg]
        except Exception as e:
            error_msg = f"Error processing zip file: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            return 0, 0, [error_msg]
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

def import_data(file, title, author, keywords, custom_prompt, summary, auto_summarize, api_name, api_key):
    if file is None:
        return "No file uploaded. Please upload a file."

    try:
        logging.debug(f"File object type: {type(file)}")
        logging.debug(f"File object attributes: {dir(file)}")

        if hasattr(file, 'name'):
            file_name = file.name
        else:
            file_name = 'unknown_file'

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt', encoding='utf-8') as temp_file:
            if isinstance(file, str):
                # If file is a string, it's likely file content
                temp_file.write(file)
            elif hasattr(file, 'read'):
                # If file has a 'read' method, it's likely a file-like object
                content = file.read()
                if isinstance(content, bytes):
                    content = content.decode('utf-8')
                temp_file.write(content)
            else:
                # If it's neither a string nor a file-like object, try converting it to a string
                temp_file.write(str(file))

            temp_file.seek(0)
            file_content = temp_file.read()

        logging.debug(f"File name: {file_name}")
        logging.debug(f"File content (first 100 chars): {file_content[:100]}")

        # Create info_dict
        info_dict = {
            'title': title or 'Untitled',
            'uploader': author or 'Unknown',
        }

        # FIXME - Add chunking support... I added chapter chunking specifically for this...
        # Create segments (assuming one segment for the entire content)
        segments = [{'Text': file_content}]

        # Process keywords
        keyword_list = [kw.strip() for kw in keywords.split(',') if kw.strip()]

        # Handle summarization
        if auto_summarize and api_name and api_key:
            summary = perform_summarization(api_name, file_content, custom_prompt, api_key)
        elif not summary:
            summary = "No summary provided"

        # Add to database
        add_media_to_database(
            url=file_name,  # Using filename as URL
            info_dict=info_dict,
            segments=segments,
            summary=summary,
            keywords=keyword_list,
            custom_prompt_input=custom_prompt,
            whisper_model="Imported",  # Indicating this was an imported file
            media_type="document"
        )

        # Clean up the temporary file
        os.unlink(temp_file.name)

        return f"File '{file_name}' successfully imported with title '{title}' and author '{author}'."
    except Exception as e:
        logging.error(f"Error importing file: {str(e)}")
        return f"Error importing file: {str(e)}"


def create_import_item_tab():
    with gr.TabItem("Import Markdown/Text Files"):
        gr.Markdown("# Import a markdown file or text file into the database")
        gr.Markdown("...and have it tagged + summarized")
        with gr.Row():
            with gr.Column():
                import_file = gr.File(label="Upload file for import", file_types=["txt", "md"])
                title_input = gr.Textbox(label="Title", placeholder="Enter the title of the content")
                author_input = gr.Textbox(label="Author", placeholder="Enter the author's name")
                keywords_input = gr.Textbox(label="Keywords", placeholder="Enter keywords, comma-separated")
                custom_prompt_input = gr.Textbox(label="Custom Prompt",
                                             placeholder="Enter a custom prompt for summarization (optional)")
                summary_input = gr.Textbox(label="Summary",
                                       placeholder="Enter a summary or leave blank for auto-summarization", lines=3)
                auto_summarize_checkbox = gr.Checkbox(label="Auto-summarize", value=False)
                api_name_input = gr.Dropdown(
                choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                         "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"],
                label="API for Auto-summarization"
                )
                api_key_input = gr.Textbox(label="API Key", type="password")
            with gr.Column():
                import_button = gr.Button("Import Data")
                import_output = gr.Textbox(label="Import Status")

        import_button.click(
            fn=import_data,
            inputs=[import_file, title_input, author_input, keywords_input, custom_prompt_input,
                    summary_input, auto_summarize_checkbox, api_name_input, api_key_input],
            outputs=import_output
        )

def create_import_obsidian_vault_tab():
    with gr.TabItem("Import Obsidian Vault"):
        gr.Markdown("## Import Obsidian Vault")
        with gr.Row():
            with gr.Column():
                vault_path_input = gr.Textbox(label="Obsidian Vault Path (Local)")
                vault_zip_input = gr.File(label="Upload Obsidian Vault (Zip)")
            with gr.Column():
                import_vault_button = gr.Button("Import Obsidian Vault")
                import_status = gr.Textbox(label="Import Status", interactive=False)


    def import_vault(vault_path, vault_zip):
        if vault_zip:
            imported, total, errors = process_obsidian_zip(vault_zip.name)
        elif vault_path:
            imported, total, errors = import_obsidian_vault(vault_path)
        else:
            return "Please provide either a local vault path or upload a zip file."

        status = f"Imported {imported} out of {total} files.\n"
        if errors:
            status += f"Encountered {len(errors)} errors:\n" + "\n".join(errors)
        return status


    import_vault_button.click(
        fn=import_vault,
        inputs=[vault_path_input, vault_zip_input],
        outputs=[import_status],
        show_progress=True
    )


def parse_prompt_file(file_content):
    sections = {
        'title': '',
        'author': '',
        'system': '',
        'user': '',
        'keywords': []
    }

    # Define regex patterns for the sections
    patterns = {
        'title': r'### TITLE ###\s*(.*?)\s*###',
        'author': r'### AUTHOR ###\s*(.*?)\s*###',
        'system': r'### SYSTEM ###\s*(.*?)\s*###',
        'user': r'### USER ###\s*(.*?)\s*###',
        'keywords': r'### KEYWORDS ###\s*(.*?)\s*###'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, file_content, re.DOTALL)
        if match:
            if key == 'keywords':
                # Split keywords by commas and strip whitespace
                sections[key] = [k.strip() for k in match.group(1).split(',') if k.strip()]
            else:
                sections[key] = match.group(1).strip()

    return sections


# FIXME - file uploads...fixed here, but rest of project... In fact make sure to check _all_ file uploads... will make it easier when centralizing everything for API
def import_prompt_from_file(file):
    if file is None:
        return "No file uploaded. Please upload a file."

    try:
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Get the original file name
            original_filename = file.name if hasattr(file, 'name') else 'unknown_file'

            # Create a path for the temporary file
            temp_file_path = os.path.join(temp_dir, original_filename)

            # Write the contents to the temporary file
            if isinstance(file, str):
                # If file is a string, it's likely a file path
                shutil.copy(file, temp_file_path)
            elif hasattr(file, 'read'):
                # If file has a 'read' method, it's likely a file-like object
                with open(temp_file_path, 'wb') as temp_file:
                    shutil.copyfileobj(file, temp_file)
            else:
                # If it's neither a string nor a file-like object, try converting it to a string
                with open(temp_file_path, 'w', encoding='utf-8') as temp_file:
                    temp_file.write(str(file))

            # Read and parse the content from the temporary file
            with open(temp_file_path, 'r', encoding='utf-8') as temp_file:
                file_content = temp_file.read()

            sections = parse_prompt_file(file_content)

        return sections['title'], sections['author'], sections['system'], sections['user'], sections['keywords']
    except Exception as e:
        return f"Error parsing file: {str(e)}"


def import_prompt_data(name, details, system, user):
    if not name or not system:
        return "Name and System fields are required."

    try:
        conn = sqlite3.connect('prompts.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Prompts (name, details, system, user)
            VALUES (?, ?, ?, ?)
        ''', (name, details, system, user))
        conn.commit()
        conn.close()
        return f"Prompt '{name}' successfully imported."
    except sqlite3.IntegrityError:
        return "Prompt with this name already exists."
    except sqlite3.Error as e:
        return f"Database error: {e}"


def create_import_single_prompt_tab():
    with gr.TabItem("Import a Prompt"):
        gr.Markdown("# Import a prompt into the database")

        with gr.Row():
            with gr.Column():
                import_file = gr.File(label="Upload file for import", file_types=["txt", "md"])
                title_input = gr.Textbox(label="Title", placeholder="Enter the title of the content")
                author_input = gr.Textbox(label="Author", placeholder="Enter the author's name")
                system_input = gr.Textbox(label="System", placeholder="Enter the system message for the prompt", lines=3)
                user_input = gr.Textbox(label="User", placeholder="Enter the user message for the prompt", lines=3)
                keywords_input = gr.Textbox(label="Keywords", placeholder="Enter keywords separated by commas")
                import_button = gr.Button("Import Prompt")

            with gr.Column():
                import_output = gr.Textbox(label="Import Status")
                save_button = gr.Button("Save to Database")
                save_output = gr.Textbox(label="Save Status")

        def handle_import(file):
            result = import_prompt_from_file(file)
            if isinstance(result, tuple) and len(result) == 5:
                title, author, system, user, keywords = result
                return gr.update(value="File successfully imported. You can now edit the content before saving."), \
                       gr.update(value=title), gr.update(value=author), gr.update(value=system), \
                       gr.update(value=user), gr.update(value=", ".join(keywords))
            else:
                return gr.update(value=result), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

        import_button.click(
            fn=handle_import,
            inputs=[import_file],
            outputs=[import_output, title_input, author_input, system_input, user_input, keywords_input]
        )

        def save_prompt_to_db(title, author, system, user, keywords):
            keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
            return insert_prompt_to_db(title, author, system, user, keyword_list)

        save_button.click(
            fn=save_prompt_to_db,
            inputs=[title_input, author_input, system_input, user_input, keywords_input],
            outputs=save_output
        )

        def update_prompt_dropdown():
            return gr.update(choices=load_preset_prompts())

        save_button.click(
            fn=update_prompt_dropdown,
            inputs=[],
            outputs=[gr.Dropdown(label="Select Preset Prompt")]
        )

def import_prompts_from_zip(zip_file):
    if zip_file is None:
        return "No file uploaded. Please upload a file."

    prompts = []
    temp_dir = tempfile.mkdtemp()
    try:
        zip_path = os.path.join(temp_dir, zip_file.name)
        with open(zip_path, 'wb') as f:
            f.write(zip_file.read())

        with zipfile.ZipFile(zip_path, 'r') as z:
            for filename in z.namelist():
                if filename.endswith('.txt') or filename.endswith('.md'):
                    with z.open(filename) as f:
                        file_content = f.read().decode('utf-8')
                        sections = parse_prompt_file(file_content)
                        if 'keywords' not in sections:
                            sections['keywords'] = []
                        prompts.append(sections)
        shutil.rmtree(temp_dir)
        return prompts
    except Exception as e:
        shutil.rmtree(temp_dir)
        return f"Error parsing zip file: {str(e)}"


def create_import_multiple_prompts_tab():
    with gr.TabItem("Import Multiple Prompts"):
        gr.Markdown("# Import multiple prompts into the database")
        gr.Markdown("Upload a zip file containing multiple prompt files (txt or md)")

        with gr.Row():
            with gr.Column():
                zip_file = gr.File(label="Upload zip file for import", file_types=["zip"])
                import_button = gr.Button("Import Prompts")
                prompts_dropdown = gr.Dropdown(label="Select Prompt to Edit", choices=[])
                title_input = gr.Textbox(label="Title", placeholder="Enter the title of the content")
                author_input = gr.Textbox(label="Author", placeholder="Enter the author's name")
                system_input = gr.Textbox(label="System", placeholder="Enter the system message for the prompt", lines=3)
                user_input = gr.Textbox(label="User", placeholder="Enter the user message for the prompt", lines=3)
                keywords_input = gr.Textbox(label="Keywords", placeholder="Enter keywords separated by commas")

            with gr.Column():
                import_output = gr.Textbox(label="Import Status")
                save_button = gr.Button("Save to Database")
                save_output = gr.Textbox(label="Save Status")
                prompts_display = gr.Textbox(label="Identified Prompts")

        def handle_zip_import(zip_file):
            result = import_prompts_from_zip(zip_file)
            if isinstance(result, list):
                prompt_titles = [prompt['title'] for prompt in result]
                return gr.update(value="Zip file successfully imported. Select a prompt to edit from the dropdown."), prompt_titles, gr.update(value="\n".join(prompt_titles)), result
            else:
                return gr.update(value=result), [], gr.update(value=""), []

        def handle_prompt_selection(selected_title, prompts):
            selected_prompt = next((prompt for prompt in prompts if prompt['title'] == selected_title), None)
            if selected_prompt:
                return (
                    selected_prompt['title'],
                    selected_prompt.get('author', ''),
                    selected_prompt['system'],
                    selected_prompt.get('user', ''),
                    ", ".join(selected_prompt.get('keywords', []))
                )
            else:
                return "", "", "", "", ""

        zip_import_state = gr.State([])

        import_button.click(
            fn=handle_zip_import,
            inputs=[zip_file],
            outputs=[import_output, prompts_dropdown, prompts_display, zip_import_state]
        )

        prompts_dropdown.change(
            fn=handle_prompt_selection,
            inputs=[prompts_dropdown, zip_import_state],
            outputs=[title_input, author_input, system_input, user_input, keywords_input]
        )

        def save_prompt_to_db(title, author, system, user, keywords):
            keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
            return insert_prompt_to_db(title, author, system, user, keyword_list)

        save_button.click(
            fn=save_prompt_to_db,
            inputs=[title_input, author_input, system_input, user_input, keywords_input],
            outputs=save_output
        )

        def update_prompt_dropdown():
            return gr.update(choices=load_preset_prompts())

        save_button.click(
            fn=update_prompt_dropdown,
            inputs=[],
            outputs=[gr.Dropdown(label="Select Preset Prompt")]
        )



# Using pypandoc to convert EPUB to Markdown
def create_import_book_tab():
    with gr.TabItem("Import .epub/ebook Files"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("# Ingest an .epub file using pypandoc")
                gr.Markdown("...and have it tagged + summarized")
                gr.Markdown(
                "How to remove DRM from your ebooks: https://www.reddit.com/r/Calibre/comments/1ck4w8e/2024_guide_on_removing_drm_from_kobo_kindle_ebooks/")
                import_file = gr.File(label="Upload file for import", file_types=[".epub"])
                title_input = gr.Textbox(label="Title", placeholder="Enter the title of the content")
                author_input = gr.Textbox(label="Author", placeholder="Enter the author's name")
                keywords_input = gr.Textbox(label="Keywords(like genre or publish year)",
                                            placeholder="Enter keywords, comma-separated")
                system_prompt_input = gr.Textbox(label="System Prompt",
                                                 lines=3,
                                                 value=""""
                                                    <s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
                                                    **Bulleted Note Creation Guidelines**
                                                    
                                                    **Headings**:
                                                    - Based on referenced topics, not categories like quotes or terms
                                                    - Surrounded by **bold** formatting 
                                                    - Not listed as bullet points
                                                    - No space between headings and list items underneath
                                                    
                                                    **Emphasis**:
                                                    - **Important terms** set in bold font
                                                    - **Text ending in a colon**: also bolded
                                                    
                                                    **Review**:
                                                    - Ensure adherence to specified format
                                                    - Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]
                                                """,)
                custom_prompt_input = gr.Textbox(label="Custom User Prompt",
                                                 placeholder="Enter a custom user prompt for summarization (optional)")
                auto_summarize_checkbox = gr.Checkbox(label="Auto-summarize", value=False)
                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"],
                    label="API for Auto-summarization"
                )
                api_key_input = gr.Textbox(label="API Key", type="password")
                import_button = gr.Button("Import eBook")
            with gr.Column():
                with gr.Row():
                    import_output = gr.Textbox(label="Import Status")

        def import_epub(epub_file, title, author, keywords, system_prompt, user_prompt, auto_summarize, api_name, api_key):
            try:
                # Create a temporary directory to store the converted file
                with tempfile.TemporaryDirectory() as temp_dir:
                    epub_path = epub_file.name
                    md_path = os.path.join(temp_dir, "converted.md")

                    # Use pypandoc to convert EPUB to Markdown
                    output = pypandoc.convert_file(epub_path, 'md', outputfile=md_path)

                    if output != "":
                        return f"Error converting EPUB: {output}"

                    # Read the converted markdown content
                    with open(md_path, "r", encoding="utf-8") as md_file:
                        content = md_file.read()

                    # Now process the content as you would with a text file
                    return import_data(content, title, author, keywords, system_prompt,
                                       user_prompt, auto_summarize, api_name, api_key)
            except Exception as e:
                return f"Error processing EPUB: {str(e)}"

        import_button.click(
            fn=import_epub,
            inputs=[import_file, title_input, author_input, keywords_input, system_prompt_input,
                    custom_prompt_input, auto_summarize_checkbox, api_name_input, api_key_input],
            outputs=import_output
        )


#
# End of Import Items Tab Functions
################################################################################################################
#
# Export Items Tab Functions
logger = logging.getLogger(__name__)

def export_item_as_markdown(media_id: int) -> Tuple[Optional[str], str]:
    try:
        content, prompt, summary = fetch_item_details(media_id)
        title = f"Item {media_id}"  # You might want to fetch the actual title
        markdown_content = f"# {title}\n\n## Prompt\n{prompt}\n\n## Summary\n{summary}\n\n## Content\n{content}"

        filename = f"export_item_{media_id}.md"
        with open(filename, "w", encoding='utf-8') as f:
            f.write(markdown_content)

        logger.info(f"Successfully exported item {media_id} to {filename}")
        return filename, f"Successfully exported item {media_id} to {filename}"
    except Exception as e:
        error_message = f"Error exporting item {media_id}: {str(e)}"
        logger.error(error_message)
        return None, error_message


def export_items_by_keyword(keyword: str) -> str:
    try:
        items = fetch_items_by_keyword(keyword)
        if not items:
            logger.warning(f"No items found for keyword: {keyword}")
            return None

        # Create a temporary directory to store individual markdown files
        with tempfile.TemporaryDirectory() as temp_dir:
            folder_name = f"export_keyword_{keyword}"
            export_folder = os.path.join(temp_dir, folder_name)
            os.makedirs(export_folder)

            for item in items:
                content, prompt, summary = fetch_item_details(item['id'])
                markdown_content = f"# {item['title']}\n\n## Prompt\n{prompt}\n\n## Summary\n{summary}\n\n## Content\n{content}"

                # Create individual markdown file for each item
                file_name = f"{item['id']}_{item['title'][:50]}.md"  # Limit filename length
                file_path = os.path.join(export_folder, file_name)
                with open(file_path, "w", encoding='utf-8') as f:
                    f.write(markdown_content)

            # Create a zip file containing all markdown files
            zip_filename = f"{folder_name}.zip"
            shutil.make_archive(os.path.join(temp_dir, folder_name), 'zip', export_folder)

            # Move the zip file to a location accessible by Gradio
            final_zip_path = os.path.join(os.getcwd(), zip_filename)
            shutil.move(os.path.join(temp_dir, zip_filename), final_zip_path)

        logger.info(f"Successfully exported {len(items)} items for keyword '{keyword}' to {zip_filename}")
        return final_zip_path
    except Exception as e:
        logger.error(f"Error exporting items for keyword '{keyword}': {str(e)}")
        return None


def export_selected_items(selected_items: List[Dict]) -> Tuple[Optional[str], str]:
    try:
        logger.debug(f"Received selected_items: {selected_items}")
        if not selected_items:
            logger.warning("No items selected for export")
            return None, "No items selected for export"

        markdown_content = "# Selected Items\n\n"
        for item in selected_items:
            logger.debug(f"Processing item: {item}")
            try:
                # Check if 'value' is a string (JSON) or already a dictionary
                if isinstance(item, str):
                    item_data = json.loads(item)
                elif isinstance(item, dict) and 'value' in item:
                    item_data = item['value'] if isinstance(item['value'], dict) else json.loads(item['value'])
                else:
                    item_data = item

                logger.debug(f"Item data after processing: {item_data}")

                if 'id' not in item_data:
                    logger.error(f"'id' not found in item data: {item_data}")
                    continue

                content, prompt, summary = fetch_item_details(item_data['id'])
                markdown_content += f"## {item_data.get('title', 'Item {}'.format(item_data['id']))}\n\n### Prompt\n{prompt}\n\n### Summary\n{summary}\n\n### Content\n{content}\n\n---\n\n"
            except Exception as e:
                logger.error(f"Error processing item {item}: {str(e)}")
                markdown_content += f"## Error\n\nUnable to process this item.\n\n---\n\n"

        filename = "export_selected_items.md"
        with open(filename, "w", encoding='utf-8') as f:
            f.write(markdown_content)

        logger.info(f"Successfully exported {len(selected_items)} selected items to {filename}")
        return filename, f"Successfully exported {len(selected_items)} items to {filename}"
    except Exception as e:
        error_message = f"Error exporting selected items: {str(e)}"
        logger.error(error_message)
        return None, error_message


def display_search_results_export_tab(search_query: str, search_type: str, page: int = 1, items_per_page: int = 10):
    logger.info(f"Searching with query: '{search_query}', type: '{search_type}', page: {page}")
    try:
        results = browse_items(search_query, search_type)
        logger.info(f"browse_items returned {len(results)} results")

        if not results:
            return [], f"No results found for query: '{search_query}'", 1, 1

        total_pages = math.ceil(len(results) / items_per_page)
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        paginated_results = results[start_index:end_index]

        checkbox_data = [
            {
                "name": f"Name: {item[1]}\nURL: {item[2]}",
                "value": {"id": item[0], "title": item[1], "url": item[2]}
            }
            for item in paginated_results
        ]

        logger.info(f"Returning {len(checkbox_data)} items for checkbox (page {page} of {total_pages})")
        return checkbox_data, f"Found {len(results)} results (showing page {page} of {total_pages})", page, total_pages

    except DatabaseError as e:
        error_message = f"Error in display_search_results_export_tab: {str(e)}"
        logger.error(error_message)
        return [], error_message, 1, 1
    except Exception as e:
        error_message = f"Unexpected error in display_search_results_export_tab: {str(e)}"
        logger.error(error_message)
        return [], error_message, 1, 1


def create_export_tab():
    with gr.Tab("Search and Export"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("# Search and Export Items")
                gr.Markdown("Search for items and export them as markdown files")
                gr.Markdown("You can also export items by keyword")
                search_query = gr.Textbox(label="Search Query")
                search_type = gr.Radio(["Title", "URL", "Keyword", "Content"], label="Search By")
                search_button = gr.Button("Search")

            with gr.Column():
                prev_button = gr.Button("Previous Page")
                next_button = gr.Button("Next Page")

        current_page = gr.State(1)
        total_pages = gr.State(1)

        search_results = gr.CheckboxGroup(label="Search Results", choices=[])
        export_selected_button = gr.Button("Export Selected Items")

        keyword_input = gr.Textbox(label="Enter keyword for export")
        export_by_keyword_button = gr.Button("Export items by keyword")

        export_output = gr.File(label="Download Exported File")
        error_output = gr.Textbox(label="Status/Error Messages", interactive=False)

    def search_and_update(query, search_type, page):
        results, message, current, total = display_search_results_export_tab(query, search_type, page)
        logger.debug(f"search_and_update results: {results}")
        return results, message, current, total, gr.update(choices=results)

    search_button.click(
        fn=search_and_update,
        inputs=[search_query, search_type, current_page],
        outputs=[search_results, error_output, current_page, total_pages, search_results],
        show_progress="full"
    )


    def update_page(current, total, direction):
        new_page = max(1, min(total, current + direction))
        return new_page

    prev_button.click(
        fn=update_page,
        inputs=[current_page, total_pages, gr.State(-1)],
        outputs=[current_page]
    ).then(
        fn=search_and_update,
        inputs=[search_query, search_type, current_page],
        outputs=[search_results, error_output, current_page, total_pages],
        show_progress=True
    )

    next_button.click(
        fn=update_page,
        inputs=[current_page, total_pages, gr.State(1)],
        outputs=[current_page]
    ).then(
        fn=search_and_update,
        inputs=[search_query, search_type, current_page],
        outputs=[search_results, error_output, current_page, total_pages],
        show_progress=True
    )

    def handle_export_selected(selected_items):
        logger.debug(f"Exporting selected items: {selected_items}")
        return export_selected_items(selected_items)

    export_selected_button.click(
        fn=handle_export_selected,
        inputs=[search_results],
        outputs=[export_output, error_output],
        show_progress="full"
    )

    export_by_keyword_button.click(
        fn=export_items_by_keyword,
        inputs=[keyword_input],
        outputs=[export_output, error_output],
        show_progress="full"
    )

    def handle_item_selection(selected_items):
        logger.debug(f"Selected items: {selected_items}")
        if not selected_items:
            return None, "No item selected"

        try:
            # Assuming selected_items is a list of dictionaries
            selected_item = selected_items[0]
            logger.debug(f"First selected item: {selected_item}")

            # Check if 'value' is a string (JSON) or already a dictionary
            if isinstance(selected_item['value'], str):
                item_data = json.loads(selected_item['value'])
            else:
                item_data = selected_item['value']

            logger.debug(f"Item data: {item_data}")

            item_id = item_data['id']
            return export_item_as_markdown(item_id)
        except Exception as e:
            error_message = f"Error processing selected item: {str(e)}"
            logger.error(error_message)
            return None, error_message

    search_results.select(
        fn=handle_item_selection,
        inputs=[search_results],
        outputs=[export_output, error_output],
        show_progress="full"
    )



def create_backup():
    backup_file = create_automated_backup(db_path, backup_dir)
    return f"Backup created: {backup_file}"

def list_backups():
    backups = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
    return "\n".join(backups)

def restore_backup(backup_name):
    backup_path = os.path.join(backup_dir, backup_name)
    if os.path.exists(backup_path):
        shutil.copy2(backup_path, db_path)
        return f"Database restored from {backup_name}"
    else:
        return "Backup file not found"


def create_backup_tab():
    with gr.Tab("Create Backup"):
        gr.Markdown("# Create a backup of the database")
        with gr.Row():
            with gr.Column():
                create_button = gr.Button("Create Backup")
                create_output = gr.Textbox(label="Result")
            with gr.Column():
                create_button.click(create_backup, inputs=[], outputs=create_output)

def create_view_backups_tab():
    with gr.TabItem("View Backups"):
        gr.Markdown("# Browse available backups")
        with gr.Row():
            with gr.Column():
                view_button = gr.Button("View Backups")
            with gr.Column():
                backup_list = gr.Textbox(label="Available Backups")
                view_button.click(list_backups, inputs=[], outputs=backup_list)


def create_restore_backup_tab():
    with gr.TabItem("Restore Backup"):
        gr.Markdown("# Restore a backup of the database")
        with gr.Column():
            backup_input = gr.Textbox(label="Backup Filename")
            restore_button = gr.Button("Restore")
        with gr.Column():
            restore_output = gr.Textbox(label="Result")
            restore_button.click(restore_backup, inputs=[backup_input], outputs=restore_output)


#
# End of Export Items Tab Functions
################################################################################################################
#
# Keyword Management Tab Functions

def create_export_keywords_tab():
    with gr.Tab("Export Keywords"):
        with gr.Row():
            with gr.Column():
                export_keywords_button = gr.Button("Export Keywords")
            with gr.Column():
                export_keywords_output = gr.File(label="Download Exported Keywords")
                export_keywords_status = gr.Textbox(label="Export Status")

            export_keywords_button.click(
                fn=export_keywords_to_csv,
                outputs=[export_keywords_status, export_keywords_output]
            )

def create_view_keywords_tab():
    with gr.TabItem("View Keywords"):
        gr.Markdown("# Browse Keywords")
        with gr.Column():
            browse_output = gr.Markdown()
            browse_button = gr.Button("View Existing Keywords")
            browse_button.click(fn=keywords_browser_interface, outputs=browse_output)


def create_add_keyword_tab():
    with gr.TabItem("Add Keywords"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("# Add Keywords to the Database")
                add_input = gr.Textbox(label="Add Keywords (comma-separated)", placeholder="Enter keywords here...")
                add_button = gr.Button("Add Keywords")
            with gr.Row():
                add_output = gr.Textbox(label="Result")
                add_button.click(fn=add_keyword, inputs=add_input, outputs=add_output)


def create_delete_keyword_tab():
    with gr.Tab("Delete Keywords"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("# Delete Keywords from the Database")
                delete_input = gr.Textbox(label="Delete Keyword", placeholder="Enter keyword to delete here...")
                delete_button = gr.Button("Delete Keyword")
            with gr.Row():
                delete_output = gr.Textbox(label="Result")
                delete_button.click(fn=delete_keyword, inputs=delete_input, outputs=delete_output)

#
# End of Keyword Management Tab Functions
################################################################################################################
#
# Document Editing Tab Functions


def adjust_tone(text, concise, casual, api_name, api_key):
    tones = [
        {"tone": "concise", "weight": concise},
        {"tone": "casual", "weight": casual},
        {"tone": "professional", "weight": 1 - casual},
        {"tone": "expanded", "weight": 1 - concise}
    ]
    tones = sorted(tones, key=lambda x: x['weight'], reverse=True)[:2]

    tone_prompt = " and ".join([f"{t['tone']} (weight: {t['weight']:.2f})" for t in tones])

    prompt = f"Rewrite the following text to match these tones: {tone_prompt}. Text: {text}"
    # Performing tone adjustment request...
    adjusted_text = perform_summarization(api_name, text, prompt, api_key)

    return adjusted_text


def grammar_style_check(input_text, custom_prompt, api_name, api_key, system_prompt):
    default_prompt = "Please analyze the following text for grammar and style. Offer suggestions for improvement and point out any misused words or incorrect spellings:\n\n"
    full_prompt = custom_prompt if custom_prompt else default_prompt
    full_text = full_prompt + input_text

    return perform_summarization(api_name, full_text, custom_prompt, api_key, system_prompt)


def create_grammar_style_check_tab():
    with gr.TabItem("Grammar and Style Check"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("# Grammar and Style Check")
                gr.Markdown("This utility checks the grammar and style of the provided text by feeding it to an LLM and returning suggestions for improvement.")
                input_text = gr.Textbox(label="Input Text", lines=10)
                custom_prompt_checkbox = gr.Checkbox(label="Use Custom Prompt", value=False, visible=True)
                system_prompt_input = gr.Textbox(label="System Prompt", placeholder="Please analyze the provided text for grammar and style. Offer any suggestions or points to improve you can identify. Additionally please point out any misuses of any words or incorrect spellings.", lines=5, visible=False)
                custom_prompt_input = gr.Textbox(label="user Prompt",
                                                     value="""<s>You are a bulleted notes specialist. [INST]```When creating comprehensive bulleted notes, you should follow these guidelines: Use multiple headings based on the referenced topics, not categories like quotes or terms. Headings should be surrounded by bold formatting and not be listed as bullet points themselves. Leave no space between headings and their corresponding list items underneath. Important terms within the content should be emphasized by setting them in bold font. Any text that ends with a colon should also be bolded. Before submitting your response, review the instructions, and make any corrections necessary to adhered to the specified format. Do not reference these instructions within the notes.``` \nBased on the content between backticks create comprehensive bulleted notes.[/INST]
**Bulleted Note Creation Guidelines**

**Headings**:
- Based on referenced topics, not categories like quotes or terms
- Surrounded by **bold** formatting 
- Not listed as bullet points
- No space between headings and list items underneath

**Emphasis**:
- **Important terms** set in bold font
- **Text ending in a colon**: also bolded

**Review**:
- Ensure adherence to specified format
- Do not reference these instructions in your response.</s>[INST] {{ .Prompt }} [/INST]
""",
                                                     lines=3,
                                                     visible=False)
                custom_prompt_checkbox.change(
                    fn=lambda x: (gr.update(visible=x), gr.update(visible=x)),
                    inputs=[custom_prompt_checkbox],
                    outputs=[custom_prompt_input, system_prompt_input]
                )
                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"],
                    value=None,
                    label="API for Grammar Check"
                )
                api_key_input = gr.Textbox(label="API Key (if not set in config.txt)", placeholder="Enter your API key here",
                                               type="password")
                check_grammar_button = gr.Button("Check Grammar and Style")

            with gr.Column():
                gr.Markdown("# Resulting Suggestions")
                gr.Markdown("(Keep in mind the API used can affect the quality of the suggestions)")

                output_text = gr.Textbox(label="Grammar and Style Suggestions", lines=15)

            check_grammar_button.click(
                fn=grammar_style_check,
                inputs=[input_text, custom_prompt_input, api_name_input, api_key_input, system_prompt_input],
                outputs=output_text
            )


def create_tone_adjustment_tab():
    with gr.TabItem("Tone Analyzer & Editor"):
        with gr.Row():
            with gr.Column():
                input_text = gr.Textbox(label="Input Text", lines=10)
                concise_slider = gr.Slider(minimum=0, maximum=1, value=0.5, label="Concise vs Expanded")
                casual_slider = gr.Slider(minimum=0, maximum=1, value=0.5, label="Casual vs Professional")
                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM","ollama", "HuggingFace"],
                    value=None,
                    label="API for Grammar Check"
                )
                api_key_input = gr.Textbox(label="API Key (if not set in config.txt)", placeholder="Enter your API key here",
                                               type="password")
                adjust_btn = gr.Button("Adjust Tone")

            with gr.Column():
                output_text = gr.Textbox(label="Adjusted Text", lines=15)

                adjust_btn.click(
                    adjust_tone,
                    inputs=[input_text, concise_slider, casual_slider],
                    outputs=output_text
                )


persona_prompts = {
    "Hemingway": "As Ernest Hemingway, known for concise and straightforward prose, provide feedback on the following text:",
    "Shakespeare": "Channel William Shakespeare's poetic style and provide feedback on the following text:",
    "Jane Austen": "Embodying Jane Austen's wit and social commentary, critique the following text:",
    "Stephen King": "With Stephen King's flair for suspense and horror, analyze the following text:",
    "J.K. Rowling": "As J.K. Rowling, creator of the magical world of Harry Potter, review the following text:"
}

def generate_writing_feedback(text, persona, aspect, api_name, api_key):
    if isinstance(persona, dict):  # If it's a character card
        base_prompt = f"You are {persona['name']}. {persona['personality']}\n\nScenario: {persona['scenario']}\n\nRespond to the following message in character:"
    else:  # If it's a regular persona
        base_prompt = persona_prompts.get(persona, f"As {persona}, provide feedback on the following text:")

    if aspect != "Overall":
        prompt = f"{base_prompt}\n\nFocus specifically on the {aspect.lower()} in the following text:\n\n{text}"
    else:
        prompt = f"{base_prompt}\n\n{text}"

    return perform_summarization(api_name, text, prompt, api_key, system_message="You are a helpful AI assistant. You will respond to the user as if you were the persona declared in the user prompt.")

def generate_writing_prompt(persona, api_name, api_key):
    prompt = f"Generate a writing prompt in the style of {persona}. The prompt should inspire a short story or scene that reflects {persona}'s typical themes and writing style."
    #FIXME
    return perform_summarization(api_name, prompt, "", api_key, system_message="You are a helpful AI assistant. You will respond to the user as if you were the persona declared in the user prompt." )

def calculate_readability(text):
    ease = textstat.flesch_reading_ease(text)
    grade = textstat.flesch_kincaid_grade(text)
    return f"Readability: Flesch Reading Ease: {ease:.2f}, Flesch-Kincaid Grade Level: {grade:.2f}"


def generate_feedback_history_html(history):
    html = "<h3>Recent Feedback History</h3>"
    for entry in reversed(history):
        html += f"<details><summary>{entry['persona']} Feedback</summary>"
        html += f"<p><strong>Original Text:</strong> {entry['text'][:100]}...</p>"

        feedback = entry.get('feedback')
        if feedback:
            html += f"<p><strong>Feedback:</strong> {feedback[:200]}...</p>"
        else:
            html += "<p><strong>Feedback:</strong> No feedback provided.</p>"

        html += "</details>"
    return html


# FIXME
def create_document_feedback_tab():
    with gr.TabItem("Writing Feedback"):
        with gr.Row():
            with gr.Column(scale=2):
                input_text = gr.Textbox(label="Your Writing", lines=10)
                persona_dropdown = gr.Dropdown(
                    label="Select Persona",
                    choices=[
                        "Agatha Christie",
                        "Arthur Conan Doyle",
                        "Charles Bukowski",
                        "Charles Dickens",
                        "Chinua Achebe",
                        "Cormac McCarthy",
                        "David Foster Wallace",
                        "Edgar Allan Poe",
                        "F. Scott Fitzgerald",
                        "Flannery O'Connor",
                        "Franz Kafka",
                        "Fyodor Dostoevsky",
                        "Gabriel Garcia Marquez",
                        "George R.R. Martin",
                        "George Orwell",
                        "Haruki Murakami",
                        "Hemingway",
                        "Herman Melville",
                        "Isabel Allende",
                        "James Joyce",
                        "Jane Austen",
                        "J.K. Rowling",
                        "J.R.R. Tolkien",
                        "Jorge Luis Borges",
                        "Kurt Vonnegut",
                        "Leo Tolstoy",
                        "Margaret Atwood",
                        "Mark Twain",
                        "Mary Shelley",
                        "Milan Kundera",
                        "Naguib Mahfouz",
                        "Neil Gaiman",
                        "Octavia Butler",
                        "Philip K Dick",
                        "Ray Bradbury",
                        "Salman Rushdie",
                        "Shakespeare",
                        "Stephen King",
                        "Toni Morrison",
                        "T.S. Eliot",
                        "Ursula K. Le Guin",
                        "Virginia Woolf",
                        "Virginia Woolf",
                        "Zadie Smith"],
                    value="Hemingway"
                )
                custom_persona_name = gr.Textbox(label="Custom Persona Name")
                custom_persona_description = gr.Textbox(label="Custom Persona Description", lines=3)
                add_custom_persona_button = gr.Button("Add Custom Persona")
                aspect_dropdown = gr.Dropdown(
                    label="Focus Feedback On",
                    choices=["Overall", "Grammar", "Word choice", "Structure of delivery", "Character Development", "Character Dialogue", "Descriptive Language", "Plot Structure"],
                    value="Overall"
                )
                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "ollama", "HuggingFace"],
                    value=None,
                    label="API for Feedback"
                )
                api_key_input = gr.Textbox(label="API Key (if not set in config.txt)", type="password")
                get_feedback_button = gr.Button("Get Feedback")
                generate_prompt_button = gr.Button("Generate Writing Prompt")

            with gr.Column(scale=2):
                feedback_output = gr.Textbox(label="Feedback", lines=15)
                readability_output = gr.Textbox(label="Readability Metrics")
                feedback_history_display = gr.HTML(label="Feedback History")

        with gr.Row():
            compare_personas = gr.CheckboxGroup(
                choices=[
                    "Agatha Christie",
                    "Arthur Conan Doyle",
                    "Charles Bukowski",
                    "Charles Dickens",
                    "Chinua Achebe",
                    "Cormac McCarthy",
                    "David Foster Wallace",
                    "Edgar Allan Poe",
                    "F. Scott Fitzgerald",
                    "Flannery O'Connor",
                    "Franz Kafka",
                    "Fyodor Dostoevsky",
                    "Gabriel Garcia Marquez",
                    "George R.R. Martin",
                    "George Orwell",
                    "Haruki Murakami",
                    "Hemingway",
                    "Herman Melville",
                    "Isabel Allende",
                    "James Joyce",
                    "Jane Austen",
                    "J.K. Rowling",
                    "J.R.R. Tolkien",
                    "Jorge Luis Borges",
                    "Kurt Vonnegut",
                    "Leo Tolstoy",
                    "Margaret Atwood",
                    "Mark Twain",
                    "Mary Shelley",
                    "Milan Kundera",
                    "Naguib Mahfouz",
                    "Neil Gaiman",
                    "Octavia Butler",
                    "Philip K Dick",
                    "Ray Bradbury",
                    "Salman Rushdie",
                    "Shakespeare",
                    "Stephen King",
                    "Toni Morrison",
                    "T.S. Eliot",
                    "Ursula K. Le Guin",
                    "Virginia Woolf",
                    "Virginia Woolf",
                    "Zadie Smith"],
                label="Compare Multiple Persona's Feedback at Once"
            )
        with gr.Row():
            compare_button = gr.Button("Compare Feedback")

    feedback_history = gr.State([])

    def add_custom_persona(name, description):
        updated_choices = persona_dropdown.choices + [name]
        persona_prompts[name] = f"As {name}, {description}, provide feedback on the following text:"
        return gr.update(choices=updated_choices)

    def update_feedback_history(current_text, persona, feedback):
        # Ensure feedback_history.value is initialized and is a list
        if feedback_history.value is None:
            feedback_history.value = []

        history = feedback_history.value

        # Append the new entry to the history
        history.append({"text": current_text, "persona": persona, "feedback": feedback})

        # Keep only the last 5 entries in the history
        feedback_history.value = history[-10:]

        # Generate and return the updated HTML
        return generate_feedback_history_html(feedback_history.value)

    def compare_feedback(text, selected_personas, api_name, api_key):
        results = []
        for persona in selected_personas:
            feedback = generate_writing_feedback(text, persona, "Overall", api_name, api_key)
            results.append(f"### {persona}'s Feedback:\n{feedback}\n\n")
        return "\n".join(results)

    add_custom_persona_button.click(
        fn=add_custom_persona,
        inputs=[custom_persona_name, custom_persona_description],
        outputs=persona_dropdown
    )

    get_feedback_button.click(
        fn=lambda text, persona, aspect, api_name, api_key: (
            generate_writing_feedback(text, persona, aspect, api_name, api_key),
            calculate_readability(text),
            update_feedback_history(text, persona, generate_writing_feedback(text, persona, aspect, api_name, api_key))
        ),
        inputs=[input_text, persona_dropdown, aspect_dropdown, api_name_input, api_key_input],
        outputs=[feedback_output, readability_output, feedback_history_display]
    )

    compare_button.click(
        fn=compare_feedback,
        inputs=[input_text, compare_personas, api_name_input, api_key_input],
        outputs=feedback_output
    )

    generate_prompt_button.click(
        fn=generate_writing_prompt,
        inputs=[persona_dropdown, api_name_input, api_key_input],
        outputs=input_text
    )

    return input_text, feedback_output, readability_output, feedback_history_display


def create_creative_writing_tab():
    with gr.TabItem("Creative Writing Assistant"):
        gr.Markdown("# Utility to be added...")


#FIXME - change to use chat function
def chat_with_character(user_message, history, char_data, api_name_input, api_key):
    if char_data is None:
        return history, "Please import a character card first."

    bot_message = generate_writing_feedback(user_message, char_data['name'], "Overall", api_name_input,
                                            api_key)
    history.append((user_message, bot_message))
    return history, ""

def import_character_card(file):
    if file is None:
        logging.warning("No file provided for character card import")
        return None
    try:
        if file.name.lower().endswith(('.png', '.webp')):
            logging.info(f"Attempting to import character card from image: {file.name}")
            json_data = extract_json_from_image(file)
            if json_data:
                logging.info("JSON data extracted from image, attempting to parse")
                return import_character_card_json(json_data)
            else:
                logging.warning("No JSON data found in the image")
        else:
            logging.info(f"Attempting to import character card from JSON file: {file.name}")
            content = file.read().decode('utf-8')
            return import_character_card_json(content)
    except Exception as e:
        logging.error(f"Error importing character card: {e}")
    return None


def import_character_card_json(json_content):
    try:
        # Remove any leading/trailing whitespace
        json_content = json_content.strip()

        # Log the first 100 characters of the content
        logging.debug(f"JSON content (first 100 chars): {json_content[:100]}...")

        card_data = json.loads(json_content)
        logging.debug(f"Parsed JSON data keys: {list(card_data.keys())}")
        if 'spec' in card_data and card_data['spec'] == 'chara_card_v2':
            logging.info("Detected V2 character card")
            return card_data['data']
        else:
            logging.info("Assuming V1 character card")
            return card_data
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        logging.error(f"Problematic JSON content: {json_content[:500]}...")
    except Exception as e:
        logging.error(f"Unexpected error parsing JSON: {e}")
    return None


def extract_json_from_image(image_file):
    logging.debug(f"Attempting to extract JSON from image: {image_file.name}")
    try:
        with Image.open(image_file) as img:
            logging.debug("Image opened successfully")
            metadata = img.info
            if 'chara' in metadata:
                logging.debug("Found 'chara' in image metadata")
                chara_content = metadata['chara']
                logging.debug(f"Content of 'chara' metadata (first 100 chars): {chara_content[:100]}...")
                try:
                    decoded_content = base64.b64decode(chara_content).decode('utf-8')
                    logging.debug(f"Decoded content (first 100 chars): {decoded_content[:100]}...")
                    return decoded_content
                except Exception as e:
                    logging.error(f"Error decoding base64 content: {e}")

            logging.debug("'chara' not found in metadata, checking for base64 encoded data")
            raw_data = img.tobytes()
            possible_json = raw_data.split(b'{', 1)[-1].rsplit(b'}', 1)[0]
            if possible_json:
                try:
                    decoded = base64.b64decode(possible_json).decode('utf-8')
                    if decoded.startswith('{') and decoded.endswith('}'):
                        logging.debug("Found and decoded base64 JSON data")
                        return '{' + decoded + '}'
                except Exception as e:
                    logging.error(f"Error decoding base64 data: {e}")

            logging.warning("No JSON data found in the image")
    except Exception as e:
        logging.error(f"Error extracting JSON from image: {e}")
    return None

def load_chat_history(file):
    try:
        content = file.read().decode('utf-8')
        chat_data = json.loads(content)
        return chat_data['history'], chat_data['character']
    except Exception as e:
        logging.error(f"Error loading chat history: {e}")
        return None, None

def create_character_card_interaction_tab():
    with gr.TabItem("Chat with a Character Card"):
        gr.Markdown("# Chat with a Character Card")
        with gr.Row():
            with gr.Column(scale=1):
                character_card_upload = gr.File(label="Upload Character Card")
                import_card_button = gr.Button("Import Character Card")
                load_characters_button = gr.Button("Load Existing Characters")
                character_dropdown = gr.Dropdown(label="Select Character", choices=get_character_names())
                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "Mistral",
                             "OpenRouter", "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "ollama", "HuggingFace"],
                    value=None,
                    label="API for Interaction"
                )
                api_key_input = gr.Textbox(label="API Key (if not set in config.txt)",
                                           placeholder="Enter your API key here", type="password")
                temperature_slider = gr.Slider(minimum=0.0, maximum=2.0, value=0.7, step=0.05, label="Temperature")
                import_chat_button = gr.Button("Import Chat History")
                chat_file_upload = gr.File(label="Upload Chat History JSON", visible=False)


            with gr.Column(scale=2):
                chat_history = gr.Chatbot(label="Conversation")
                user_input = gr.Textbox(label="Your message")
                send_message_button = gr.Button("Send Message")
                regenerate_button = gr.Button("Regenerate Last Message")
                save_chat_button = gr.Button("Save This Chat")
                save_status = gr.Textbox(label="Save Status", interactive=False)

    character_data = gr.State(None)

    def import_chat_history(file, current_history, char_data):
        loaded_history, char_name = load_chat_history(file)
        if loaded_history is None:
            return current_history, char_data, "Failed to load chat history."

        # Check if the loaded chat is for the current character
        if char_data and char_data.get('name') != char_name:
            return current_history, char_data, f"Warning: Loaded chat is for character '{char_name}', but current character is '{char_data.get('name')}'. Chat not imported."

        # If no character is selected, try to load the character from the chat
        if not char_data:
            new_char_data = load_character(char_name)[0]
            if new_char_data:
                char_data = new_char_data
            else:
                return current_history, char_data, f"Warning: Character '{char_name}' not found. Please select the character manually."

        return loaded_history, char_data, f"Chat history for '{char_name}' imported successfully."

    def import_character(file):
        card_data = import_character_card(file)
        if card_data:
            save_character(card_data)
            return card_data, gr.update(choices=get_character_names())
        else:
            return None, gr.update()

    def load_character(name):
        characters = load_characters()
        char_data = characters.get(name)
        if char_data:
            first_message = char_data.get('first_mes', "Hello! I'm ready to chat.")
            return char_data, [(None, first_message)] if first_message else []
        return None, []

    def character_chat_wrapper(message, history, char_data, api_endpoint, api_key, temperature):
        logging.debug("Entered character_chat_wrapper")
        if char_data is None:
            return "Please select a character first.", history

        # Prepare the character's background information
        char_background = f"""
        Name: {char_data.get('name', 'Unknown')}
        Description: {char_data.get('description', 'N/A')}
        Personality: {char_data.get('personality', 'N/A')}
        Scenario: {char_data.get('scenario', 'N/A')}
        """

        # Prepare the system prompt for character impersonation
        system_message = f"""You are roleplaying as the character described below. Respond to the user's messages in character, maintaining the personality and background provided. Do not break character or refer to yourself as an AI.

        {char_background}

        Additional instructions: {char_data.get('post_history_instructions', '')}
        """

        # Prepare media_content and selected_parts
        media_content = {
            'id': char_data.get('name'),
            'title': char_data.get('name', 'Unknown Character'),
            'content': char_background,
            'description': char_data.get('description', ''),
            'personality': char_data.get('personality', ''),
            'scenario': char_data.get('scenario', '')
        }
        selected_parts = ['description', 'personality', 'scenario']

        prompt = char_data.get('post_history_instructions', '')

        # Prepare the input for the chat function
        if not history:
            full_message = f"{prompt}\n\n{message}" if prompt else message
        else:
            full_message = message

        # Call the chat function
        bot_message = chat(
            message,
            history,
            media_content,
            selected_parts,
            api_endpoint,
            api_key,
            prompt,
            temperature,
            system_message
        )

        # Update history
        history.append((message, bot_message))
        return history

    def save_chat_history(history, character_name):
        # Create the Saved_Chats folder if it doesn't exist
        save_directory = "Saved_Chats"
        os.makedirs(save_directory, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_history_{character_name}_{timestamp}.json"
        filepath = os.path.join(save_directory, filename)

        chat_data = {
            "character": character_name,
            "timestamp": timestamp,
            "history": history
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(chat_data, f, ensure_ascii=False, indent=2)
            return filepath
        except Exception as e:
            return f"Error saving chat: {str(e)}"

    def save_current_chat(history, char_data):
        if not char_data or not history:
            return "No chat to save or character not selected."

        character_name = char_data.get('name', 'Unknown')
        result = save_chat_history(history, character_name)
        if result.startswith("Error"):
            return result
        return f"Chat saved successfully as {result}"

    def regenerate_last_message(history, char_data, api_name, api_key, temperature):
        if not history:
            return history

        last_user_message = history[-1][0]
        new_history = history[:-1]

        return character_chat_wrapper(last_user_message, new_history, char_data, api_name, api_key, temperature)

    import_chat_button.click(
        fn=lambda: gr.update(visible=True),
        outputs=chat_file_upload
    )

    chat_file_upload.change(
        fn=import_chat_history,
        inputs=[chat_file_upload, chat_history, character_data],
        outputs=[chat_history, character_data, save_status]
    )

    import_card_button.click(
        fn=import_character,
        inputs=[character_card_upload],
        outputs=[character_data, character_dropdown]
    )

    load_characters_button.click(
        fn=lambda: gr.update(choices=get_character_names()),
        outputs=character_dropdown
    )

    character_dropdown.change(
        fn=load_character,
        inputs=[character_dropdown],
        outputs=[character_data, chat_history]
    )

    send_message_button.click(
        fn=character_chat_wrapper,
        inputs=[user_input, chat_history, character_data, api_name_input, api_key_input, temperature_slider],
        outputs=[chat_history]
    ).then(lambda: "", outputs=user_input)

    regenerate_button.click(
        fn=regenerate_last_message,
        inputs=[chat_history, character_data, api_name_input, api_key_input, temperature_slider],
        outputs=[chat_history]
    )

    save_chat_button.click(
        fn=save_current_chat,
        inputs=[chat_history, character_data],
        outputs=[save_status]
    )

    return character_data, chat_history, user_input


def create_mikupad_tab():
    with gr.TabItem("Mikupad"):
        gr.Markdown("I Wish. Gradio won't embed it successfully...")


#
#
################################################################################################################
#
# Utilities Tab Functions

def create_utilities_yt_video_tab():
    with gr.Tab("YouTube Video Downloader"):
        with gr.Row():
            with gr.Column():
                gr.Markdown(
                    "<h3>Youtube Video Downloader</h3><p>This Input takes a Youtube URL as input and creates a webm file for you to download. </br><em>If you want a full-featured one:</em> <strong><em>https://github.com/StefanLobbenmeier/youtube-dl-gui</strong></em> or <strong><em>https://github.com/yt-dlg/yt-dlg</em></strong></p>")
                youtube_url_input = gr.Textbox(label="YouTube URL", placeholder="Enter YouTube video URL here")
                download_button = gr.Button("Download Video")
            with gr.Column():
                output_file = gr.File(label="Download Video")
                output_message = gr.Textbox(label="Status")

        download_button.click(
            fn=gradio_download_youtube_video,
            inputs=youtube_url_input,
            outputs=[output_file, output_message]
        )

def create_utilities_yt_audio_tab():
    with gr.Tab("YouTube Audio Downloader"):
        with gr.Row():
            with gr.Column():
                gr.Markdown(
                    "<h3>Youtube Audio Downloader</h3><p>This Input takes a Youtube URL as input and creates an audio file for you to download.</p>"
                    +"\n<em>If you want a full-featured one:</em> <strong><em>https://github.com/StefanLobbenmeier/youtube-dl-gui</strong></em>\n or \n<strong><em>https://github.com/yt-dlg/yt-dlg</em></strong></p>")
                youtube_url_input_audio = gr.Textbox(label="YouTube URL", placeholder="Enter YouTube video URL here")
                download_button_audio = gr.Button("Download Audio")
            with gr.Column():
                output_file_audio = gr.File(label="Download Audio")
                output_message_audio = gr.Textbox(label="Status")

        download_button_audio.click(
            fn=download_youtube_audio,
            inputs=youtube_url_input_audio,
            outputs=[output_file_audio, output_message_audio]
        )

def create_utilities_yt_timestamp_tab():
    with gr.Tab("YouTube Timestamp URL Generator"):
        gr.Markdown("## Generate YouTube URL with Timestamp")
        with gr.Row():
            with gr.Column():
                url_input = gr.Textbox(label="YouTube URL")
                hours_input = gr.Number(label="Hours", value=0, minimum=0, precision=0)
                minutes_input = gr.Number(label="Minutes", value=0, minimum=0, maximum=59, precision=0)
                seconds_input = gr.Number(label="Seconds", value=0, minimum=0, maximum=59, precision=0)
                generate_button = gr.Button("Generate URL")
            with gr.Column():
                output_url = gr.Textbox(label="Timestamped URL")

        generate_button.click(
            fn=generate_timestamped_url,
            inputs=[url_input, hours_input, minutes_input, seconds_input],
            outputs=output_url
        )

#
# End of Utilities Tab Functions
################################################################################################################

# FIXME - Prompt sample box
#
# # Sample data
# prompts_category_1 = [
#     "What are the key points discussed in the video?",
#     "Summarize the main arguments made by the speaker.",
#     "Describe the conclusions of the study presented."
# ]
#
# prompts_category_2 = [
#     "How does the proposed solution address the problem?",
#     "What are the implications of the findings?",
#     "Can you explain the theory behind the observed phenomenon?"
# ]
#
# all_prompts2 = prompts_category_1 + prompts_category_2


def launch_ui(share_public=None, server_mode=False):
    share=share_public
    css = """
    .result-box {
        margin-bottom: 20px;
        border: 1px solid #ddd;
        padding: 10px;
    }
    .result-box.error {
        border-color: #ff0000;
        background-color: #ffeeee;
    }
    .transcription, .summary {
        max-height: 300px;
        overflow-y: auto;
        border: 1px solid #eee;
        padding: 10px;
        margin-top: 10px;
    }
    """

    with gr.Blocks(theme='bethecloud/storj_theme',css=css) as iface:
        db_config = get_db_config()
        db_type = db_config['type']
        gr.Markdown(f"# tl/dw: Your LLM-powered Research Multi-tool")
        gr.Markdown(f"(Using {db_type.capitalize()} Database)")
        with gr.Tabs():
            with gr.TabItem("Transcription / Summarization / Ingestion"):
                with gr.Tabs():
                    create_video_transcription_tab()
                    create_audio_processing_tab()
                    create_podcast_tab()
                    create_import_book_tab()
                    create_website_scraping_tab()
                    create_pdf_ingestion_tab()
                    create_pdf_ingestion_test_tab()
                    create_resummary_tab()
                    create_summarize_explain_tab()

            with gr.TabItem("Search / Detailed View"):
                create_search_tab()
                create_rag_tab()
                create_embeddings_tab()
                create_viewing_tab()
                create_search_summaries_tab()
                create_prompt_search_tab()
                create_prompt_view_tab()

            with gr.TabItem("Chat with an LLM"):
                create_chat_interface()
                create_chat_interface_stacked()
                create_chat_interface_multi_api()
                create_chat_interface_four()
                create_chat_with_llamafile_tab()
                create_chat_management_tab()
                chat_workflows_tab()
                create_character_card_interaction_tab()


            with gr.TabItem("Edit Existing Items"):
                create_media_edit_tab()
                create_media_edit_and_clone_tab()
                create_prompt_edit_tab()
                create_prompt_clone_tab()
                # FIXME
                #create_compare_transcripts_tab()

            with gr.TabItem("Writing Tools"):
                with gr.Tabs():
                    create_document_feedback_tab()
                    create_grammar_style_check_tab()
                    create_tone_adjustment_tab()
                    create_creative_writing_tab()
                    create_mikupad_tab()


            with gr.TabItem("Keywords"):
                create_view_keywords_tab()
                create_add_keyword_tab()
                create_delete_keyword_tab()
                create_export_keywords_tab()

            with gr.TabItem("Import/Export"):
                create_import_item_tab()
                create_import_obsidian_vault_tab()
                create_import_single_prompt_tab()
                create_import_multiple_prompts_tab()
                create_export_tab()

            with gr.TabItem("Backup Management"):
                create_backup_tab()
                create_view_backups_tab()
                create_restore_backup_tab()

            with gr.TabItem("Utilities"):
                create_utilities_yt_video_tab()
                create_utilities_yt_audio_tab()
                create_utilities_yt_timestamp_tab()

            with gr.TabItem("Trashcan"):
                create_view_trash_tab()
                create_delete_trash_tab()
                create_empty_trash_tab()
            
            with gr.TabItem("Introduction/Help"):
                create_introduction_tab()

    # Launch the interface
    server_port_variable = 7860
    if share==True:
        iface.launch(share=True)
    elif server_mode and not share_public:
        iface.launch(share=False, server_name="0.0.0.0", server_port=server_port_variable)
    else:
        try:
            iface.launch(share=False)
        except Exception as e:
            logging.error(f"Error launching interface: {str(e)}")
