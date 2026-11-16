from fastapi import FastAPI

from app.schemas import PostingRequest, PostingResponse
from app.services.posting_service import post_to_all

app = FastAPI(
    title="Automated Multi-Platform Posting System",
    description="Publishes a short message with one CTA link to multiple platforms via their APIs.",
    version="1.0.0",
)


@app.post("/posting", response_model=PostingResponse, summary="Publish a message to all platforms")
async def posting(payload: PostingRequest) -> PostingResponse:
    return await post_to_all(payload.message, payload.link)


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}
