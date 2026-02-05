import asyncio
from fastmcp import Client

client = Client("http://localhost:8000/mcp")

async def call_tool(s: str):
    async with client:
        result = await client.call_tool("get_video_metadata", {"file_path": s})
        print(result)
        
        result = await client.call_tool("transcribe_video", {"file_path": s})
        print(result)

        result = await client.call_tool("cut_video", {
            "file_path": s,
            "start_time": 230.80,
            "end_time": 235.80
        })
        print(result)

        result = await client.call_tool("create_supercut", {
            "file_path": s,
            "segments": [
                [230.80 , 235.80],
                [410.80 , 414.80],
                [416.80 , 420.80]
            ]
        })
        print(result)

asyncio.run(call_tool('/Users/amuller/Documents/VideoExtractMCP/2025-12-19 15-17-42.mov'))