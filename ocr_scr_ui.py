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
import tkinter.font as tkfont

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
        self.title("batchOCR by Consertis GmbH")
        self.geometry("1000x700")
        self.configure(bg="#f0f0f0")
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
        self.last_folder = os.path.expanduser("~")
        self.set_styles()
        self.create_widgets()

    def set_styles(self):
        """Setzt ein modernes Theme und angepasste Fonts für ttk-Widgets."""
        style = ttk.Style(self)
        style.theme_use("xpnative")
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=11)
        style.configure("TLabel", font=("Segoe UI", 11), background="#f0f0f0")
        style.configure("TButton", font=("Segoe UI", 11))
        style.configure("TEntry", font=("Segoe UI", 11))
        style.configure("TCheckbutton", font=("Segoe UI", 11), background="#f0f0f0")
        style.configure("Horizontal.TProgressbar", thickness=20)
        self.lb_font = tkfont.Font(family="Segoe UI", size=11)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="20 20 20 20")
        main_frame.pack(fill="both", expand=True)

        # Konfigurieren der Spalten: Die Spalte mit den Eingabefeldern erhält Gewicht
        main_frame.columnconfigure(1, weight=1)

        # Header
        header = ttk.Label(main_frame, text="batchOCR", font=("Segoe UI", 18, "bold"))
        header.grid(row=0, column=0, columnspan=3, pady=(0,20))

        # Quellordner-Bereich
        ttk.Label(main_frame, text="📂 Quellordner:").grid(row=1, column=0, sticky="w")
        # Listbox und Scrollbar in einem eigenen Frame
        source_frame = ttk.Frame(main_frame)
        source_frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        source_frame.columnconfigure(0, weight=1)
        self.source_listbox = tk.Listbox(source_frame, height=6, width=80, selectmode=tk.EXTENDED, font=self.lb_font)
        self.source_listbox.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(source_frame, orient="vertical", command=self.source_listbox.yview)
        self.source_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        # Button-Frame direkt unterhalb der Listbox – rechte Ausrichtung
        src_btn_frame = ttk.Frame(main_frame)
        src_btn_frame.grid(row=3, column=0, columnspan=3, sticky="e", pady=5)
        ttk.Button(src_btn_frame, text="➕ Hinzufügen", command=self.browse_source).pack(side="left", padx=5)
        ttk.Button(src_btn_frame, text="❌ Entfernen", command=self.remove_source_folder).pack(side="left", padx=5)

        # Zielordner-Bereich
        ttk.Label(main_frame, text="📁 Zielordner:").grid(row=4, column=0, sticky="w", pady=(20,0))
        target_frame = ttk.Frame(main_frame)
        target_frame.grid(row=5, column=0, columnspan=3, sticky="ew")
        target_frame.columnconfigure(0, weight=1)
        self.target_entry = ttk.Entry(target_frame, width=80)
        self.target_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(target_frame, text="📂 Durchsuchen", command=self.browse_target).grid(row=0, column=1, padx=5)

        # Optionen Dropdown
        self.options_menubutton = ttk.Menubutton(main_frame, text="🔧 Optionen", direction="below")
        self.options_menu = tk.Menu(self.options_menubutton, tearoff=0)
        self.options_menubutton["menu"] = self.options_menu

        self.options_menu.add_checkbutton(label="Unterordner integrieren", variable=self.include_subfolders)
        self.options_menu.add_checkbutton(label="Interne Parallelisierung aktivieren", variable=self.use_internal_parallelism)
        self.options_menu.add_checkbutton(label="Logfile erstellen", variable=self.logfile_enabled)

        self.options_menubutton.grid(row=6, column=0, columnspan=3, pady=5)


        # Fortschrittsanzeige
        self.progress_label = ttk.Label(main_frame, text="Noch nicht gestartet")
        self.progress_label.grid(row=8, column=0, columnspan=3, pady=20)
        self.progress_bar = ttk.Progressbar(main_frame, orient="horizontal", length=800, mode="determinate", style="Horizontal.TProgressbar")
        self.progress_bar.grid(row=9, column=0, columnspan=3, pady=10)

        # Steuerungsbuttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=10, column=0, columnspan=3, pady=20)
        self.start_button = ttk.Button(btn_frame, text="🚀 Start", command=self.start_processing)
        self.start_button.grid(row=0, column=0, padx=10)
        self.stop_button = ttk.Button(btn_frame, text="🛑 Stop", command=self.stop_processing, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=10)

    def browse_source(self):
        """Ermöglicht die Auswahl mehrerer Quellordner via tkfilebrowser."""
        folders = tkfilebrowser.askopendirnames(
            title="Wählen Sie Quellordner aus",
            initialdir=self.last_folder,
            parent=self
        )
        if folders:
            for folder in folders:
                if folder not in self.source_listbox.get(0, tk.END):
                    self.source_listbox.insert(tk.END, folder)
            self.last_folder = os.path.dirname(folders[-1])

    def remove_source_folder(self):
        """Entfernt die ausgewählten Ordner aus der Listbox."""
        selected = self.source_listbox.curselection()
        for index in selected[::-1]:
            self.source_listbox.delete(index)

    def browse_target(self):
        """Wählt einen Zielordner und speichert den zuletzt verwendeten Ordner."""
        folder = filedialog.askdirectory(title="Zielordner wählen", initialdir=self.last_folder)
        if folder:
            self.target_folder = folder
            self.target_entry.delete(0, tk.END)
            self.target_entry.insert(0, folder)
            self.last_folder = folder

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