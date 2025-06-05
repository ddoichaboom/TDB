# utils/qr_display.py
import qrcode
import tkinter as tk
from PIL import Image, ImageTk

def show_qr_code(data: dict):
    qr = qrcode.make(data)
    qr.save("assets/qr_temp.png")

    window = tk.Tk()
    window.title("기기 등록 QR")
    window.geometry("400x450")

    img = Image.open("assets/qr_temp.png")
    img = img.resize((350, 350))
    tk_img = ImageTk.PhotoImage(img)

    label = tk.Label(window, text="기기를 등록해주세요", font=("Arial", 14))
    label.pack(pady=10)

    qr_label = tk.Label(window, image=tk_img)
    qr_label.pack()

    window.mainloop()
