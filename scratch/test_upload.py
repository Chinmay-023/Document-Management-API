import httpx
import json

def test_upload():
    url = "http://127.0.0.1:8000/documents/upload"
    files = {
        "file": ("CardioTrack_v1.pdf", open("CardioTrack_v1.pdf", "rb"), "application/pdf")
    }
    data = {
        "name": "Mohan"
    }
    
    try:
        response = httpx.post(url, data=data, files=files, timeout=10.0)
        print("Status Code:", response.status_code)
        print("Response Body:")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print("Failed to run request:", e)

if __name__ == "__main__":
    test_upload()
