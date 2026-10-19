import json
from typing import Any

import httpx


class TinyFishClient:
    def __init__(self, api_key: str, search_url: str, fetch_url: str, agent_url: str | None = None):
        self.api_key, self.search_url, self.fetch_url = api_key, search_url, fetch_url
        self.agent_url = agent_url or "https://agent.tinyfish.ai/v1/automation/run"

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    def search(self, query: str) -> dict:
        response = httpx.get(self.search_url, headers=self._headers(), params={"query": query}, timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch(self, urls: list[str]) -> dict:
        response = httpx.post(self.fetch_url, headers=self._headers(), json={"urls": urls, "format": "markdown"}, timeout=90)
        response.raise_for_status()
        return response.json()

    def run_agent(self, url: str, goal: str) -> dict[str, Any]:
        response = httpx.post(self.agent_url, headers=self._headers(), json={"url": url, "goal": goal}, timeout=180)
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "COMPLETED":
            raise RuntimeError(f"TinyFish Agent did not complete: {payload.get('status', 'unknown')}")
        result = payload.get("result")
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {"raw_result": result}
        return result if isinstance(result, dict) else {"result": result}
