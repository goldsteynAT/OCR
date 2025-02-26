import os
import time

class LogHandler:
    def __init__(self, log_file_path, enabled=True):
        self.log_file_path = log_file_path
        self.enabled = enabled
        self.lock = None
    
    def set_lock(self, lock):
        self.lock = lock

    def write_log(self, input_path, pdf_folder):
        if not self.enabled:
            return
        relative_path = os.path.relpath(input_path, pdf_folder)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} - {relative_path}\n"
        if self.lock:
            with self.lock:
                with open(self.log_file_path, "a", encoding="utf-8") as logfile:
                    logfile.write(log_entry)
        else:
            with open(self.log_file_path, "a", encoding="utf-8") as logfile:
                logfile.write(log_entry)
