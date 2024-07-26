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
import math
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, time
import json
import logging
import os.path
from pathlib import Path
import sqlite3
from typing import Dict, List, Tuple, Optional
import traceback
from functools import wraps

import pypandoc
#
# Import 3rd-Party Libraries
import yt_dlp
import gradio as gr
#
# Local Imports
from App_Function_Libraries.Article_Summarization_Lib import scrape_and_summarize_multiple
from App_Function_Libraries.Audio_Files import process_audio_files, process_podcast
from App_Function_Libraries.Chunk_Lib import improved_chunking_process
from App_Function_Libraries.PDF_Ingestion_Lib import process_and_cleanup_pdf
from App_Function_Libraries.Local_LLM_Inference_Engine_Lib import local_llm_gui_function
from App_Function_Libraries.Local_Summarization_Lib import summarize_with_llama, summarize_with_kobold, \
    summarize_with_oobabooga, summarize_with_tabbyapi, summarize_with_vllm, summarize_with_local_llm
from App_Function_Libraries.Summarization_General_Lib import summarize_with_openai, summarize_with_cohere, \
    summarize_with_anthropic, summarize_with_groq, summarize_with_openrouter, summarize_with_deepseek, \
    summarize_with_huggingface, perform_summarization, save_transcription_and_summary, \
    perform_transcription, summarize_chunk
from App_Function_Libraries.SQLite_DB import update_media_content, list_prompts, search_and_display, db, DatabaseError, \
    fetch_prompt_details, keywords_browser_interface, add_keyword, delete_keyword, \
    export_keywords_to_csv, add_media_to_database, insert_prompt_to_db, import_obsidian_note_to_db
from App_Function_Libraries.Utils import sanitize_filename, extract_text_from_segments, create_download_directory, \
    convert_to_seconds, load_comprehensive_config
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


def load_preset_prompts():
    return list_prompts()


def gradio_download_youtube_video(url):
    """Download video using yt-dlp with specified options."""
    # Determine ffmpeg path based on the operating system.
    ffmpeg_path = './Bin/ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'

    # Extract information about the video
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        sanitized_title = sanitize_filename(info_dict['title'])
        original_ext = info_dict['ext']

    # Setup the final directory and filename
    download_dir = Path(f"results/{sanitized_title}")
    download_dir.mkdir(parents=True, exist_ok=True)
    output_file_path = download_dir / f"{sanitized_title}.{original_ext}"

    # Initialize yt-dlp with generic options and the output template
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'ffmpeg_location': ffmpeg_path,
        'outtmpl': str(output_file_path),
        'noplaylist': True, 'quiet': True
    }

    # Execute yt-dlp to download the video
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Final check to ensure file exists
    if not output_file_path.exists():
        raise FileNotFoundError(f"Expected file was not found: {output_file_path}")

    return str(output_file_path)




def format_transcription(content):
    # Add extra space after periods for better readability
    content = content.replace('.', '. ').replace('.  ', '. ')
    # Split the content into lines for multiline display
    lines = content.split('. ')
    # Join lines with HTML line break for better presentation in Markdown
    formatted_content = "<br>".join(lines)
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

def display_details(media_id):
    # Gradio Search Function-related stuff
    if media_id:
        details = display_item_details(media_id)
        details_html = ""
        for detail in details:
            details_html += f"<h4>Prompt:</h4><p>{detail[0]}</p>"
            details_html += f"<h4>Summary:</h4><p>{detail[1]}</p>"
            details_html += f"<h4>Transcription:</h4><pre>{detail[2]}</pre><hr>"
        return details_html
    return "No details available."


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


def display_item_details(media_id):
    # Function to display item details
    prompt_summary_results, content = fetch_item_details(media_id)
    content_section = f"<h4>Transcription:</h4><pre>{content}</pre><hr>"
    prompt_summary_section = ""
    for prompt, summary in prompt_summary_results:
        prompt_summary_section += f"<h4>Prompt:</h4><p>{prompt}</p>"
        prompt_summary_section += f"<h4>Summary:</h4><p>{summary}</p><hr>"
    return prompt_summary_section, content_section


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
                    details_html += f"<h4>Prompt:</h4>{prompt}</p>"
                if summary:
                    details_html += f"<h4>Summary:</h4>{summary}</p>"
                # Format the transcription content for better readability
                content_html = f"<h4>Transcription:</h4><div style='white-space: pre-wrap;'>{format_transcription(content)}</div>"
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
        details = fetch_prompt_details(selected_prompt)
        if details:
            details_str = f"<h4>Details:</h4><p>{details[0]}</p>"
            system_str = f"<h4>System:</h4><p>{details[1]}</p>"
            user_str = f"<h4>User:</h4><p>{details[2]}</p>" if details[2] else ""
            return details_str + system_str + user_str
    return "No details available."

def search_media_database(query: str) -> List[Tuple[int, str, str]]:
    return browse_items(query, 'Title')


def load_media_content(media_id: int) -> dict:
    try:
        print(f"Debug - Load Media Content - Media ID: {media_id}")
        item_details = fetch_item_details(media_id)
        print(f"Debug - Load Media Content - Item Details: {item_details}")

        if isinstance(item_details, tuple) and len(item_details) == 3:
            content, prompt, summary = item_details
        else:
            print(f"Debug - Load Media Content - Unexpected item_details format: {item_details}")
            content, prompt, summary = "", "", ""

        return {
            "content": content or "No content available",
            "prompt": prompt or "No prompt available",
            "summary": summary or "No summary available"
        }
    except Exception as e:
        print(f"Debug - Load Media Content - Error: {str(e)}")
        return {"content": "", "prompt": "", "summary": ""}


# FIXME - not adding content from selected item to query
def chat(message, history, media_content, selected_parts, api_endpoint, api_key, prompt):
    try:
        print(f"Debug - Chat Function - Message: {message}")
        print(f"Debug - Chat Function - Media Content: {media_content}")
        print(f"Debug - Chat Function - Selected Parts: {selected_parts}")
        print(f"Debug - Chat Function - API Endpoint: {api_endpoint}")
        print(f"Debug - Chat Function - Prompt: {prompt}")

        # Ensure selected_parts is a list
        if not isinstance(selected_parts, (list, tuple)):
            selected_parts = [selected_parts] if selected_parts else []

        print(f"Debug - Chat Function - Selected Parts (after check): {selected_parts}")

        # Combine the selected parts of the media content
        combined_content = "\n\n".join([f"{part.capitalize()}: {media_content.get(part, '')}" for part in selected_parts if part in media_content])
        print(f"Debug - Chat Function - Combined Content: {combined_content[:500]}...")  # Print first 500 chars

        # Prepare the input for the API
        input_data = f"{combined_content}\n\nUser: {message}\nAI:"
        print(f"Debug - Chat Function - Input Data: {input_data[:500]}...")  # Print first 500 chars

        # Use the existing API request code based on the selected endpoint
        if api_endpoint.lower() == 'openai':
            response = summarize_with_openai(api_key, input_data, prompt)
        elif api_endpoint.lower() == "anthropic":
            response = summarize_with_anthropic(api_key, input_data, prompt)
        elif api_endpoint.lower() == "cohere":
            response = summarize_with_cohere(api_key, input_data, prompt)
        elif api_endpoint.lower() == "groq":
            response = summarize_with_groq(api_key, input_data, prompt)
        elif api_endpoint.lower() == "openrouter":
            response = summarize_with_openrouter(api_key, input_data, prompt)
        elif api_endpoint.lower() == "deepseek":
            response = summarize_with_deepseek(api_key, input_data, prompt)
        elif api_endpoint.lower() == "llama.cpp":
            response = summarize_with_llama(input_data, prompt)
        elif api_endpoint.lower() == "kobold":
            response = summarize_with_kobold(input_data, api_key, prompt)
        elif api_endpoint.lower() == "ooba":
            response = summarize_with_oobabooga(input_data, api_key, prompt)
        elif api_endpoint.lower() == "tabbyapi":
            response = summarize_with_tabbyapi(input_data, prompt)
        elif api_endpoint.lower() == "vllm":
            response = summarize_with_vllm(input_data, prompt)
        elif api_endpoint.lower() == "local-llm":
            response = summarize_with_local_llm(input_data, prompt)
        elif api_endpoint.lower() == "huggingface":
            response = summarize_with_huggingface(api_key, input_data, prompt)
        else:
            raise ValueError(f"Unsupported API endpoint: {api_endpoint}")

        return response

    except Exception as e:
        logging.error(f"Error in chat function: {str(e)}")
        return f"An error occurred: {str(e)}"


def save_chat_history(history: List[List[str]], media_content: Dict[str, str], selected_parts: List[str],
                      api_endpoint: str, prompt: str):
    """
    Save the chat history along with context information to a JSON file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chat_history_{timestamp}.json"

    chat_data = {
        "timestamp": timestamp,
        "history": history,
        "context": {
            "selected_media": {
                part: media_content.get(part, "") for part in selected_parts
            },
            "api_endpoint": api_endpoint,
            "prompt": prompt
        }
    }

    json_data = json.dumps(chat_data, indent=2)

    return filename, json_data


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



def create_video_transcription_tab():
    with gr.TabItem("Video Transcription + Summarization"):
        gr.Markdown("# Transcribe & Summarize Videos from URLs")
        with gr.Row():
            gr.Markdown("""Follow this project at [tldw - GitHub](https://github.com/rmusser01/tldw)""")
        with gr.Row():
            with gr.Column():
                url_input = gr.Textbox(label="URL(s) (Mandatory)",
                                       placeholder="Enter video URLs here, one per line. Supports YouTube, Vimeo, and playlists.",
                                       lines=5)
                video_file_input = gr.File(label="Upload Video File (Optional)", file_types=["video/*"])
                diarize_input = gr.Checkbox(label="Enable Speaker Diarization", value=False)
                whisper_model_input = gr.Dropdown(choices=whisper_models, value="medium", label="Whisper Model")
                custom_prompt_checkbox = gr.Checkbox(label="Use Custom Prompt", value=False, visible=True)
                custom_prompt_input = gr.Textbox(label="Custom Prompt", placeholder="Enter custom prompt here", lines=3, visible=False)
                custom_prompt_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[custom_prompt_checkbox],
                    outputs=[custom_prompt_input]
                )
                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "HuggingFace"],
                    value=None, label="API Name (Mandatory)")
                api_key_input = gr.Textbox(label="API Key (Mandatory)", placeholder="Enter your API key here")
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

                                logging.debug("Gradio_Related.py: process_url_with_metadata being called")
                                result = process_url_with_metadata(
                                    input_item, 2, whisper_model,
                                    custom_prompt if custom_prompt_checkbox else None,
                                    start_seconds, api_name, api_key,
                                    False, False, False, False, 0.01, None, keywords, None, diarize,
                                    end_time=end_seconds,
                                    include_timestamps=(timestamp_option == "Include Timestamps"),
                                    metadata=video_metadata,
                                    use_chunking=chunking_options_checkbox,
                                    chunk_options=chunk_options,
                                    keep_original_video=keep_original_video
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

                            summary = open(summary_file, 'r').read() if summary_file else "No summary available"

                            results_html += f"""
                            <div class="result-box">
                                <gradio-accordion>
                                    <gradio-accordion-item label="{title}">
                                        <p><strong>URL:</strong> <a href="{url}" target="_blank">{url}</a></p>
                                        <h4>Metadata:</h4>
                                        <pre>{metadata_text}</pre>
                                        <h4>Transcription:</h4>
                                        <div class="transcription">{transcription_text}</div>
                                        <h4>Summary:</h4>
                                        <div class="summary">{summary}</div>
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
                    with open('all_transcriptions.json', 'w') as f:
                        json.dump(all_transcriptions, f, indent=2)

                    with open('all_summaries.txt', 'w') as f:
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

                    # Handle both URL input and file upload
                    inputs = []
                    if url_input:
                        inputs.extend([url.strip() for url in url_input.split('\n') if url.strip()])
                    if video_file is not None:
                        inputs.append(video_file.name)  # Assuming video_file is a file object with a 'name' attribute

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
                        f"process_videos_wrapper(): An error occurred: {str(e)}",  # progress_output
                        str(e),  # error_output
                        f"<div class='error'>Error: {str(e)}</div>",  # results_output
                        None,  # download_transcription
                        None  # download_summary
                    )

            # FIXME - remove dead args for process_url_with_metadata
            @error_handler
            def process_url_with_metadata(input_item, num_speakers, whisper_model, custom_prompt, offset, api_name, api_key,
                                          vad_filter, download_video_flag, download_audio, rolling_summarization,
                                          detail_level, question_box, keywords, local_file_path, diarize, end_time=None,
                                          include_timestamps=True, metadata=None, use_chunking=False,
                                          chunk_options=None, keep_original_video=False):

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
                        # Extract basic info from local file
                        info_dict = {
                            'webpage_url': input_item,
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
                        video_file_path = download_video(input_item, download_path, full_info, download_video_flag)
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
                custom_prompt_checkbox = gr.Checkbox(label="Use Custom Prompt", value=False, visible=True)
                custom_prompt_input = gr.Textbox(label="Custom Prompt", placeholder="Enter custom prompt here", lines=3, visible=False)
                custom_prompt_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[custom_prompt_checkbox],
                    outputs=[custom_prompt_input]
                )
                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "HuggingFace"],
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

                custom_prompt_checkbox = gr.Checkbox(label="Use Custom Prompt", value=False, visible=True)
                podcast_custom_prompt_input = gr.Textbox(
                    label="Custom Prompt",
                    placeholder="Enter custom prompt for summarization (optional)",
                    lines=3,
                    visible=False
                )
                custom_prompt_checkbox.change(
                    fn=lambda x: gr.update(visible=x),
                    inputs=[custom_prompt_checkbox],
                    outputs=[podcast_custom_prompt_input]
                )

                podcast_api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter", "Llama.cpp",
                             "Kobold", "Ooba", "Tabbyapi", "VLLM", "HuggingFace"],
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
                custom_prompt_input = gr.Textbox(label="Custom Prompt (Optional)",
                                                 placeholder="Provide a custom prompt for summarization", lines=3)
                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "HuggingFace"], value=None, label="API Name (Mandatory for Summarization)")
                api_key_input = gr.Textbox(label="API Key (Mandatory if API Name is specified)",
                                           placeholder="Enter your API key here; Ignore if using Local API or Built-in API")
                keywords_input = gr.Textbox(label="Keywords", placeholder="Enter keywords here (comma-separated)",
                                            value="default,no_keyword_set", visible=True)

                scrape_button = gr.Button("Scrape and Summarize")
            with gr.Column():
                result_output = gr.Textbox(label="Result", lines=20)

                scrape_button.click(
                    fn=scrape_and_summarize_multiple,
                    inputs=[url_input, custom_prompt_input, api_name_input, api_key_input, keywords_input,
                            custom_article_title_input],
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
                pdf_ingest_button = gr.Button("Ingest PDF")

                pdf_upload_button.upload(fn=lambda file: file, inputs=pdf_upload_button, outputs=pdf_file_input)
            with gr.Column():
                pdf_result_output = gr.Textbox(label="Result")

            pdf_ingest_button.click(
                fn=process_and_cleanup_pdf,
                inputs=[pdf_file_input, pdf_title_input, pdf_author_input, pdf_keywords_input],
                outputs=pdf_result_output
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
            search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
            search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title", label="Search By")
            search_button = gr.Button("Search")

        items_output = gr.Dropdown(label="Select Item", choices=[], interactive=True)
        item_mapping = gr.State({})

        with gr.Row():
            api_name_input = gr.Dropdown(
                choices=["Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter",
                         "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "HuggingFace"],
                value="Local-LLM", label="API Name")
            api_key_input = gr.Textbox(label="API Key", placeholder="Enter your API key here")

        chunking_options_checkbox = gr.Checkbox(label="Use Chunking", value=False)
        with gr.Row(visible=False) as chunking_options_box:
            chunk_method = gr.Dropdown(choices=['words', 'sentences', 'paragraphs', 'tokens', 'chapters'],
                                       label="Chunking Method", value='words')
            max_chunk_size = gr.Slider(minimum=100, maximum=1000, value=300, step=50, label="Max Chunk Size")
            chunk_overlap = gr.Slider(minimum=0, maximum=100, value=0, step=10, label="Chunk Overlap")

        custom_prompt_checkbox = gr.Checkbox(label="Use Custom Prompt", value=False)
        custom_prompt_input = gr.Textbox(label="Custom Prompt", placeholder="Enter custom prompt here", lines=3, visible=False)

        resummary_button = gr.Button("Re-Summarize")

        result_output = gr.Textbox(label="Result")

    # Connect the UI elements
    search_button.click(
        fn=update_resummary_dropdown,
        inputs=[search_query_input, search_type_input],
        outputs=[items_output, item_mapping]
    )

    chunking_options_checkbox.change(
        fn=lambda x: gr.update(visible=x),
        inputs=[chunking_options_checkbox],
        outputs=[chunking_options_box]
    )

    custom_prompt_checkbox.change(
        fn=lambda x: gr.update(visible=x),
        inputs=[custom_prompt_checkbox],
        outputs=[custom_prompt_input]
    )

    resummary_button.click(
        fn=resummary_content_wrapper,
        inputs=[items_output, item_mapping, api_name_input, api_key_input, chunking_options_checkbox, chunk_method,
                max_chunk_size, chunk_overlap, custom_prompt_checkbox, custom_prompt_input],
        outputs=result_output
    )

    return search_query_input, search_type_input, search_button, items_output, item_mapping, api_name_input, api_key_input, chunking_options_checkbox, chunking_options_box, chunk_method, max_chunk_size, chunk_overlap, custom_prompt_checkbox, custom_prompt_input, resummary_button, result_output


def update_resummary_dropdown(search_query, search_type):
    if search_type in ['Title', 'URL']:
        results = fetch_items_by_title_or_url(search_query, search_type)
    elif search_type == 'Keyword':
        results = fetch_items_by_keyword(search_query)
    else:  # Content
        results = fetch_items_by_content(search_query)

    item_options = [f"{item[1]} ({item[2]})" for item in results]
    item_mapping = {f"{item[1]} ({item[2]})": item[0] for item in results}
    return gr.update(choices=item_options), item_mapping


def resummary_content_wrapper(selected_item, item_mapping, api_name, api_key, chunking_options_checkbox, chunk_method,
                              max_chunk_size, chunk_overlap, custom_prompt_checkbox, custom_prompt):
    if not selected_item or not api_name or not api_key:
        return "Please select an item and provide API details."

    media_id = item_mapping.get(selected_item)
    if not media_id:
        return "Invalid selection."

    content, old_prompt, old_summary = fetch_item_details(media_id)

    if not content:
        return "No content available for re-summarization."

    # Prepare chunking options
    chunk_options = {
        'method': chunk_method,
        'max_size': int(max_chunk_size),
        'overlap': int(chunk_overlap),
        'language': 'english',
        'adaptive': True,
        'multi_level': False,
    } if chunking_options_checkbox else None

    # Prepare summarization prompt
    summarization_prompt = custom_prompt if custom_prompt_checkbox and custom_prompt else None

    # Call the resummary_content function
    result = resummary_content(media_id, content, api_name, api_key, chunk_options, summarization_prompt)

    return result


def resummary_content(selected_item, item_mapping, api_name, api_key, chunking_options_checkbox, chunk_method, max_chunk_size, chunk_overlap, custom_prompt_checkbox, custom_prompt):
    if not selected_item or not api_name or not api_key:
        return "Please select an item and provide API details."

    media_id = item_mapping.get(selected_item)
    if not media_id:
        return "Invalid selection."

    content, old_prompt, old_summary = fetch_item_details(media_id)

    if not content:
        return "No content available for re-summarization."

    # Load configuration
    config = load_comprehensive_config()

    # Prepare chunking options
    chunk_options = {
        'method': chunk_method,
        'max_size': int(max_chunk_size),
        'overlap': int(chunk_overlap),
        'language': 'english',
        'adaptive': True,
        'multi_level': False,
    }

    # Chunking logic
    if chunking_options_checkbox:
        chunks = improved_chunking_process(content, chunk_options)
    else:
        chunks = [{'text': content, 'metadata': {}}]

    # Prepare summarization prompt
    if custom_prompt_checkbox and custom_prompt:
        summarization_prompt = custom_prompt
    else:
        summarization_prompt = config.get('Prompts', 'default_summary_prompt', fallback="Summarize the following text:")

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
            return f"Re-summarization complete. New summary: {new_summary[:500]}..."
        else:
            return f"Error during database update: {update_result}"
    except Exception as e:
        logging.error(f"Error updating database: {str(e)}")
        return f"Error updating database: {str(e)}"

# End of Re-Summarization Functions
#
############################################################################################################################################################################################################################
#
# Search Tab

def add_or_update_prompt(title, description, system_prompt, user_prompt):
    if not title:
        return "Error: Title is required."

    existing_prompt = fetch_prompt_details(title)
    if existing_prompt:
        # Update existing prompt
        result = update_prompt_in_db(title, description, system_prompt, user_prompt)
    else:
        # Insert new prompt
        result = insert_prompt_to_db(title, description, system_prompt, user_prompt)

    # Refresh the prompt dropdown
    update_prompt_dropdown()
    return result


def load_prompt_details(selected_prompt):
    if selected_prompt:
        details = fetch_prompt_details(selected_prompt)
        if details:
            return details[0], details[1], details[2], details[3]
    return "", "", "", ""


def update_prompt_in_db(title, description, system_prompt, user_prompt):
    try:
        conn = sqlite3.connect('prompts.db')
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE Prompts SET details = ?, system = ?, user = ? WHERE name = ?",
            (description, system_prompt, user_prompt, title)
        )
        conn.commit()
        conn.close()
        return "Prompt updated successfully!"
    except sqlite3.Error as e:
        return f"Error updating prompt: {e}"


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


def create_prompt_view_tab():
    with gr.TabItem("Search Prompts"):
        with gr.Row():
            with gr.Column():
                gr.Markdown("# Search and View Prompt Details")
                gr.Markdown("Currently has all of the https://github.com/danielmiessler/fabric prompts already available")
                search_query_input = gr.Textbox(label="Search Prompts", placeholder="Enter your search query...")
                search_button = gr.Button("Search Prompts")
            with gr.Column():
                search_results_output = gr.Markdown()
                prompt_details_output = gr.HTML()
        search_button.click(
            fn=display_search_results,
            inputs=[search_query_input],
            outputs=[search_results_output]
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


def create_llamafile_settings_tab():
    with gr.TabItem("Local LLM with Llamafile"):
        gr.Markdown("# Settings for Llamafile")
        am_noob = gr.Checkbox(label="Check this to enable sane defaults", value=False, visible=True)
        advanced_mode_toggle = gr.Checkbox(label="Advanced Mode - Enable to show all settings", value=False)

        model_checked = gr.Checkbox(label="Enable Setting Local LLM Model Path", value=False, visible=True)
        model_value = gr.Textbox(label="Select Local Model File", value="", visible=True)
        ngl_checked = gr.Checkbox(label="Enable Setting GPU Layers", value=False, visible=True)
        ngl_value = gr.Number(label="Number of GPU Layers", value=None, precision=0, visible=True)

        advanced_inputs = create_llamafile_advanced_inputs()

        start_button = gr.Button("Start Llamafile")
        stop_button = gr.Button("Stop Llamafile")
        output_display = gr.Markdown()

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


def update_chat_content(selected_item, use_content, use_summary, use_prompt, item_mapping):
    print(f"Debug - Update Chat Content - Selected Item: {selected_item}")
    print(f"Debug - Update Chat Content - Use Content: {use_content}")
    print(f"Debug - Update Chat Content - Use Summary: {use_summary}")
    print(f"Debug - Update Chat Content - Use Prompt: {use_prompt}")
    print(f"Debug - Update Chat Content - Item Mapping: {item_mapping}")

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
                print(f"Debug - Update Chat Content - {key} (first 500 char): {str(value)[:500]}")
        else:
            print(f"Debug - Update Chat Content - Content(first 500 char): {str(content)[:500]}")

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


def update_user_prompt(preset_name):
    details = fetch_prompt_details(preset_name)
    if details:
        # 0 is title, 1 is details, 2 is system prompt, 3 is user prompt
        return details[2]  # Return the system prompt
    return ""


def chat_wrapper(message, history, media_content, selected_parts, api_endpoint, api_key, user_prompt):
    print(f"Debug - Chat Wrapper - Message: {message}")
    print(f"Debug - Chat Wrapper - Media Content: {media_content}")
    print(f"Debug - Chat Wrapper - Selected Parts: {selected_parts}")
    print(f"Debug - Chat Wrapper - API Endpoint: {api_endpoint}")
    print(f"Debug - Chat Wrapper - User Prompt: {user_prompt}")

    selected_content = "\n\n".join(
        [f"{part.capitalize()}: {media_content.get(part, '')}" for part in selected_parts if
         part in media_content])
    print(f"Debug - Chat Wrapper - Selected Content: {selected_content[:500]}...")  # Print first 500 chars

    context = f"Selected content:\n{selected_content}\n\nUser message: {message}"
    print(f"Debug - Chat Wrapper - Context: {context[:500]}...")  # Print first 500 chars

    # Use a default API endpoint if none is selected
    if not api_endpoint:
        api_endpoint = "OpenAI"  # You can change this to any default endpoint you prefer
        print(f"Debug - Chat Wrapper - Using default API Endpoint: {api_endpoint}")

    bot_message = chat(context, history, media_content, selected_parts, api_endpoint, api_key, user_prompt)
    print(f"Debug - Chat Wrapper - Bot Message: {bot_message[:500]}...")  # Print first 500 chars

    history.append((message, bot_message))
    return "", history


def create_chat_interface():
    with gr.TabItem("Remote LLM Chat"):
        gr.Markdown("# Chat with a designated LLM Endpoint, using your selected item as starting context")
        chat_history = gr.State([])
        media_content = gr.State({})
        selected_parts = gr.State([])

        with gr.Row():
            with gr.Column(scale=1):
                search_query_input = gr.Textbox(label="Search Query", placeholder="Enter your search query here...")
                search_type_input = gr.Radio(choices=["Title", "URL", "Keyword", "Content"], value="Title", label="Search By")
                search_button = gr.Button("Search")

            with gr.Column(scale=2):
                items_output = gr.Dropdown(label="Select Item", choices=[], interactive=True)
                item_mapping = gr.State({})

        with gr.Row():
            use_content = gr.Checkbox(label="Use Content")
            use_summary = gr.Checkbox(label="Use Summary")
            use_prompt = gr.Checkbox(label="Use Prompt")

        api_endpoint = gr.Dropdown(label="Select API Endpoint", choices=["Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter", "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "HuggingFace"])
        api_key = gr.Textbox(label="API Key (if required)", type="password")
        preset_prompt = gr.Dropdown(label="Select Preset Prompt", choices=load_preset_prompts())
        user_prompt = gr.Textbox(label="Modify Prompt (Need to delete this after the first message, otherwise it'll "
                                       "be used as the next message instead)", lines=3)
        chatbot = gr.Chatbot(height=500)
        msg = gr.Textbox(label="Enter your message")
        submit = gr.Button("Submit")
        save_button = gr.Button("Save Chat History")
        download_file = gr.File(label="Download Chat History")

        submit.click(
            chat_wrapper,
            inputs=[msg, chat_history, media_content, selected_parts, api_endpoint, api_key, user_prompt],
            outputs=[msg, chatbot]
        )

        save_button.click(save_chat_history, inputs=[chat_history], outputs=[download_file])

        search_button.click(
            fn=update_dropdown,
            inputs=[search_query_input, search_type_input],
            outputs=[items_output, item_mapping]
        )

        preset_prompt.change(update_user_prompt, inputs=preset_prompt, outputs=user_prompt)

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
        use_content.change(update_selected_parts, inputs=[use_content, use_summary, use_prompt],
                           outputs=[selected_parts])
        use_summary.change(update_selected_parts, inputs=[use_content, use_summary, use_prompt],
                           outputs=[selected_parts])
        use_prompt.change(update_selected_parts, inputs=[use_content, use_summary, use_prompt],
                          outputs=[selected_parts])
        items_output.change(debug_output, inputs=[media_content, selected_parts], outputs=[])

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
#
#
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
            time.sleep(0.1)  # Small delay to prevent UI freezing

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

        if isinstance(file, str):
            # If file is a string, it's likely a file path
            file_path = file
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
        elif hasattr(file, 'read'):
            # If file has a 'read' method, it's likely a file-like object
            file_content = file.read()
            if isinstance(file_content, bytes):
                file_content = file_content.decode('utf-8')
        else:
            # If it's neither a string nor a file-like object, try converting it to a string
            file_content = str(file)

        logging.debug(f"File name: {file_name}")
        logging.debug(f"File content (first 100 chars): {file_content[:100]}")

        # Create info_dict
        info_dict = {
            'title': title or 'Untitled',
            'uploader': author or 'Unknown',
        }

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
            whisper_model="Imported",  # Indicating this was an imported file,
            media_type = "document"
        )

        return f"File '{file_name}' successfully imported with title '{title}' and author '{author}'."
    except Exception as e:
        logging.error(f"Error importing file: {str(e)}")
        return f"Error importing file: {str(e)}"


def create_import_item_tab():
    with gr.TabItem("Import Markdown/Text Files"):
        gr.Markdown("# Import a markdown file or text file into the database")
        gr.Markdown("...and have it tagged + summarized")
        with gr.Row():
            import_file = gr.File(label="Upload file for import", file_types=["txt", "md"])
        with gr.Row():
            title_input = gr.Textbox(label="Title", placeholder="Enter the title of the content")
            author_input = gr.Textbox(label="Author", placeholder="Enter the author's name")
        with gr.Row():
            keywords_input = gr.Textbox(label="Keywords", placeholder="Enter keywords, comma-separated")
            custom_prompt_input = gr.Textbox(label="Custom Prompt",
                                             placeholder="Enter a custom prompt for summarization (optional)")
        with gr.Row():
            summary_input = gr.Textbox(label="Summary",
                                       placeholder="Enter a summary or leave blank for auto-summarization", lines=3)
        with gr.Row():
            auto_summarize_checkbox = gr.Checkbox(label="Auto-summarize", value=False)
            api_name_input = gr.Dropdown(
                choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter",
                         "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "HuggingFace"],
                label="API for Auto-summarization"
            )
            api_key_input = gr.Textbox(label="API Key", type="password")
        with gr.Row():
            import_button = gr.Button("Import Data")
        with gr.Row():
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
            vault_path_input = gr.Textbox(label="Obsidian Vault Path (Local)")
            vault_zip_input = gr.File(label="Upload Obsidian Vault (Zip)")
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
                custom_prompt_input = gr.Textbox(label="Custom Prompt",
                                                 placeholder="Enter a custom prompt for summarization (optional)")
                summary_input = gr.Textbox(label="Summary",
                                           placeholder="Enter a summary or leave blank for auto-summarization", lines=3)
                auto_summarize_checkbox = gr.Checkbox(label="Auto-summarize", value=False)
                api_name_input = gr.Dropdown(
                    choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter",
                             "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "HuggingFace"],
                    label="API for Auto-summarization"
                )
                api_key_input = gr.Textbox(label="API Key", type="password")
                import_button = gr.Button("Import Data")
            with gr.Column():
                with gr.Row():
                    import_output = gr.Textbox(label="Import Status")

        def import_epub(epub_file, title, author, keywords, custom_prompt, summary, auto_summarize, api_name, api_key):
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
                    return import_data(content, title, author, keywords, custom_prompt,
                                       summary, auto_summarize, api_name, api_key)
            except Exception as e:
                return f"Error processing EPUB: {str(e)}"

        import_button.click(
            fn=import_epub,
            inputs=[import_file, title_input, author_input, keywords_input, custom_prompt_input,
                    summary_input, auto_summarize_checkbox, api_name_input, api_key_input],
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
                markdown_content += f"## {item_data.get('title', f'Item {item_data['id']}')}\n\n### Prompt\n{prompt}\n\n### Summary\n{summary}\n\n### Content\n{content}\n\n---\n\n"
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
        search_query = gr.Textbox(label="Search Query")
        search_type = gr.Radio(["Title", "URL", "Keyword", "Content"], label="Search By")
        search_button = gr.Button("Search")

        with gr.Row():
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
        show_progress=True
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
        show_progress=True
    )

    export_by_keyword_button.click(
        fn=export_items_by_keyword,
        inputs=[keyword_input],
        outputs=[export_output, error_output],
        show_progress=True
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
        show_progress=True
    )


#
# End of Export Items Tab Functions
################################################################################################################
#
# Keyword Management Tab Functions

def create_export_keywords_tab():
    with gr.Group():
        with gr.Tab("Export Keywords"):
            export_keywords_button = gr.Button("Export Keywords")
            export_keywords_output = gr.File(label="Download Exported Keywords")
            export_keywords_status = gr.Textbox(label="Export Status")

            export_keywords_button.click(
                fn=export_keywords_to_csv,
                outputs=[export_keywords_status, export_keywords_output]
            )

def create_view_keywords_tab():
    with gr.TabItem("View Keywords"):
        gr.Markdown("# Browse Keywords")
        browse_output = gr.Markdown()
        browse_button = gr.Button("View Existing Keywords")
        browse_button.click(fn=keywords_browser_interface, outputs=browse_output)


def create_add_keyword_tab():
    with gr.TabItem("Add Keywords"):
        with gr.Row():
            gr.Markdown("# Add Keywords to the Database")
            add_input = gr.Textbox(label="Add Keywords (comma-separated)", placeholder="Enter keywords here...")
            add_button = gr.Button("Add Keywords")
        with gr.Row():
            add_output = gr.Textbox(label="Result")
            add_button.click(fn=add_keyword, inputs=add_input, outputs=add_output)


def create_delete_keyword_tab():
    with gr.Tab("Delete Keywords"):
        with gr.Row():
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


def grammar_style_check(input_text, custom_prompt, api_name, api_key):
    default_prompt = "Please analyze the following text for grammar and style. Offer suggestions for improvement and point out any misused words or incorrect spellings:\n\n"
    full_prompt = custom_prompt if custom_prompt else default_prompt
    full_text = full_prompt + input_text

    return perform_summarization(api_name, full_text, custom_prompt, api_key)


def create_document_editing_tab():
    with gr.Group():
        with gr.Tab("Grammar and Style Check"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("# Grammar and Style Check")
                    gr.Markdown("This utility checks the grammar and style of the provided text by feeding it to an LLM and returning suggestions for improvement.")
                    input_text = gr.Textbox(label="Input Text", lines=10)
                    custom_prompt_checkbox = gr.Checkbox(label="Use Custom Prompt", value=False, visible=True)
                    custom_prompt_input = gr.Textbox(label="Custom Prompt", placeholder="Please analyze the provided text for grammar and style. Offer any suggestions or points to improve you can identify. Additionally please point out any misuses of any words or incorrect spellings.", lines=5, visible=False)
                    custom_prompt_checkbox.change(
                        fn=lambda x: gr.update(visible=x),
                        inputs=[custom_prompt_checkbox],
                        outputs=[custom_prompt_input]
                    )
                    api_name_input = gr.Dropdown(
                        choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter",
                                 "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "HuggingFace"],
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
                    inputs=[input_text, custom_prompt_input, api_name_input, api_key_input],
                    outputs=output_text
                )

        # FIXME - Add actual function for this
        with gr.Tab("Tone Analyzer & Editor"):
            with gr.Row():
                with gr.Column():
                    input_text = gr.Textbox(label="Input Text", lines=10)
                    concise_slider = gr.Slider(minimum=0, maximum=1, value=0.5, label="Concise vs Expanded")
                    casual_slider = gr.Slider(minimum=0, maximum=1, value=0.5, label="Casual vs Professional")
                    api_name_input = gr.Dropdown(
                        choices=[None, "Local-LLM", "OpenAI", "Anthropic", "Cohere", "Groq", "DeepSeek", "OpenRouter",
                                 "Llama.cpp", "Kobold", "Ooba", "Tabbyapi", "VLLM", "HuggingFace"],
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


        with gr.Tab("Creative Writing Assistant"):
            gr.Markdown("# Utility to be added...")

        with gr.Tab("Mikupad"):
            gr.Markdown("I Wish. Gradio won't embed it successfully...")


#
#
################################################################################################################
#
# Utilities Tab Functions


def create_utilities_tab():
    with gr.Group():
        with gr.Tab("YouTube Video Downloader"):
            gr.Markdown(
                "<h3>Youtube Video Downloader</h3><p>This Input takes a Youtube URL as input and creates a webm file for you to download. </br><em>If you want a full-featured one:</em> <strong><em>https://github.com/StefanLobbenmeier/youtube-dl-gui</strong></em> or <strong><em>https://github.com/yt-dlg/yt-dlg</em></strong></p>")
            youtube_url_input = gr.Textbox(label="YouTube URL", placeholder="Enter YouTube video URL here")
            download_button = gr.Button("Download Video")
            output_file = gr.File(label="Download Video")

            download_button.click(
                fn=gradio_download_youtube_video,
                inputs=youtube_url_input,
                outputs=output_file
            )

        with gr.Tab("YouTube Audio Downloader"):
            gr.Markdown(
                "<h3>Youtube Audio Downloader</h3><p>This Input takes a Youtube URL as input and creates an audio file for you to download. </br><em>If you want a full-featured one:</em> <strong><em>https://github.com/StefanLobbenmeier/youtube-dl-gui</strong></em> or <strong><em>https://github.com/yt-dlg/yt-dlg</em></strong></p>")
            youtube_url_input_audio = gr.Textbox(label="YouTube URL", placeholder="Enter YouTube video URL here")
            download_button_audio = gr.Button("Download Audio")
            output_file_audio = gr.File(label="Download Audio")

            # Implement the audio download functionality here

        with gr.Tab("YouTube Timestamp URL Generator"):
            gr.Markdown("## Generate YouTube URL with Timestamp")
            with gr.Row():
                url_input = gr.Textbox(label="YouTube URL")
                hours_input = gr.Number(label="Hours", value=0, minimum=0, precision=0)
                minutes_input = gr.Number(label="Minutes", value=0, minimum=0, maximum=59, precision=0)
                seconds_input = gr.Number(label="Seconds", value=0, minimum=0, maximum=59, precision=0)

            generate_button = gr.Button("Generate URL")
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
        gr.Markdown("# TL/DW: Too Long, Didn't Watch - Your Personal Research Multi-Tool")
        with gr.Tabs():
            with gr.TabItem("Transcription / Summarization / Ingestion"):
                with gr.Tabs():
                    create_video_transcription_tab()
                    create_audio_processing_tab()
                    create_podcast_tab()
                    create_import_book_tab()
                    create_website_scraping_tab()
                    create_pdf_ingestion_tab()
                    create_resummary_tab()

            with gr.TabItem("Search / Detailed View"):
                create_search_tab()
                create_prompt_view_tab()
                create_prompt_edit_tab()

            with gr.TabItem("Local LLM with Llamafile"):
                create_llamafile_settings_tab()

            with gr.TabItem("Remote LLM Chat"):
                create_chat_interface()

            with gr.TabItem("Edit Existing Items"):
                create_media_edit_tab()

            with gr.TabItem("Keywords"):
                with gr.Tabs():
                    create_view_keywords_tab()
                    create_add_keyword_tab()
                    create_delete_keyword_tab()
                    create_export_keywords_tab()

            with gr.TabItem("Import/Export"):
                create_import_item_tab()
                create_import_obsidian_vault_tab()
                create_export_tab()

            with gr.TabItem("Document Editing"):
                create_document_editing_tab()

            with gr.TabItem("Utilities"):
                create_utilities_tab()


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
