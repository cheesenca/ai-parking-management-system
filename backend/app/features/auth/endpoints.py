from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import AdminUser

logger = logging.getLogger(__name__)
router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "e8d6d16d4bcaed978853d2f4b6f5efb7b6bc58bcfcde3f9352f8f5f3ca38a51e")
ALGORITHM = "HS256"
EXPIRE_MIN = int(os.getenv("TOKEN_EXPIRE_MINUTES", "480"))   

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "Security"
    location: Optional[str] = "west"


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    location: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: str
    new_password: str


class AuthUserResponse(BaseModel):
    username: str
    role: str
    location: Optional[str]


class UserResponse(BaseModel):
    admin_id: int
    username: str
    email: str
    role: str
    location: Optional[str]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verifies whether the plaintext password input matches the hash in the database
    """
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        return pwd_context.verify(plain, hashed)
    return plain == hashed


def hash_password(plain: str) -> str:
    """
    Convert plain-text passwords into a secure bcrypt hash format
    """
    return pwd_context.hash(plain)


def create_token(data: dict, expire_minutes: int = EXPIRE_MIN) -> str:
    """
    Issuing a JWT with an expiration time claim
    """
    payload = {**data, "exp": datetime.utcnow() + timedelta(minutes=expire_minutes)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Dependency Injection to secure endpoints
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="The token is invalid or has expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as exc:
        logger.warning("Invalid or expired token rejected: %s", exc)
        raise credentials_exception
        
    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if user is None:
        logger.warning("Token valid but user '%s' no longer exists", username)
        raise credentials_exception
    return user


def require_admin(current_user: AdminUser = Depends(get_current_user)) -> AdminUser:
    """
    Dependency that restricts an endpoint to users with the 'Admin' role
    """
    if current_user.role != "Admin":
        logger.warning("Forbidden: user '%s' (role=%s) attempted an admin-only action", current_user.username, current_user.role)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage user accounts",
        )
    return current_user


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Endpoint for user authentication
    """
    admin = db.query(AdminUser).filter(AdminUser.username == req.username).first()
    if not admin or not verify_password(req.password, admin.password):
        logger.warning("Failed login attempt for username '%s'", req.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    logger.info("User '%s' logged in successfully (role=%s)", admin.username, admin.role)

    token = create_token({
        "sub": admin.username,
        "role": admin.role,
        "location": admin.location,
        "admin_id": admin.admin_id,
    })

    return LoginResponse(
        access_token=token,
        user=AuthUserResponse(
            username=admin.username,
            role=admin.role,
            location=admin.location,
        ),
    )


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_admin),
):
    """
    Admin-only: list all Admin/Security accounts for the User Management screen.
    """
    users = db.query(AdminUser).order_by(AdminUser.username.asc()).all()
    return [
        UserResponse(
            admin_id=u.admin_id, username=u.username, email=u.email,
            role=u.role, location=u.location,
        )
        for u in users
    ]


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def create_user(
    req: UserCreate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_admin),
):
    """
    Create a new Admin or Security account
    """
    existing_user = db.query(AdminUser).filter(
        (AdminUser.username == req.username) | (AdminUser.email == req.email)
    ).first()

    if existing_user:
        logger.warning(
            "User creation rejected: username/email already taken (username='%s', email='%s')",
            req.username, req.email,
        )
        raise HTTPException(status_code=400, detail="Username or Email already registered")

    new_admin = AdminUser(
        username=req.username,
        email=req.email,
        password=hash_password(req.password),
        role=req.role,
        location=req.location if req.role != "Admin" else None,
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    logger.info("New account created by admin '%s': username='%s', role='%s'", admin.username, req.username, req.role)
    return UserResponse(
        admin_id=new_admin.admin_id, username=new_admin.username, email=new_admin.email,
        role=new_admin.role, location=new_admin.location,
    )


@router.put("/users/{admin_id}", response_model=UserResponse)
def update_user(
    admin_id: int,
    req: UserUpdate,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_admin),
):
    """
    Update an existing Admin/Security account's profile, role, or password.
    """
    target = db.query(AdminUser).filter(AdminUser.admin_id == admin_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if req.username and req.username != target.username:
        if db.query(AdminUser).filter(AdminUser.username == req.username).first():
            raise HTTPException(status_code=400, detail="Username already taken")
        target.username = req.username

    if req.email and req.email != target.email:
        if db.query(AdminUser).filter(AdminUser.email == req.email).first():
            raise HTTPException(status_code=400, detail="Email already taken")
        target.email = req.email

    if req.role:
        target.role = req.role

    if req.location is not None:
        target.location = req.location if target.role != "Admin" else None

    if req.password:
        target.password = hash_password(req.password)

    db.commit()
    db.refresh(target)
    logger.info("User '%s' updated by admin '%s'", target.username, admin.username)
    return UserResponse(
        admin_id=target.admin_id, username=target.username, email=target.email,
        role=target.role, location=target.location,
    )


@router.delete("/users/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    admin_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_admin),
):
    """
    Remove an Admin/Security account. Admins cannot delete their own account.
    """
    if admin_id == admin.admin_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    target = db.query(AdminUser).filter(AdminUser.admin_id == admin_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(target)
    db.commit()
    logger.info("User '%s' deleted by admin '%s'", target.username, admin.username)


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Demo simulation endpoint for resetting a user's password based on email verification
    """
    user = db.query(AdminUser).filter(AdminUser.email == req.email).first()
    if not user:
        logger.warning("Password reset requested for unknown email '%s'", req.email)
        return {"message": "If the email is registered, the password has been reset"}
        
    user.password = hash_password(req.new_password)
    db.commit()
    logger.info("Password reset for user '%s'", user.username)
    return {"message": "Password has been reset"}


@router.get("/me", response_model=AuthUserResponse)
def me(current_user: AdminUser = Depends(get_current_user)):
    """
    Protected endpoint for retrieving profile information of the currently logged-in user
    """
    return AuthUserResponse(
        username=current_user.username,
        role=current_user.role,
        location=current_user.location
    )
