import os
import subprocess


def extract_audio(video_path: str, output_path: str) -> str:
    """
    Extract 16kHz mono WAV audio from video using FFmpeg.
    FFmpeg must be installed and available on PATH.
    Raises RuntimeError if extraction fails.
    """
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",           # strip video stream
        "-ar", "16000",  # 16kHz — optimal for Sarvam.ai saarika:v2
        "-ac", "1",      # mono
        "-f", "wav",
        output_path,
        "-y",            # overwrite without asking
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr[-500:]}")

    if not os.path.exists(output_path):
        raise RuntimeError("FFmpeg ran successfully but produced no output file")

    return output_path
