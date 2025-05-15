import os
import sys
import logging
import time
from io import StringIO
from contextlib import redirect_stdout
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agno.agent import Agent
from agno.tools.postgres import PostgresTools
from agno.models.groq import Groq

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI()

# Add CORS middleware to allow browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production (e.g., ["https://yourdomain.com"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY is not set in environment or .env file")
os.environ["GROQ_API_KEY"] = api_key

# Initialize PostgresTools
postgres_tools = PostgresTools(
    db_name='planmans',
    user='planmans',
    password='Ls4LEZ#c!u',
    host='localhost',
    port='5433'
)

# Create the agent
agent = Agent(
    tools=[postgres_tools],
    model=Groq(id="qwen-qwq-32b"),
    instructions="""
You are a PostgreSQL assistant for all tables in the `planmans` database. Process user prompts to perform database operations or provide information as requested. Follow these guidelines:
- Execute SQL commands or queries based on the prompt (e.g., SELECT, INSERT, UPDATE, DELETE).
- Return results in a clear, structured format.
- If the prompt is ambiguous, return an error asking for clarification.
- If the database is read-only, report the issue and suggest checking permissions, transaction settings, or primary node status.
- Use table metadata (e.g., from show_tables()) to validate inputs if needed.
"""
)

# Pydantic model for prompt input
class PromptRequest(BaseModel):
    prompt: str

def capture_printed_output(command: str) -> str:
    """Capture printed output from agent.print_response."""
    output = StringIO()
    with redirect_stdout(output):
        try:
            agent.print_response(command)
        except Exception as e:
            logger.error(f"Error in agent.print_response: {str(e)}")
            return f"Error in agent.print_response: {str(e)}"
    captured = output.getvalue().strip()
    logger.info(f"Captured output for command '{command}': {captured}")
    return captured if captured else "No output captured"

def process_prompt(prompt: str) -> str:
    """Process the user prompt with retry logic for rate limits."""
    logger.info(f"Processing prompt: {prompt}")
    max_retries = 3
    retry_delay = 5  # Initial delay in seconds

    for attempt in range(max_retries):
        try:
            response = agent.print_response(prompt)
            logger.info(f"Raw response from agent: {response}")
            # If response is None or empty, capture printed output
            if not response:
                response = capture_printed_output(prompt)
            if not response:
                logger.warning("No response received from the agent")
                raise HTTPException(status_code=500, detail="No response received from the agent")
            return response
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if "429" in str(e).lower() or "too many requests" in str(e).lower():
                if attempt < max_retries - 1:
                    logger.info(f"Rate limit hit, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": str(e),
                        "message": "Rate limit exceeded for Groq API after retries. Please try again later or check your API key quota."
                    }
                )
            if "read-only" in str(e).lower():
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": str(e),
                        "message": "Database is read-only. Please check:",
                        "suggestions": [
                            "Permissions: GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO planmans;",
                            "Transaction: Ensure not in read-only mode.",
                            "Database: Verify primary node (SELECT pg_is_in_recovery(); should return false)."
                        ]
                    }
                )
            raise HTTPException(status_code=500, detail=f"Error processing prompt: {str(e)}")

# HTML form for browser-based prompt input
@app.get("/", response_class=HTMLResponse)
async def get_prompt_form():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PostgreSQL Prompt Assistant</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px;  background-color: hsla(50, 28%, 66%, 1.75);}
            h1 {color: #007bff; }
            textarea { width: 100%; height: 100px; }
            button { padding: 10px 20px; background-color: #007bff; color: white; border: none; cursor: pointer; }
            button:hover { background-color: #0056b3; }
            #response { margin-top: 20px; white-space: pre-wrap; border: 1px solid #ddd; padding: 10px; }
            #error { color: red; margin-top: 10px; }
        </style>
    </head>
    <body>
        <h1>PostgreSQL Prompt Assistant</h1>
        <form id="promptForm">
            <label for="prompt">Enter your prompt (e.g., "Show all records in vehicles_vehicles"):</label><br>
            <textarea id="prompt" name="prompt" required></textarea><br>
            <button type="submit">Submit</button>
        </form>
        <div id="response"></div>
        <div id="error"></div>
        <script>
            document.getElementById("promptForm").addEventListener("submit", async (e) => {
                e.preventDefault();
                const prompt = document.getElementById("prompt").value;
                const responseDiv = document.getElementById("response");
                const errorDiv = document.getElementById("error");
                responseDiv.textContent = "";
                errorDiv.textContent = "";
                try {
                    const res = await fetch("/prompt", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ prompt })
                    });
                    const data = await res.json();
                    console.log("Response data:", data); // Debug in browser console
                    if (res.ok) {
                        // Display the result, handling strings or objects
                        responseDiv.textContent = typeof data.result === "string" ? data.result : JSON.stringify(data.result, null, 2);
                    } else {
                        errorDiv.textContent = `Error: ${JSON.stringify(data, null, 2)}`;
                    }
                } catch (err) {
                    errorDiv.textContent = `Network Error: ${err.message}`;
                    console.error("Fetch error:", err); // Debug in browser console
                }
            });
        </script>
    </body>
    </html>
    """

# POST endpoint for processing prompts
@app.post("/prompt")
async def handle_prompt(request: PromptRequest):
    result = process_prompt(request.prompt)
    return {"status": "success", "result": result}

# Test endpoint to verify frontend connectivity
@app.get("/test")
async def test_endpoint():
    return {"message": "Test endpoint is working"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)