from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    marketplace: str = Field(pattern="^(ebay|reverb|etsy)$")
    sync_type: str = Field(default="status", pattern="^(search|status)$")
    idempotency_key: str = Field(min_length=8, max_length=255)
    item_ids: list[str] = Field(default_factory=list, max_length=50000)
