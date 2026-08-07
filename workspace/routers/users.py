from fastapi import APIRouter, HTTPException
from typing import List
from models import User

router = APIRouter(prefix="/users", tags=["users"])

# In-memory storage
users_db: dict[int, User] = {}
next_id = 1

@router.get("/", response_model=List[User])
async def get_users():
    return list(users_db.values())

@router.post("/", response_model=User)
async def create_user(user: User):
    global next_id
    user.id = next_id
    users_db[next_id] = user
    next_id += 1
    return user

@router.get("/{user_id}", response_model=User)
async def get_user(user_id: int):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    return users_db[user_id]

@router.put("/{user_id}", response_model=User)
async def update_user(user_id: int, updated_user: User):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    updated_user.id = user_id
    users_db[user_id] = updated_user
    return updated_user

@router.delete("/{user_id}")
async def delete_user(user_id: int):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    del users_db[user_id]
    return {"message": "User deleted successfully"}
