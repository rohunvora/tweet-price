"""
Cache Twitter profile avatars locally.
Downloads, resizes to 48x48, and stores in public/avatars.
"""
from typing import Optional
import httpx
import json
from PIL import Image
from io import BytesIO
from config import DATA_DIR, AVATARS_DIR, TARGET_USERNAME, X_BEARER_TOKEN, X_API_BASE

# Avatar size (small for fast canvas rendering)
AVATAR_SIZE = 48


def get_user_profile_image(username: str) -> Optional[str]:
    """Get profile image URL from Twitter API."""
    if not X_BEARER_TOKEN:
        print("No X_BEARER_TOKEN found")
        return None
    
    url = f"{X_API_BASE}/users/by/username/{username}"
    params = {"user.fields": "profile_image_url"}
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}
    
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url, params=params, headers=headers)
        
        if response.status_code != 200:
            print(f"Error fetching user: {response.status_code}")
            return None
        
        data = response.json()
        user = data.get("data", {})
        
        # Get profile image URL (replace _normal with _400x400 for higher res)
        img_url = user.get("profile_image_url", "")
        if img_url:
            img_url = img_url.replace("_normal", "_400x400")
        
        return img_url


def download_and_resize(url: str, output_path, size: int = AVATAR_SIZE) -> bool:
    """Download image, resize, and save."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            
            # Open and resize
            img = Image.open(BytesIO(response.content))
            img = img.convert("RGBA")
            img = img.resize((size, size), Image.Resampling.LANCZOS)
            
            # Save as PNG (supports transparency)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG", optimize=True)
            
            return True
    except Exception as e:
        print(f"Error downloading/resizing image: {e}")
        return False


def main():
    """Cache avatar for target user."""
    print("=" * 60)
    print("Avatar Caching")
    print("=" * 60)
    
    username = TARGET_USERNAME
    print(f"\nFetching profile image for @{username}...")
    
    img_url = get_user_profile_image(username)
    
    if not img_url:
        print("Could not get profile image URL")
        # Create a placeholder or use default
        return
    
    print(f"  URL: {img_url}")
    
    # Download and resize
    output_path = AVATARS_DIR / f"{username}.png"
    print(f"\nDownloading and resizing to {AVATAR_SIZE}x{AVATAR_SIZE}...")
    
    if download_and_resize(img_url, output_path):
        print(f"  Saved to: {output_path}")
        
        # Verify file size
        size_kb = output_path.stat().st_size / 1024
        print(f"  Size: {size_kb:.1f} KB")
    else:
        print("  Failed to cache avatar")


if __name__ == "__main__":
    main()

