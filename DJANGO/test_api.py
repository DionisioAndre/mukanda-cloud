import requests

# Test login endpoint
url = "http://127.0.0.1:8000/api/auth/token/"
data = {
    "email": "admin@mukanda.com",
    "password": "admin123"
}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        print("\n✅ Login successful!")
        print(f"Access Token: {response.json().get('access', 'N/A')[:50]}...")
    else:
        print("\n❌ Login failed")
except Exception as e:
    print(f"Error: {e}")
