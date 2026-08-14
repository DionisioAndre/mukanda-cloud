import requests

# Test login through frontend proxy
url = "http://localhost:5173/api/auth/token/"
data = {
    "email": "admin@mukanda.com",
    "password": "admin123"
}

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        print("\n✅ Proxy integration successful!")
        print(f"Access Token: {response.json().get('access', 'N/A')[:50]}...")
    else:
        print("\n❌ Proxy integration failed")
except Exception as e:
    print(f"Error: {e}")
