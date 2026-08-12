from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class PostBase(BaseModel):
    """Base schema for post data (common fields)"""
    title: str
    content: str
    author: str


class PostCreate(PostBase):
    """Schema for creating a new post (request)"""
    pass


class PostResponse(PostBase):
    """Schema for post response (reading)"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    """Schema for listing multiple posts"""
    total: int
    items: List[PostResponse]