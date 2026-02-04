import asyncio
from fastmcp import Client

client = Client("http://localhost:8000/mcp")

async def call_tool(s: str):
    async with client:
        result = await client.call_tool("get_video_metadata", {"file_path": s})
        print(result)

asyncio.run(call_tool('miao'))