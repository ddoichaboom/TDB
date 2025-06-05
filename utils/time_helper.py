from datetime import datetime

def get_current_time_of_day():
    hour = datetime.now().hour
    if 5 <= hour < 11:
        return "morning"
    elif 11 <= hour < 17:
        return "afternoon"
    elif 17<= hour < 24:
        return "evening"
    else:
        return "inappropriate"
    
def get_required_time_slots(current_time):
    if current_time == "morning":
        return ["morning", "afternoon", "evening"]
    elif current_time == "afternoon":
        return ["afternoon", "evening"]
    elif current_time == "evening":
        return ["evening"]
    elif current_time == "inappropriate":
        print("현재 시간대는 약 복용/배출 대상이 아닙니다.")
        return []
    else:
        return []

