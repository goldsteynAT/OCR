import os
import time
import signal
import ocrmypdf

class OCRProcessor:
    def __init__(self, use_internal_parallelism=True, logfile_handler=None, pdf_folder=""):
        self.use_internal_parallelism = use_internal_parallelism
        self.logfile_handler = logfile_handler
        self.pdf_folder = pdf_folder

    def process_pdf(self, input_path, output_path):
        try:
            relative_path = os.path.relpath(input_path, self.pdf_folder)
            print(f"📄 Processing: {relative_path}")

            jobs_value = 4 if self.use_internal_parallelism else 1

            ocrmypdf.ocr(
                input_path, output_path,
                deskew=True,
                optimize=1,
                force_ocr=True,
                oversample=600,
                language="deu+eng",
                jobs=jobs_value
            )
            print(f"✅ Finished: {relative_path}")

            if self.logfile_handler:
                self.logfile_handler.write_log(input_path, self.pdf_folder)

        except Exception as e:
            print(f"❌ Error processing {input_path}: {e}")

        return os.path.basename(input_path)

    @staticmethod
    def init_worker(lock):
        # Initialisierer für Worker-Prozesse: Setzt den globalen Lock und ignoriert SIGINT.
        global LOG_LOCK
        LOG_LOCK = lock
        signal.signal(signal.SIGINT, signal.SIG_IGN)
