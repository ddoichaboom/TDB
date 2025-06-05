import requests
from utils.qr_handler import generate_qr_image

SERVER_URL = "http://your-server-address/api/dispenser"

def authenticate_kit_uid(uid: str):
    res = requests.post(f"{SERVER_URL}/verify-uid", json={"uid": uid})
    if res.status_code == 200:
        return res.json()  # user_id, connect 등 포함
    else:
        return None

def handle_unregistered_uid(uid: str):
    from datetime import datetime
    data = {
        "type": "register",
        "k_uid": uid,
        "createdAt": datetime.now().isoformat()
    }
    return generate_qr_image(data)
