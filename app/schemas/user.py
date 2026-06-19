from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value):
        if len(value) < 8:
            raise ValueError(
                "Password must be at least 8 characters"
            )

        if not any(c.isupper() for c in value):
            raise ValueError(
                "Password must contain an uppercase letter"
            )

        if not any(c.isdigit() for c in value):
            raise ValueError(
                "Password must contain a digit"
            )

        return value

class TokenData(BaseModel):
    token: str
    token_type: str
    
# class TokenData(BaseModel):
#     email: EmailStr