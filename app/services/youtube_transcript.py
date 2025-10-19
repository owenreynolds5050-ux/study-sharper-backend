# app/services/youtube_transcript.py
import httpx
import os
from typing import Dict

async def fetch_youtube_transcript(youtube_url: str) -> Dict[str, str]:
    """
    Fetch YouTube transcript via n8n workflow.
    
    Args:
        youtube_url: YouTube video URL
        
    Returns:
        dict: {
            "title": video title,
            "transcript": full transcript text
        }
    """
    
    # Get n8n webhook URL from environment
    n8n_webhook_url = os.getenv("N8N_YOUTUBE_WEBHOOK_URL")
    
    if not n8n_webhook_url:
        raise ValueError("N8N_YOUTUBE_WEBHOOK_URL not configured in environment variables")
    
    # Call n8n webhook
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            n8n_webhook_url,
            json={"url": youtube_url}
        )
        
        if response.status_code != 200:
            raise ValueError(f"n8n workflow failed: {response.text}")
        
        data = response.json()
        
        # Expected response format from n8n:
        # {
        #     "title": "Video Title",
        #     "transcript": "Full transcript text..."
        # }
        
        if "transcript" not in data:
            raise ValueError("Invalid response from n8n workflow")
        
        # Format as markdown
        title = data.get("title", "YouTube Video")
        transcript = data["transcript"]
        
        formatted_transcript = f"# {title}\n\n**Source:** {youtube_url}\n\n---\n\n{transcript}"
        
        return {
            "title": title,
            "transcript": formatted_transcript
        }
