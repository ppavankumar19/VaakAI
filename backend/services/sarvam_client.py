import os
import subprocess
import tempfile
from pathlib import Path
import httpx


SARVAM_API_URL = "https://api.sarvam.ai/speech-to-text"
CHUNK_SECONDS = 25  # Sarvam limit is 30s; use 25s for safety


def _get_duration(audio_path: str) -> float:
    """Return audio duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def _split_audio(audio_path: str, chunk_dir: str, chunk_seconds: int) -> list[str]:
    """Split audio into chunk_seconds-long WAV files. Returns list of chunk paths."""
    output_pattern = os.path.join(chunk_dir, "chunk_%03d.wav")
    subprocess.run(
        [
            "ffmpeg", "-i", audio_path,
            "-f", "segment",
            "-segment_time", str(chunk_seconds),
            "-ar", "16000", "-ac", "1",
            "-y", output_pattern,
        ],
        capture_output=True, text=True, timeout=300, check=True,
    )
    chunks = sorted(
        os.path.join(chunk_dir, f)
        for f in os.listdir(chunk_dir)
        if f.startswith("chunk_") and f.endswith(".wav")
    )
    return chunks


def _transcribe_chunk(chunk_path: str, api_key: str, lang: str) -> list:
    """Send one chunk to Sarvam and return parsed segments."""
    with open(chunk_path, "rb") as f:
        response = httpx.post(
            SARVAM_API_URL,
            headers={"api-subscription-key": api_key},
            data={
                "model": "saarika:v2.5",
                "language_code": lang,
                "with_timestamps": "true",
                "with_disfluency": "true",
            },
            files={"file": (Path(chunk_path).name, f, "audio/wav")},
            timeout=300.0,
        )
    if not response.is_success:
        raise RuntimeError(f"Sarvam.ai {response.status_code}: {response.text}")
    return _parse_response(response.json())


def transcribe_audio(audio_path: str, language_code: str = "en-IN") -> list:
    """
    Transcribe audio via Sarvam.ai saarika:v2.5.
    Splits into 25s chunks automatically (API limit is 30s).

    Returns list of:
        {"start_ms": int, "end_ms": int, "text": str, "confidence": float}
    """
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise ValueError("SARVAM_API_KEY environment variable is not set")

    lang = language_code if language_code != "auto" else "en-IN"

    duration = _get_duration(audio_path)

    # Short audio — send directly
    if duration <= CHUNK_SECONDS:
        return _transcribe_chunk(audio_path, api_key, lang)

    # Long audio — split, transcribe each chunk, merge with time offset
    all_segments = []
    with tempfile.TemporaryDirectory() as chunk_dir:
        chunks = _split_audio(audio_path, chunk_dir, CHUNK_SECONDS)
        for i, chunk_path in enumerate(chunks):
            offset_ms = i * CHUNK_SECONDS * 1000
            segments = _transcribe_chunk(chunk_path, api_key, lang)
            for seg in segments:
                seg["start_ms"] += offset_ms
                seg["end_ms"] += offset_ms
            all_segments.extend(segments)

    return all_segments


def _parse_response(data: dict) -> list:
    """
    Parse Sarvam.ai v2.5 response.
    timestamps is a dict: {words: [...], start_time_seconds: [...], end_time_seconds: [...]}
    Each entry in 'words' is a text segment (may span multiple sentences).
    """
    transcript_text: str = data.get("transcript", "")
    ts = data.get("timestamps", {})

    # v2.5 format: parallel arrays
    if isinstance(ts, dict):
        words = ts.get("words", [])
        starts = ts.get("start_time_seconds", [])
        ends = ts.get("end_time_seconds", [])

        if not words:
            if transcript_text.strip():
                return [{"start_ms": 0, "end_ms": 0, "text": transcript_text.strip(), "confidence": 1.0}]
            return []

        segments = []
        for i, text in enumerate(words):
            text = text.strip()
            if not text:
                continue
            start_ms = int(starts[i] * 1000) if i < len(starts) else 0
            end_ms = int(ends[i] * 1000) if i < len(ends) else 0
            segments.append({
                "start_ms": start_ms,
                "end_ms": end_ms,
                "text": text,
                "confidence": 0.95,
            })
        return segments

    # Fallback: no usable timestamps
    if transcript_text.strip():
        return [{"start_ms": 0, "end_ms": 0, "text": transcript_text.strip(), "confidence": 1.0}]
    return []
