def extract_qr_info(response: dict):
    if response.get("status") == "unregistered":
        return response.get("qr_url")
    return None