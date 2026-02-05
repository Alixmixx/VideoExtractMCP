import asyncio
from fastmcp import Client

client = Client("http://localhost:8000/mcp")

async def call_tool(s: str):
    async with client:
        result = await client.call_tool("get_video_metadata", {"file_path": s})
        print(result)
        
        result = await client.call_tool("get_raw_transcript", {"file_path": s})
        print(result)

        result = await client.call_tool("extract_clip", {
            "file_path": s,
            "start_time": 230.80,
            "end_time": 235.80,
            "output_format": 'short',
            "captions": [
                {"start": 0.5, "end": 2.5, "text": "Testing single clip caption"},
                {"start": 3.0, "end": 4.5, "text": "Vertical blur check"}
            ]
        })
        print(result)

        result = await client.call_tool("create_supercut", {
            "file_path": s,
            "segments": [
                [230.80 , 235.80],
                [410.80 , 414.80]
            ],
            "output_format": 'short',
            "captions": [
                {"start": 1.0, "end": 4.0, "text": "Supercut Segment 1"},
                {"start": 6.0, "end": 8.0, "text": "Supercut Segment 2"}
            ]
        })
        print(result)

asyncio.run(call_tool('/Users/amuller/Documents/VideoExtractMCP/2025-12-19 15-17-42.mov'))