from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class CommentBase(BaseModel):
    """Base schema for comment data (common fields)"""
    content: str
    author: str


class CommentCreate(CommentBase):
    """Schema for creating a new comment (request)"""
    post_id: int


class CommentResponse(CommentBase):
    """Schema for comment response (reading)"""
    id: int
    post_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CommentListResponse(BaseModel):
    """Schema for listing multiple comments"""
    total: int
    items: List[CommentResponse]