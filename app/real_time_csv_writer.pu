import csv
import threading
from thread_safe_logger import ThreadSafeLogger

class RealTimeCSVWriter:
    def __init__(self, filename, fieldnames):
        self._lock = threading.Lock()
        self._filename = filename
        self._fieldnames = fieldnames

        with open(self._filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    def write_row(self, row):
        with self._lock:
            try:
                with open(self._filename, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self._fieldnames)
                    writer.writerow(row)
            except Exception as e:
                ThreadSafeLogger.log('error', f"Error writing to CSV: {e}")
