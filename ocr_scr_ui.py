import os
import sys
import time
import signal
import multiprocessing
import ocrmypdf
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import tkfilebrowser

# Globaler Lock für Log-Schreibzugriffe
LOG_LOCK = None

def process_pdf(input_path, output_path, use_internal_parallelism, logfile_enabled, pdf_folder, log_file_path):
    """Führt OCR auf einer PDF aus und speichert das Ergebnis."""
    try:
        relative_path = os.path.relpath(input_path, pdf_folder)
        print(f"📄 Processing: {relative_path}")

        jobs_value = 4 if use_internal_parallelism else 1

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

        if logfile_enabled:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"{timestamp} - {relative_path}\n"
            if LOG_LOCK:
                with LOG_LOCK:
                    with open(log_file_path, "a", encoding="utf-8") as logfile:
                        logfile.write(log_entry)
            else:
                with open(log_file_path, "a", encoding="utf-8") as logfile:
                    logfile.write(log_entry)

    except Exception as e:
        print(f"❌ Error processing {input_path}: {e}")

    return os.path.basename(input_path)

def init_worker(lock):
    """Initializer für Worker-Prozesse: Setzt den globalen Lock und ignoriert SIGINT."""
    global LOG_LOCK
    LOG_LOCK = lock
    signal.signal(signal.SIGINT, signal.SIG_IGN)

class OcrApp(tk.Tk):
    def __init__(self):
        tk.Tk.__init__(self)
        self.title("OCR Application")
        self.geometry("700x400")
        self.source_folders = []
        self.target_folder = ""
        self.include_subfolders = tk.BooleanVar(value=True)
        self.use_internal_parallelism = tk.BooleanVar(value=True)
        self.logfile_enabled = tk.BooleanVar(value=True)
        self.total_files = 0
        self.processed_files = 0
        self.pool = None
        self.manager = None
        self.tasks = []
        self.processing = False
        self.start_time = None
        self.log_file_path = ""
        self.last_folder = os.path.expanduser("~")  # Startet im Home-Verzeichnis
        self.create_widgets()

    def create_widgets(self):
        frame = tk.Frame(self)
        frame.pack(pady=10)

        tk.Label(frame, text="Quellordner:").grid(row=0, column=0, sticky="w")

        # Listbox für Quellordner mit Scrollbar
        self.source_listbox = tk.Listbox(frame, height=4, width=50, selectmode=tk.EXTENDED)
        self.source_listbox.grid(row=0, column=1, padx=5)

        scrollbar = tk.Scrollbar(frame, orient="vertical")
        scrollbar.config(command=self.source_listbox.yview)
        self.source_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=2, sticky="ns")

        tk.Button(frame, text="Browse", command=self.browse_source).grid(row=0, column=3)
        tk.Button(frame, text="Ordner entfernen", command=self.remove_source_folder).grid(row=0, column=4)

        tk.Label(frame, text="Zielordner:").grid(row=1, column=0, sticky="w")
        self.target_entry = tk.Entry(frame, width=50)
        self.target_entry.grid(row=1, column=1, padx=5)
        tk.Button(frame, text="Browse", command=self.browse_target).grid(row=1, column=2)

        tk.Checkbutton(frame, text="Unterordner integrieren", variable=self.include_subfolders).grid(row=2, column=1, sticky="w", pady=5)
        tk.Checkbutton(frame, text="Interne Parallelisierung aktivieren", variable=self.use_internal_parallelism).grid(row=3, column=1, sticky="w", pady=5)
        tk.Checkbutton(frame, text="Logfile erstellen", variable=self.logfile_enabled).grid(row=4, column=1, sticky="w", pady=5)

        self.progress_label = tk.Label(self, text="Noch nicht gestartet")
        self.progress_label.pack(pady=10)
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", length=500, mode="determinate")
        self.progress_bar.pack(pady=5)

        button_frame = tk.Frame(self)
        button_frame.pack(pady=10)
        self.start_button = tk.Button(button_frame, text="Start", command=self.start_processing)
        self.start_button.grid(row=0, column=0, padx=5)
        self.stop_button = tk.Button(button_frame, text="Stop", command=self.stop_processing, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=5)

    def browse_source(self):
        """Ermöglicht die Auswahl mehrerer Quellordner und speichert den zuletzt ausgewählten Ordner."""
        folders = tkfilebrowser.askopendirnames(
            title="Wählen Sie Quellordner aus",
            initialdir=self.last_folder,
            parent=self
        )
        if folders:
            for folder in folders:
                if folder not in self.source_listbox.get(0, tk.END):
                    self.source_listbox.insert(tk.END, folder)
            self.last_folder = os.path.dirname(folders[-1])  # Speichert den Ordner des letzten ausgewählten Ordners

    def remove_source_folder(self):
        """Entfernt die ausgewählten Ordner aus der Listbox."""
        selected = self.source_listbox.curselection()
        for index in selected[::-1]:  # Rückwärts, um Indizes korrekt zu löschen
            self.source_listbox.delete(index)

    def browse_target(self):
        """Wählt einen Zielordner und speichert den letzten Ordner."""
        folder = filedialog.askdirectory(title="Zielordner wählen", initialdir=self.last_folder)
        if folder:
            self.target_folder = folder
            self.target_entry.delete(0, tk.END)
            self.target_entry.insert(0, folder)
            self.last_folder = folder  # Aktualisiert den letzten Ordner

    def get_pdf_files(self):
        """Sammelt alle PDF-Dateien aus den ausgewählten Quellordnern."""
        pdf_files = []
        self.source_folders = self.source_listbox.get(0, tk.END)
        
        for source_folder in self.source_folders:
            if not os.path.isdir(source_folder):
                continue
            if self.include_subfolders.get():
                for root, _, files in os.walk(source_folder):
                    for file in files:
                        if file.lower().endswith(".pdf"):
                            input_path = os.path.join(root, file)
                            rel = os.path.relpath(root, source_folder)
                            base_folder = os.path.basename(source_folder)
                            output_dir = os.path.join(self.target_folder, base_folder, rel)
                            os.makedirs(output_dir, exist_ok=True)
                            output_path = os.path.join(output_dir, file)
                            pdf_files.append((input_path, output_path, source_folder))
            else:
                for file in os.listdir(source_folder):
                    if file.lower().endswith(".pdf"):
                        input_path = os.path.join(source_folder, file)
                        base_folder = os.path.basename(source_folder)
                        output_dir = os.path.join(self.target_folder, base_folder)
                        os.makedirs(output_dir, exist_ok=True)
                        output_path = os.path.join(output_dir, file)
                        pdf_files.append((input_path, output_path, source_folder))
        return pdf_files

    def start_processing(self):
        """Startet die OCR-Verarbeitung für alle ausgewählten Ordner."""
        self.source_folders = self.source_listbox.get(0, tk.END)
        
        if not self.source_folders or not self.target_folder:
            messagebox.showerror("Fehler", "Bitte wählen Sie mindestens einen Quellordner und einen Zielordner aus.")
            return

        files = self.get_pdf_files()
        if not files:
            messagebox.showinfo("Info", "Keine PDF-Dateien gefunden.")
            return

        self.start_time = time.time()
        self.total_files = len(files)
        self.processed_files = 0
        self.progress_bar["maximum"] = self.total_files
        self.progress_bar["value"] = 0

        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.processing = True

        self.log_file_path = os.path.join(self.target_folder, "ocr_log.txt")
        self.manager = multiprocessing.Manager()
        log_lock = self.manager.Lock()

        self.pool = multiprocessing.Pool(
            processes=os.cpu_count(),
            initializer=init_worker,
            initargs=(log_lock,)
        )

        self.tasks = []
        for args in files:
            res = self.pool.apply_async(
                process_pdf,
                args=(args[0], args[1], self.use_internal_parallelism.get(),
                     self.logfile_enabled.get(), args[2], self.log_file_path),
                callback=self.task_callback
            )
            self.tasks.append(res)

        self.update_progress()

    def stop_processing(self):
        """Stoppt die Verarbeitung."""
        if self.pool:
            self.pool.terminate()
            self.pool.join()

        self.processing = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        messagebox.showinfo("Gestoppt", "Die Verarbeitung wurde gestoppt.")

    def update_progress(self):
        """Aktualisiert die Fortschrittsanzeige."""
        elapsed_time = time.time() - self.start_time
        percent = (self.processed_files / self.total_files) * 100 if self.total_files > 0 else 0
        self.progress_label.config(
            text=f"{self.processed_files}/{self.total_files} Dateien verarbeitet ({percent:.1f}%) - {elapsed_time:.1f}s vergangen"
        )

        if self.processed_files < self.total_files:
            self.after(1000, self.update_progress)
        else:
            self.pool.close()
            self.pool.join()
            self.processing = False
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            messagebox.showinfo("Fertig", "Alle PDFs wurden verarbeitet.")

    def task_callback(self, result):
        """Callback für abgeschlossene Aufgaben."""
        self.processed_files += 1
        self.progress_bar["value"] = self.processed_files

if __name__ == "__main__":
    app = OcrApp()
    app.mainloop()