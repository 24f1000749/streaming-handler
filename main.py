import os
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from dotenv import load_dotenv
import asyncio
import httpx
import os

@app.on_event("startup")
async def keep_warm():
    asyncio.create_task(_ping_self())

async def _ping_self():
    await asyncio.sleep(60)  # wait for server to fully start
    url = os.getenv("RENDER_EXTERNAL_URL", "")
    if not url:
        return
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await client.get(f"{url}/")
            except:
                pass
            await asyncio.sleep(840)  # ping every 14 minutes

load_dotenv()

app = FastAPI()
client = AsyncOpenAI(
    api_key=os.getenv("AIPIPE_TOKEN"),
    base_url="https://aipipe.org/openai/v1"   # ← points to AI Pipe instead of OpenAI
)


@app.post("/stream")
async def stream_response(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "Write a 250-word essay about AI ethics")

    async def generate():
        try:
            # ✅ KEY FIX: Use gpt-4o-mini — it's fast enough to beat the 2047ms limit
            stream = await client.chat.completions.create(
                model="gpt-4o-mini",   # 🔑 FAST model — this fixes your latency error
                messages=[
                    {
                        "role": "system",
                        "content": "You are an essay writer. Write detailed, well-structured essays with arguments and a conclusion."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=600,        # enough for 250 words
                stream=True,           # ✅ enables streaming
                temperature=0.7
            )

            # Send each chunk as it arrives (SSE format)
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    # Format: SSE data line
                    data = json.dumps({
                        "choices": [{"delta": {"content": delta.content}}]
                    })
                    yield f"data: {data}\n\n"

            # Signal the stream is done
            yield "data: [DONE]\n\n"

        except Exception as e:
            # Handle errors gracefully — send error in stream
            error_data = json.dumps({"error": str(e)})
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",   # ✅ SSE content type
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # ✅ prevents nginx from buffering
            "Connection": "keep-alive"
        }
    )


# Health check
@app.get("/")
async def root():
    return {"status": "ok"}
