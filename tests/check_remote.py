import io
import requests
from PIL import Image

img = Image.new("RGB", (300, 300), color=(110, 110, 110))
buf = io.BytesIO()
img.save(buf, format="JPEG")
img_bytes = buf.getvalue()

files = {"photo": ("pothole_test.jpg", img_bytes, "image/jpeg")}
data = {
    "latitude": "37.7749",
    "longitude": "-122.4194",
    "timestamp": "2026-09-16T10:00:00Z",
}

print("Submitting report to live Render...")
res = requests.post(
    "https://potholeddetection.onrender.com/api/v1/reports",
    files=files,
    data=data,
    timeout=60,
)
print("Response status:", res.status_code)
print("Response body:", res.text)
