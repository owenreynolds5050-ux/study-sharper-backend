import requests
import time
import json

# Replace with your actual token
TOKEN = "eyJhbGciOiJIUzI1NiIsImtpZCI6IldSeGpJZ3c4cjE3TU4rU1…HNlfQ.2_BGnjpdhOnL_r4ZQwHM4L1--MnytKAk4LluNLSI0-A"  # Paste your token here
headers = {"Authorization": f"Bearer {TOKEN}"}

# Upload the file
print("📤 Uploading test_document.txt...")
with open("test_document.txt", "rb") as f:
    files = {"file": f}
    response = requests.post(
        "http://localhost:8000/api/files/upload",
        headers=headers,
        files=files
    )

print(f"Status code: {response.status_code}")
result = response.json()
print(f"Upload response:\n{json.dumps(result, indent=2)}")

if "file_id" not in result:
    print("❌ Upload failed!")
    exit(1)

file_id = result["file_id"]

# Poll status
print(f"\n📊 Polling status for file_id={file_id}...")
for i in range(20):
    response = requests.get(
        f"http://localhost:8000/api/files/status/{file_id}",
        headers=headers
    )
    data = response.json()
    print(f"[{i}] Status: {data['status']}")
    
    if data['status'] == 'completed':
        print(f"\n✅ SUCCESS!")
        print(f"   Chunks: {data.get('chunk_count')}")
        print(f"   Title: {data.get('title')}")
        print(f"   Text length: {len(data.get('extracted_text', '')) if data.get('extracted_text') else 0} chars")
        break
    elif data['status'] == 'failed':
        print(f"\n❌ FAILED: {data.get('error_message')}")
        break
    
    time.sleep(1)