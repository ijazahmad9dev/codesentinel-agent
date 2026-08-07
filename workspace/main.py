from fastapi import FastAPI
from routers.users import router as users_router

app = FastAPI(title="User Management API")

# Include routers
app.include_router(users_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the User Management API"}
