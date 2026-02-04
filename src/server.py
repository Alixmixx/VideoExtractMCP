from fastmcp import FastMCP
from faster_whisper import WhisperModel
import ffmpeg
import os

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
def transcribe_video(file_path: str) -> str:
    """
    Transcribe the audio of a vido file to text with timestamps
    Return format: [Start - End] Text
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at :{file_path}"
    
    try:
        segments, _ = model.transcribe(file_path, beam_size=5)
        transcript = []

        for segment in segments:
            # format [00.00 -> 00.00] text
            line = f"[{segment.start:.2f} -> {segment.end:.2f}] {segment.text}"
            transcript.append(line)

        return "\n".join(transcript)

    except Exception as e:
        return f"{type(e).__name__}: {e}"

@mcp.tool
def cut_video(file_path: str, start_time: float, end_time: float) -> str:
    """
    Extarct a specific clip from a video file
    
    Args:
        file_path: Path to the source video
        start_time: Start time in seconds
        end_timeL End time in seconds
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at :{file_path}"
    return ""