from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List

from config import settings
from database import get_db, engine
import models
from crud import post as post_crud
from schemas import post as post_schema
from routers import comment

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Include the comment router
app.include_router(comment.router)

# OAuth2 authentication setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Simple in-memory user storage (in production, use a database)
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": "admin123",  # In production, hash this properly!
        "disabled": False
    }
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return plain_password == hashed_password

def get_user(db, username: str):
    """Get a user by username"""
    if username in db:
        user_dict = db[username]
        return user_dict
    return None

def authenticate_user(fake_db, username: str, password: str):
    """Authenticate a user by username and password"""
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False
    return user

@app.get("/")
async def root():
    return {"message": "Welcome to the Blog API"}

# Authentication endpoint
@app.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """Authenticate user and return a token"""
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # In production, generate a proper JWT token here
    return {"access_token": user["username"], "token_type": "bearer"}

def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get the current authenticated user from the token"""
    user = get_user(fake_users_db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@app.post("/posts", response_model=post_schema.PostResponse)
def create_post(
    post: post_schema.PostCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new blog post (requires authentication)"""
    return post_crud.create_post(db=db, post=post)

@app.get("/posts", response_model=List[post_schema.PostResponse])
def read_posts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve all posts with pagination (public endpoint)"""
    posts = post_crud.get_posts(db, skip=skip, limit=limit)
    return posts

@app.get("/posts/{post_id}", response_model=post_schema.PostResponse)
def read_post(post_id: int, db: Session = Depends(get_db)):
    """Retrieve a specific post by ID (public endpoint)"""
    post = post_crud.get_post(db, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@app.put("/posts/{post_id}", response_model=post_schema.PostResponse)
def update_post(
    post_id: int,
    post: post_schema.PostCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update an existing post (requires authentication)"""
    updated_post = post_crud.update_post(db, post_id, post)
    if not updated_post:
        raise HTTPException(status_code=404, detail="Post not found")
    return updated_post

@app.delete("/posts/{post_id}")
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a post (requires authentication)"""
    deleted = post_crud.delete_post(db, post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"message": "Post deleted successfully"}