from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from models.post import Post
from schemas.post import PostCreate


def get_post(db: Session, post_id: int) -> Optional[Post]:
    """Get a single post by ID"""
    return db.query(Post).filter(Post.id == post_id).first()


def get_posts(db: Session, skip: int = 0, limit: int = 100) -> List[Post]:
    """Get all posts with pagination support"""
    return db.query(Post).offset(skip).limit(limit).all()


def create_post(db: Session, post: PostCreate) -> Post:
    """Create a new post"""
    db_post = Post(
        title=post.title,
        content=post.content,
        author=post.author,
        created_at=datetime.utcnow()
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post


def update_post(db: Session, post_id: int, post: PostCreate) -> Optional[Post]:
    """Update an existing post"""
    db_post = get_post(db, post_id)
    if not db_post:
        return None
    
    db_post.title = post.title
    db_post.content = post.content
    db_post.author = post.author
    db.commit()
    db.refresh(db_post)
    return db_post


def delete_post(db: Session, post_id: int) -> bool:
    """Delete a post by ID"""
    db_post = get_post(db, post_id)
    if not db_post:
        return False
    
    db.delete(db_post)
    db.commit()
    return True