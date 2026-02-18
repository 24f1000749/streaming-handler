import os
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
