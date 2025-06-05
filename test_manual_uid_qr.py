import qrcode
import tkinter as tk
from PIL import Image, ImageTk
from datetime import datetime
import json

def generate_qr(uid: str):
    payload = {
        "type": "link",
        "uid": uid,
        "createdAt": datetime.now().isoformat()
    }

    # QR 생성
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(json.dumps(payload))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    return img, payload

def show_qr_image(img):
    window = tk.Tk()
    window.title("Test QR Code")

    # PIL 이미지를 Tkinter 이미지로 변환
    img = img.resize((300, 300))
    tk_img = ImageTk.PhotoImage(img)

    label = tk.Label(window, image=tk_img)
    label.pack(padx=20, pady=20)

    window.mainloop()

def main():
    print("=== 수동 UID QR 코드 생성 테스트 ===")
    uid = input("UID 값을 입력하세요 (예: F3 6B 8F 0F): ").strip()

    img, payload = generate_qr(uid)
    print(f"🔍 생성된 JSON 데이터:\n{json.dumps(payload, indent=2)}")

    show_qr_image(img)

if __name__ == "__main__":
    main()
