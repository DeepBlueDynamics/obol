from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from ..models import AgentIdentity
from ..storage import storage
from ..auth import get_current_identity, get_optional_identity, AuthIdentity

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

@router.post("/register", response_model=AgentIdentity)
async def register_agent(
    agent: AgentIdentity,
    auth: AuthIdentity = Depends(get_current_identity)
):
    """Register or update an agent's identity, public keys, and capabilities."""
    agent.tenant_user_id = auth.user_id
    saved = storage.save_agent(agent)
    return saved

@router.get("", response_model=List[AgentIdentity])
async def list_agents():
    """List all registered agents and their advertised identities."""
    return storage.list_agents()

@router.get("/{principal}", response_model=AgentIdentity)
async def get_agent_profile(principal: str):
    """Retrieve details and public keys for a specific agent principal."""
    agent = storage.get_agent(principal)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with principal '{principal}' not found"
        )
    return agent
