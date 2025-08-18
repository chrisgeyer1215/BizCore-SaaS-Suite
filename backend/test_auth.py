import requests
import json

BASE_URL = "http://localhost:8000/api/auth"

def test_registration():
    print("Testing user registration...")
    url = f"{BASE_URL}/register/"
    data = {
        "email": "newuser@example.com",  # Use a different email
        "password": "securepassword123",
        "first_name": "New",
        "last_name": "User"
    }
    
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.json()

def test_login(email, password):
    print(f"\nTesting login with {email}...")
    url = f"{BASE_URL}/login/"
    data = {"email": email, "password": password}
    
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    
    if 'tokens' in result:
        return result['tokens']['access']
    return None

def test_profile(access_token):
    print("\nTesting profile...")
    url = f"{BASE_URL}/profile/"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_tenant_creation(access_token):
    print("\nTesting tenant creation...")
    url = f"{BASE_URL}/create-tenant/"  # Fixed URL
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {
        "name": "Test Company",
        "description": "A test company",
        "company_name": "Test Company LLC"
    }
    
    response = requests.post(url, json=data, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_user_tenants(access_token):
    print("\nTesting user tenants...")
    url = f"{BASE_URL}/tenants/"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def test_invite_user(access_token):
    print("\nTesting invite user...")
    url = f"{BASE_URL}/invite-user/"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {
        "email": "invited@example.com",
        "role": "employee",
        "message": "Welcome to our team!"
    }
    
    response = requests.post(url, json=data, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

def run_tests():
    print("=== Django Auth API Tests ===\n")
    
    # Register new user
    reg_result = test_registration()
    
    # Try to login with the new user
    if 'tokens' in reg_result:
        access_token = reg_result['tokens']['access']
        email = reg_result['user']['email']
        print(f"Got access token from registration: {access_token[:50]}...")
        
        # Test authenticated endpoints
        test_profile(access_token)
        test_tenant_creation(access_token)
        test_user_tenants(access_token)
        test_invite_user(access_token)
    else:
        print("Registration failed, trying to login with existing user...")
        
        # Try different credentials for existing user
        access_token = test_login("test@example.com", "password123")
        if not access_token:
            print("Login failed, let's check what users exist in the database")

if __name__ == "__main__":
    run_tests()
