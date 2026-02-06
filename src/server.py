from fastmcp import FastMCP
from faster_whisper import WhisperModel
import ffmpeg
import os
import json
from typing import Optional
from utils import create_blurred_background_filter, build_drawtext_filters

# init the MCP
mcp = FastMCP("Media Factory")

# load the light whisper model
print("Loading Whisper model...")
model = WhisperModel("base")
print("Model loaded")

@mcp.tool
def get_video_metadata(file_path: str) -> str:
    """
    Get all technical details about a video file (duration, resolution, format)
    Use this first to verify the file exist and is valid
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at :{file_path}"

    try:
        probe = ffmpeg.probe(file_path)

        format_info = probe.get('format', {})
        duration = float(format_info.get('duration', 0))
        filename = os.path.basename(file_path)

        video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        info = [f"File: {filename}", f"Duration: {duration:.2f}"]

        if video_stream:
            width = video_stream.get('width', 'N/A')
            height = video_stream.get('height', 'N/A')
            codec = video_stream.get('codec_name', 'N/A')
            info.append(f"Video: {width}x{height} ({codec})")
        else:
            info.append("Type: Audio only")

        return "\n".join(info)
    except Exception as e:
        return f"{type(e).__name__}: {e}"

@mcp.tool
def get_raw_transcript(file_path: str) -> str:
    """
    Get the full transcript as JSON
    This must be called to get text for context or generate captions
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at :{file_path}"

    try:
        segments, _ = model.transcribe(file_path, word_timestamps=True)

        data = []
        for s in segments:
            data.append({
                "start": round(s.start, 2),
                "end": round(s.end, 2),
                "text": s.text.strip()
            })
        return json.dumps(data, indent=2)

    except Exception as e:
        return f"{type(e).__name__}: {e}"

@mcp.tool
def extract_clip(file_path: str, start_time: float, end_time: float, output_format: str = 'original', captions: Optional[list[dict]] = None) -> str:
    """
    Extract a specific clip from a video file

    Args:
        file_path: Path to the source video
        start_time: Start time in seconds
        end_time: End time in seconds
        output_format: 'original' (keep aspect ratio) or 'short' (convert to 9:16)
        captions: Optional list of dicts [{"start": 0, "end": 5, "text": "..."}]. timestamps are relative to the clip
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at :{file_path}"

    base, ext = os.path.splitext(file_path)
    final_output = f"{base}_clip_{output_format}{ext}"

    try:
        input_stream = ffmpeg.input(file_path, ss=start_time, to=end_time)
        video_track = input_stream.video
        audio_track = input_stream.audio

        if output_format == 'short':
            video_track = create_blurred_background_filter(video_track)

        # apply captions via drawtext filters
        if captions:
            probe = ffmpeg.probe(file_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            if output_format == 'short':
                video_width, video_height = 1080, 1920
            else:
                video_width = int(video_info['width'])
                video_height = int(video_info['height'])
            video_track = build_drawtext_filters(video_track, captions, video_width, video_height)

        (
            ffmpeg
            .output(video_track, audio_track, final_output)
            .overwrite_output()
            .run(quiet=True)
        )

        return f"Success! Clip saved to: {final_output}"

    except ffmpeg.Error as e:
        return f"Error cutting video: {e.stderr.decode()}"

@mcp.tool()
def create_supercut(file_path: str, segments: list[list[float]], output_format: str = 'original', captions: Optional[list[dict]] = None) -> str:
    """
    Extracts multiple time segments and concatenates them into a single video.

    Args:
        file_path: Path to the source video.
        segments: A list of [start, end] pairs (in seconds).
                  Example: [[10.5, 20.0], [50.0, 60.5]] will combine
                  seconds 10.5-20.0 AND 50.0-60.5 into one video.
        output_format: 'original' (keep aspect ratio) or 'short' (convert to 9:16)
        captions: Optional list of dicts [{"start": 0, "end": 5, "text": "..."}]. timestamps are relative to the clip
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at: {file_path}"

    if not segments:
        return "Error: No segments provided."

    base, ext = os.path.splitext(file_path)
    final_output = f"{base}_supercut_{output_format}{ext}"

    try:
        input_streams = []
        for start, end in segments:
            clip = ffmpeg.input(file_path, ss=start, to=end)
            input_streams.append(clip.video)
            input_streams.append(clip.audio)

        joined = ffmpeg.concat(*input_streams, v=1, a=1)
        video_track = joined.node[0]
        audio_track = joined.node[1]

        if output_format == 'short':
            video_track = create_blurred_background_filter(video_track)

        # apply captions via drawtext filters
        if captions:
            probe = ffmpeg.probe(file_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            if output_format == 'short':
                video_width, video_height = 1080, 1920
            else:
                video_width = int(video_info['width'])
                video_height = int(video_info['height'])
            video_track = build_drawtext_filters(video_track, captions, video_width, video_height)

        (
            ffmpeg
            .output(video_track, audio_track, final_output)
            .overwrite_output()
            .run(quiet=True)
        )

        return f"Success! Supercut created at: {final_output}"

    except ffmpeg.Error as e:
        error_log = e.stderr.decode() if e.stderr else "No details"
        return f"FFmpeg Error: {error_log}"
