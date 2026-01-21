import requests
import json
import sqlite3
import os

# Configuration
BASE_URL = "http://localhost:5000"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "keyhub.db")


def get_admin_token():
    # Login to get token
    url = f"{BASE_URL}/api/login"
    data = {"username": "admin", "password": "admin123"}
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return response.json().get("token")
        else:
            print(f"Login failed: {response.text}")
            return None
    except requests.exceptions.ConnectionError:
        print("Connection failed. Is the server running?")
        return None


def test_custom_key_creation(token):
    print("\n--- Testing Custom Key Creation ---")
    headers = {"X-Admin-Token": token, "Content-Type": "application/json"}

    # Get project ID (Default Project)
    proj_resp = requests.get(f"{BASE_URL}/api/projects", headers=headers)
    projects = proj_resp.json()
    if not projects:
        print("No projects found.")
        return
    project_id = projects[0]["id"]

    # 1. Create a unique custom key
    custom_key = "TEST-KEY-1001"
    url = f"{BASE_URL}/api/keys"
    data = {
        "project_id": project_id,
        "remarks": "Automated Test Key",
        "custom_key": custom_key,
    }

    # Clean up first if exists
    requests.delete(f"{BASE_URL}/api/keys/{custom_key}", headers=headers)

    resp = requests.post(url, headers=headers, json=data)
    print(f"Create '{custom_key}': Status {resp.status_code}")
    if resp.status_code == 200:
        print(">> Success: Custom key created.")
        key_data = resp.json().get("key")
        if key_data != custom_key:
            print(
                f">> FAIL: Returned key '{key_data}' does not match requested '{custom_key}'"
            )
    else:
        print(f">> FAIL: {resp.text}")

    # 2. Try to create duplicate
    print("\n--- Testing Duplicate Key ---")
    resp = requests.post(url, headers=headers, json=data)
    print(f"Create Duplicate '{custom_key}': Status {resp.status_code}")
    if resp.status_code == 400 and "自定义密钥已存在" in resp.text:
        print(">> Success: Correctly rejected duplicate.")
    else:
        print(
            f">> FAIL: Should return 400 with specific error. Got {resp.status_code} - {resp.text}"
        )

    # Clean up
    requests.delete(f"{BASE_URL}/api/keys/{custom_key}", headers=headers)
    print("\nTest Complete.")


if __name__ == "__main__":
    token = get_admin_token()
    if token:
        test_custom_key_creation(token)
