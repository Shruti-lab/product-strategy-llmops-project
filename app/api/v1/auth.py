"""Authentication and authorization endpoints for the API.

This module provides endpoints for user registration, login, session management,
and token verification.
"""


import uuid
from typing import List


from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
)


from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)