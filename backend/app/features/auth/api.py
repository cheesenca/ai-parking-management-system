from __future__ import annotations
import os
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

router = APIRouter()

SECRET_KEY = os.getenv("SECRET_KEY", "e8d6d16d4bcaed978853d2f4b6f5efb7b6bc58bcfcde3f9352f8f5f3ca38a51e")
ALGORITHM = "HS256"
EXPIRE_MIN = int(os.getenv("TOKEN_EXPIRE_MINUTES", "480"))   

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "Security" 
    location: Optional[str] = "west"


class ForgotPasswordRequest(BaseModel):
    email: str
    new_password: str


class AuthUserResponse(BaseModel):
    username: str
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
        detail="Token tidak valid atau sudah kadaluarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if user is None:
        raise credentials_exception
    return user


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Endpoint for user authentication
    """
    admin = db.query(AdminUser).filter(AdminUser.username == req.username).first()
    if not admin or not verify_password(req.password, admin.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
        )

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


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    Endpoint for registering a new administrator or security officer account
    """
    existing_user = db.query(AdminUser).filter(
        (AdminUser.username == req.username) | (AdminUser.email == req.email)
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Username atau Email sudah terdaftar")
        
    new_admin = AdminUser(
        username=req.username,
        email=req.email,
        password=hash_password(req.password),
        role=req.role,
        location=req.location
    )
    db.add(new_admin)
    db.commit()
    return {"message": "Registrasi berhasil"}


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Demo simulation endpoint for resetting a user's password based on email verification
    """
    user = db.query(AdminUser).filter(AdminUser.email == req.email).first()
    if not user:
        return {"message": "Jika email terdaftar, password telah direset."}
        
    user.password = hash_password(req.new_password)
    db.commit()
    return {"message": "Password berhasil direset (Demo Version)."}


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
