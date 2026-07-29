from pydantic import BaseModel, Field
class CreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str | None = None
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
