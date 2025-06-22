from pydantic import BaseModel
from typing import Any, Optional

# Pydantic model for script request
class ScriptRequest(BaseModel):
    script_id: str

# Pydantic model for tunnel creation request
class CreateTunnelRequest(BaseModel):
    script_id: str
    timeout_minutes: Optional[int] = None

# Pydantic model for tunnel response
class TunnelResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    tunnel_url: Optional[str] = None
    complete_url: Optional[str] = None
    script_id: Optional[str] = None
    error: Optional[str] = None
    note: Optional[str] = None

# Pydantic model for script execution response
class ScriptResponse(BaseModel):
    success: bool
    message: str
    script_id: str
    result: Any  # Accept any type, not just dict
    error: Optional[str] = None

class StartNgrokTunnelRequest(BaseModel):
    script_id: str
    port: int = 8099
    name: str = "publish-scripts-tunnel"

class StopNgrokTunnelRequest(BaseModel):
    script_id: str 