from pydantic import BaseModel


class OAuthConnectResponse(BaseModel):
    provider: str
    authorization_url: str


class OAuthDiscoveredPage(BaseModel):
    id: str
    name: str
    tasks: list[str]


class OAuthCallbackResponse(BaseModel):
    provider: str
    status: str
    workspace_id: str
    page_count: int
    pages: list[OAuthDiscoveredPage]
