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
    
    return f"Valid path: {file_path}"

@mcp.tool
def transcribe_video(file_path: str) -> str:
    """
    Transcribe the audio of a vido file to text with timestamps
    Return format: [Start - End] Text
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at :{file_path}"
    
    return f"path: {file_path}"

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