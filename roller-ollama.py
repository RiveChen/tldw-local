#!/usr/bin/env python3
from jinja2 import Template
import json
import requests
from dotenv import load_dotenv
import os

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL")
MODEL = os.getenv("OLLAMA_MODEL")


prompt_template = """
Continue the rolling transcription summary of "{{title}}".  Consider the current context when summarizing the given transcription part.

### Context: {{ context }}
Speaker-Map: {{ speakermap }}

### Transcription part {{ idx }} of {{ len }}, start time {{ start }}:
{{ chunk }}

### Instruction: Using the Context above, analyze the Trasncription and respond with a JSON object in this form:

{
    "Speaker-Map": { "SPEAKER 1": "Bob Dole", "SPEAKER 2": "Jane Doe" } // A map of speakers to their names, make sure to remember all previous speakers.
    "Next-Context": "..." // An updated context for the next part of the transcription. Always include the speakers and the current topics of discussion.
    "Summary": "..." // A detailed, point-by-point summary of the current transcription.
}
"""


def query_ollama(prompt: str, model: str = MODEL) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    response = requests.post(OLLAMA_URL, json=payload)
    if response.status_code == 200:
        return response.json().get("response", "")
    else:
        raise RuntimeError(
            f"Ollama request failed: {response.status_code}, {response.text}"
        )


def main(prefix: str, init_speakers: str = ""):
    the_template = Template(prompt_template)

    split_segments = json.load(open(prefix + ".chunk.json"))

    context = f"""
    Video Title: {prefix}
    """

    speakers = "{ UNKNOWN }"

    f = open(prefix + ".summary.json", "w")
    idx = 0
    for chunk in split_segments:
        dur = chunk["end"] - chunk["start"]
        print(f"{idx}: {dur}s {len(chunk)}")

        prompt = the_template.render(
            chunk=chunk["text"],
            start=chunk["start"],
            end=chunk["end"],
            idx=idx,
            len=len(split_segments),
            context=context,
            speakermap=speakers,
            title=prefix,
        )

        try:
            answer = query_ollama(prompt)
            parsed = json.loads(answer)
        except RuntimeError as e:
            print(f"Error querying ollama: {e}")
            exit(1)

        summary = parsed.get("Summary", "")
        new_speakers = parsed.get("Speaker-Map", "")
        new_context = parsed.get("Next-Context", "")

        if summary == "" or new_context == "" or new_speakers == "":
            print("Extraction failed:", new_context, new_speakers, summary)
            exit(1)
        else:

            section = {
                "start": chunk["start"],
                "end": chunk["end"],
                "summary": summary,
                "speakers": new_speakers,
                "context": new_context,
            }
            print("## ", new_speakers)
            print(">> ", new_context)
            print(summary)
            print()

            f.write(json.dumps(section) + "\n")
            f.flush()

            context = new_context
            speakers = new_speakers

        idx = idx + 1


if __name__ == "__main__":
    import fire

    fire.Fire(main)
