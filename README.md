# Too Long, Didn't Watch - Local

Summarize local videos using an Ollama server.

This project is a slimmed-down version of [tldw](https://github.com/the-crypt-keeper/tldw), from which the majority of the code originates. Special thanks to the original authors!

## Files

- **`diarize.py`** - Downloads, transcribes, and diarizes audio.
  - [FFmpeg](https://github.com/FFmpeg/FFmpeg) - Decompresses audio.
  - [faster_whisper](https://github.com/SYSTRAN/faster-whisper) - Converts speech to text.
  - [pyannote](https://github.com/pyannote/pyannote-audio) - Performs diarization.
- **`chunker.py`** - Splits text into segments and prepares them for LLM summarization.
- **`roller-ollama.py`** - Implements rolling summarization.

## Disclaimer

This project is currently under development and only for personal use.
