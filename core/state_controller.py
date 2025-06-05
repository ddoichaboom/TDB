class StateController:
    def __init__(self):
        self.current_uid = None

    def is_processing(self, uid: str) -> bool:
        return uid == self.current_uid
    
    def set_processing(self, uid: str):
        self.current_uid = uid

    def clear(self):
        self.current_uid = None