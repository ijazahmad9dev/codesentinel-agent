from .post import (
    get_post,
    get_posts,
    create_post,
    update_post,
    delete_post
)

from .comment import (
    get_comment,
    get_comments_by_post,
    create_comment,
    update_comment,
    delete_comment
)

__all__ = [
    "get_post",
    "get_posts", 
    "create_post",
    "update_post",
    "delete_post",
    "get_comment",
    "get_comments_by_post",
    "create_comment",
    "update_comment",
    "delete_comment"
]