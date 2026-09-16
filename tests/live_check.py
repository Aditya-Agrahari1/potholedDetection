import io
import requests
from PIL import Image

# 1. Health check
res = requests.get("http://127.0.0.1:8000/health")
print("Health check:", res.status_code, res.json())

# Create a test image
img = Image.new("RGB", (300, 300), color=(130, 130, 130))
buf = io.BytesIO()
img.save(buf, format="JPEG")
img_bytes = buf.getvalue()

# 2. Submit initial report at baseline coordinates
files1 = {"photo": ("road1.jpg", img_bytes, "image/jpeg")}
data1 = {"latitude": "37.7749", "longitude": "-122.4194", "timestamp": "2026-09-16T10:00:00Z"}
res1 = requests.post("http://127.0.0.1:8000/api/v1/reports", files=files1, data=data1)
print("POST Report 1 status:", res1.status_code)
rep1 = res1.json()
print("Report 1 ID:", rep1.get("report_id"), "Location ID:", rep1.get("location_id"), "Status:", rep1.get("status"))

# 3. Download PDF
pdf_url = f"http://127.0.0.1:8000{rep1['pdf_url']}"
pdf_res = requests.get(pdf_url)
print("Download PDF status:", pdf_res.status_code, "Content length:", len(pdf_res.content), "Starts with %PDF:", pdf_res.content.startswith(b"%PDF"))

# 4. Submit follow-up report within 15m radius
files2 = {"photo": ("road2.jpg", img_bytes, "image/jpeg")}
data2 = {"latitude": "37.77495", "longitude": "-122.4194", "timestamp": "2026-09-20T14:30:00Z"}
res2 = requests.post("http://127.0.0.1:8000/api/v1/reports", files=files2, data=data2)
print("POST Report 2 status:", res2.status_code)
rep2 = res2.json()
print("Report 2 ID:", rep2.get("report_id"), "Location ID:", rep2.get("location_id"), "Compared to:", rep2.get("compared_to_report_id"), "Status:", rep2.get("status"))

# 5. Fetch location timeline
loc_id = rep1["location_id"]
timeline_res = requests.get(f"http://127.0.0.1:8000/api/v1/locations/{loc_id}/reports")
print("Location timeline status:", timeline_res.status_code, "Total reports for location:", len(timeline_res.json()["reports"]))

print("\n--- ALL LIVE API CHECKS SUCCEEDED! ---")
