# utils/api.py
import requests

SERVER_URL = "http://localhost:3000"  # 또는 EC2 IP

def get_user_list_by_machine(m_uid):
    res = requests.get(f"{SERVER_URL}/api/family/members?m_uid={m_uid}")
    return res.json()

def get_schedule_by_machine(m_uid):
    res = requests.get(f"{SERVER_URL}/dispenser/schedules/connect/{m_uid}")
    return res.json()
