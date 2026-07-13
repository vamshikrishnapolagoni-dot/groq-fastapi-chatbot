import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv
from groq import Groq
# Load environment variables
load_dotenv()
# Initialize the Groq client lazily
client = None
api_key = os.getenv("GROQ_API_KEY")
if api_key:
    client = Groq(api_key=api_key)


# Initialize FastAPI app
app = FastAPI(title="Groq AI Chatbot API")

# Mount standard static files directory
# Note: This will serve files from the "static" subdirectory
os.makedirs("static", exist_ok=True)

class ChatRequest(BaseModel):
    message: str
    history: List[List[str]] = []

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    global client
    if client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY is not set in the environment.")
        client = Groq(api_key=api_key)
    try:
        messages = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant."
            }
        ]

        # Append conversion history formatted for Groq completion API
        for turn in request.history:
            if len(turn) == 2:
                messages.append({"role": "user", "content": turn[0]})
                messages.append({"role": "assistant", "content": turn[1]})

        # Append current user message
        messages.append({
            "role": "user",
            "content": request.message
        })

        # Fetch completion from Groq API
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )

        reply_content = completion.choices[0].message.content
        return {"response": reply_content}

    except Exception as e:
        print(f"Error handling chat completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def get_index():
    index_path = os.path.join("static", "index.html")
    if not os.path.exists(index_path):
         return {"message": "Welcome to Groq AI Chatbot. Static files not yet generated."}
    return FileResponse(index_path)

# Mount static files *after* the root route, so index.html at root is served correctly
app.mount("/", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    # Run the server
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
