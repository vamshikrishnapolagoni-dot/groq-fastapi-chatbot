import httpx
from typing import List, Dict, Any, Optional
import logging
from backend.config import settings

logger = logging.getLogger("search_service")

class SearchService:
    def __init__(self):
        self.api_url = "https://api.tavily.com/search"

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Executes a web search query using Tavily Search API.
        If Tavily API key is not configured, returns a mock/empty result with a warning.
        """
        if not settings.TAVILY_API_KEY or settings.TAVILY_API_KEY == "YOUR_TAVILY_API_KEY":
            logger.warning("Tavily API key is not set. Skipping web search and returning blank results.")
            return []

        payload = {
            "api_key": settings.TAVILY_API_KEY,
            "query": query,
            "max_results": max_results,
            "include_raw_content": False,
            "include_images": False
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.api_url, json=payload, timeout=8.0)
                if response.status_code != 200:
                    logger.error(f"Tavily API error: Status {response.status_code} - {response.text}")
                    return []
                
                data = response.json()
                results = data.get("results", [])
                
                # Format to a standard output
                formatted_results = []
                for res in results:
                    formatted_results.append({
                        "title": res.get("title", "Untitled Source"),
                        "url": res.get("url", ""),
                        "snippet": res.get("content", ""),
                        "score": res.get("score", 0.0)
                    })
                return formatted_results
        except Exception as e:
            logger.error(f"Exception during Tavily search: {e}")
            return []

# Singleton instantiation
search_service = SearchService()
