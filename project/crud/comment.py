from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from models.comment import Comment
from schemas.comment import CommentCreate


def get_comment(db: Session, comment_id: int) -> Optional[Comment]:
    """Get a single comment by ID"""
    return db.query(Comment).filter(Comment.id == comment_id).first()


def get_comments_by_post(db: Session, post_id: int, skip: int = 0, limit: int = 100) -> List[Comment]:
    """Get all comments for a specific post with pagination support"""
    return db.query(Comment).filter(Comment.post_id == post_id).offset(skip).limit(limit).all()


def create_comment(db: Session, comment: CommentCreate) -> Comment:
    """Create a new comment for a post"""
    db_comment = Comment(
        content=comment.content,
        author=comment.author,
        post_id=comment.post_id,
        created_at=datetime.utcnow()
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment


def update_comment(db: Session, comment_id: int, comment: CommentCreate) -> Optional[Comment]:
    """Update an existing comment"""
    db_comment = get_comment(db, comment_id)
    if not db_comment:
        return None
    
    db_comment.content = comment.content
    db_comment.author = comment.author
    db.commit()
    db.refresh(db_comment)
    return db_comment


def delete_comment(db: Session, comment_id: int) -> bool:
    """Delete a comment by ID"""
    db_comment = get_comment(db, comment_id)
    if not db_comment:
        return False
    
    db.delete(db_comment)
    db.commit()
    return True
