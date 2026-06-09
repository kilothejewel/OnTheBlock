import base64
import json
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User

security = HTTPBearer()

def decode_token_payload(token: str) -> dict:
    """
    Decodes the JWT token payload without signature verification (for local development/simplicity),
    or returns mock payload for local portfolio testing.
    """
    # Support mock tokens for local/demo runs
    if token.startswith("mock_token_"):
        user_id = token.replace("mock_token_", "")
        return {
            "sub": user_id,
            "email": f"{user_id}@example.com"
        }
        
    try:
        # JWT format is header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT token format")
            
        payload_b64 = parts[1]
        # Adjust base64 padding
        payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to retrieve the current user.
    Auto-registers the user in the local database if they are authenticating for the first time.
    """
    token = credentials.credentials
    payload = decode_token_payload(token)
    
    supabase_uid = payload.get("sub")
    email = payload.get("email")
    
    if not supabase_uid or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token: missing sub or email",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Check if user exists in our local SQL database, if not, auto-sync them
    user = db.query(User).filter(User.supabase_uid == supabase_uid).first()
    if not user:
        user = User(supabase_uid=supabase_uid, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)
        
    return user
