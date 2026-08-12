import requests
import time

# Wait for server to start
time.sleep(2)

BASE_URL = "http://localhost:8000"

def test_api():
    print("Testing Blog API...")
    
    # Test root endpoint
    response = requests.get(f"{BASE_URL}/")
    print(f"Root endpoint: {response.json()}")
    
    # Test creating a post (requires auth)
    token_response = requests.post(
        f"{BASE_URL}/token",
        data={"username": "admin", "password": "admin123"}
    )
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create a post
    post_data = {
        "title": "Test Post",
        "content": "This is test content",
        "author": "John Doe"
    }
    response = requests.post(f"{BASE_URL}/posts", json=post_data, headers=headers)
    print(f"Create post: {response.json()}")
    
    # Get all posts
    response = requests.get(f"{BASE_URL}/posts")
    print(f"Get all posts: {response.json()}")
    
    # Test creating a comment (requires auth)
    post_id = 1
    comment_data = {
        "content": "Great post!",
        "author": "Jane Doe",
        "post_id": post_id
    }
    response = requests.post(f"{BASE_URL}/posts/{post_id}/comments", json=comment_data, headers=headers)
    print(f"Create comment: {response.json()}")
    
    # Get comments for a post
    response = requests.get(f"{BASE_URL}/posts/{post_id}/comments")
    print(f"Get comments: {response.json()}")
    
    print("\nAll tests passed!")

if __name__ == "__main__":
    test_api()