from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import crud.comment as comment_crud
from schemas import comment as comment_schema

router = APIRouter(prefix="/posts/{post_id}/comments", tags=["comments"])


@router.post("/", response_model=comment_schema.CommentResponse)
def create_comment(
    post_id: int,
    comment: comment_schema.CommentCreate,
    db: Session = Depends(get_db)
):
    """Create a new comment for a specific post"""
    # Verify the post exists
    from crud import post as post_crud
    from database import get_db
    
    db_post = post_crud.get_post(db, post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return comment_crud.create_comment(db=db, comment=comment)


@router.get("/", response_model=List[comment_schema.CommentResponse])
def read_comments(
    post_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Retrieve all comments for a specific post with pagination"""
    # Verify the post exists
    from crud import post as post_crud
    
    db_post = post_crud.get_post(db, post_id)
    if not db_post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    comments = comment_crud.get_comments_by_post(db, post_id=post_id, skip=skip, limit=limit)
    return comments


@router.put("/{comment_id}", response_model=comment_schema.CommentResponse)
def update_comment(
    post_id: int,
    comment_id: int,
    comment: comment_schema.CommentCreate,
    db: Session = Depends(get_db)
):
    """Update an existing comment"""
    updated_comment = comment_crud.update_comment(db, comment_id, comment)
    if not updated_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    return updated_comment


@router.delete("/{comment_id}")
def delete_comment(
    post_id: int,
    comment_id: int,
    db: Session = Depends(get_db)
):
    """Delete a comment"""
    deleted = comment_crud.delete_comment(db, comment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Comment not found")
    return {"message": "Comment deleted successfully"}