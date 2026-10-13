from __future__ import annotations

import os
import logging
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import AdminUser

logger = logging.getLogger(__name__)
router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    logger.warning(
        "SECRET_KEY is not set in the environment. Generated a random key for this session"
    )
ALGORITHM = "HS256"
EXPIRE_MIN = int(os.getenv("TOKEN_EXPIRE_MINUTES", "480"))
RESET_TOKEN_EXPIRE_MIN = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "15"))

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


class ResetPasswordRequest(BaseModel):
    email: str
    token: str
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
    """Verifies whether the plaintext password input matches the bcrypt hash stored in the database"""
    try:
        return pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def hash_password(plain: str) -> str:
    """Convert plain-text passwords into a secure bcrypt hash format"""
    return pwd_context.hash(plain)


def _hash_reset_token(token: str) -> str:
    """Reset tokens are stored hashed"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_token(data: dict, expire_minutes: int = EXPIRE_MIN) -> str:
    """Issuing a JWT with an expiration time claim"""
    payload = {**data, "exp": datetime.utcnow() + timedelta(minutes=expire_minutes)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Dependency Injection to secure endpoints"""
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
    """Dependency that restricts an endpoint to users with the 'Admin' role"""
    if current_user.role != "Admin":
        logger.warning("Forbidden: user '%s' (role=%s) attempted an admin-only action", current_user.username, current_user.role)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage user accounts",
        )
    return current_user


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Endpoint for user authentication"""
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
    """Admin-only: list all Admin/Security accounts for the User Management screen"""
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
    """Create a new Admin or Security account"""
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
    """Update an existing Admin/Security account's profile, role, or password"""
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
    """Remove an Admin/Security account. Admins cannot delete their own account"""
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
    """Issue a short-lived, single-use token for the account matching the given email."""
    user = db.query(AdminUser).filter(AdminUser.email == req.email).first()
    generic_response = {"message": "If the email is registered, a reset link has been sent"}

    if not user:
        logger.warning("Password reset requested for unknown email '%s'", req.email)
        return generic_response

    raw_token = secrets.token_urlsafe(32)
    user.reset_token_hash = _hash_reset_token(raw_token)
    user.reset_token_expires = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRE_MIN)
    db.commit()
    logger.info("Password reset token issued for user '%s'", user.username)

    return {**generic_response, "token": raw_token, "expires_in_minutes": RESET_TOKEN_EXPIRE_MIN}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Consume the token issued by /forgot-password and set a new password"""
    invalid_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Reset token is invalid or has expired",
    )

    user = db.query(AdminUser).filter(AdminUser.email == req.email).first()
    if not user or not user.reset_token_hash or not user.reset_token_expires:
        raise invalid_exception

    if datetime.utcnow() > user.reset_token_expires:
        raise invalid_exception

    if not secrets.compare_digest(user.reset_token_hash, _hash_reset_token(req.token)):
        logger.warning("Invalid password reset token presented for '%s'", req.email)
        raise invalid_exception

    user.password = hash_password(req.new_password)
    user.reset_token_hash = None
    user.reset_token_expires = None
    db.commit()
    logger.info("Password reset completed for user '%s'", user.username)
    return {"message": "Password has been reset"}


@router.get("/me", response_model=AuthUserResponse)
def me(current_user: AdminUser = Depends(get_current_user)):
    """Protected endpoint for retrieving profile information of the currently logged-in user"""
    return AuthUserResponse(
        username=current_user.username,
        role=current_user.role,
        location=current_user.location
    )