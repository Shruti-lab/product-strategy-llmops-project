from pydantic import BaseModel, EmailStr


class SessionRequest(BaseModel):
    session_id: str
    user_id: str
    email: EmailStr