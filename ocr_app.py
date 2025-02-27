import os
import time
import multiprocessing
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont
from PIL import Image, ImageTk
import tkfilebrowser

from loghandler import LogHandler
from ocr_processor import OCRProcessor
from filemanager import FileManager

class OcrApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("batchOCR by Consertis GmbH")
        #self.icon_img = ImageTk.PhotoImage(Image.open(r"C:\Pfad\zur\deiner\Logo.png"))
        #self.iconphoto(False, self.icon_img)
        self.geometry("1000x700")
        self.configure(bg="#f0f0f0")
        
        self.source_folders = []
        self.source_files = []
        self.target_folder = ""
        self.include_subfolders = tk.BooleanVar(value=True)
        self.use_internal_parallelism = tk.BooleanVar(value=True)
        self.logfile_enabled = tk.BooleanVar(value=True)
        self.mode = tk.StringVar(value="folder_mode")  # Default to folder mode
        
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
        style = ttk.Style(self)
        style.theme_use("xpnative")
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=11)
        style.configure("TLabel", font=("Segoe UI", 11), background="#f0f0f0")
        style.configure("TButton", font=("Segoe UI", 11))
        style.configure("TEntry", font=("Segoe UI", 11))
        style.configure("TCheckbutton", font=("Segoe UI", 11), background="#f0f0f0")
        style.configure("TRadiobutton", font=("Segoe UI", 11), background="#f0f0f0")
        style.configure("Horizontal.TProgressbar", thickness=20)
        self.lb_font = tkfont.Font(family="Segoe UI", size=11)

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="20 20 20 20")
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(1, weight=1)

        header = ttk.Label(main_frame, text="batchOCR", font=("Segoe UI", 18, "bold"))
        header.grid(row=0, column=0, columnspan=3, pady=(0,20))

        # Mode selection (Folder or Files)
        mode_frame = ttk.LabelFrame(main_frame, text="Verarbeitungsmodus", padding=10)
        mode_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 15))

        ttk.Radiobutton(
            mode_frame, 
            text="Ordner verarbeiten", 
            variable=self.mode, 
            value="folder_mode",
            command=self.toggle_mode
        ).pack(side="left", padx=20)
        
        ttk.Radiobutton(
            mode_frame, 
            text="Einzelne PDF-Dateien verarbeiten", 
            variable=self.mode, 
            value="file_mode",
            command=self.toggle_mode
        ).pack(side="left", padx=20)

        # Source container frame (will contain both folder and file frames)
        self.source_container = ttk.Frame(main_frame)
        self.source_container.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.source_container.columnconfigure(0, weight=1)
        
        # Folder Selection Frame
        self.folder_frame = ttk.Frame(self.source_container)
        self.folder_frame.grid(row=0, column=0, sticky="ew")
        self.folder_frame.columnconfigure(0, weight=1)
        
        ttk.Label(self.folder_frame, text="📂 Quellordner:").grid(row=0, column=0, sticky="w")
        source_frame = ttk.Frame(self.folder_frame)
        source_frame.grid(row=1, column=0, sticky="ew")
        source_frame.columnconfigure(0, weight=1)
        
        self.source_listbox = tk.Listbox(source_frame, height=6, width=80, selectmode=tk.EXTENDED, font=self.lb_font)
        self.source_listbox.grid(row=0, column=0, sticky="ew")
        scrollbar = ttk.Scrollbar(source_frame, orient="vertical", command=self.source_listbox.yview)
        self.source_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        src_btn_frame = ttk.Frame(self.folder_frame)
        src_btn_frame.grid(row=2, column=0, sticky="e", pady=5)
        ttk.Button(src_btn_frame, text="➕ Hinzufügen", command=self.browse_source).pack(side="left", padx=5)
        ttk.Button(src_btn_frame, text="❌ Entfernen", command=self.remove_source_folder).pack(side="left", padx=5)

        # File Selection Frame (initially hidden)
        self.file_frame = ttk.Frame(self.source_container)
        self.file_frame.columnconfigure(0, weight=1)
        
        ttk.Label(self.file_frame, text="📄 PDF-Dateien:").grid(row=0, column=0, sticky="w")
        file_source_frame = ttk.Frame(self.file_frame)
        file_source_frame.grid(row=1, column=0, sticky="ew")
        file_source_frame.columnconfigure(0, weight=1)
        
        self.file_listbox = tk.Listbox(file_source_frame, height=6, width=80, selectmode=tk.EXTENDED, font=self.lb_font)
        self.file_listbox.grid(row=0, column=0, sticky="ew")
        file_scrollbar = ttk.Scrollbar(file_source_frame, orient="vertical", command=self.file_listbox.yview)
        self.file_listbox.config(yscrollcommand=file_scrollbar.set)
        file_scrollbar.grid(row=0, column=1, sticky="ns")
        
        file_btn_frame = ttk.Frame(self.file_frame)
        file_btn_frame.grid(row=2, column=0, sticky="e", pady=5)
        ttk.Button(file_btn_frame, text="➕ Dateien hinzufügen", command=self.browse_files).pack(side="left", padx=5)
        ttk.Button(file_btn_frame, text="❌ Entfernen", command=self.remove_source_files).pack(side="left", padx=5)

        # Zielordner-Bereich
        ttk.Label(main_frame, text="🏁 Zielordner:").grid(row=4, column=0, sticky="w", pady=(20,0))
        target_frame = ttk.Frame(main_frame)
        target_frame.grid(row=5, column=0, columnspan=3, sticky="ew")
        target_frame.columnconfigure(0, weight=1)
        self.target_entry = ttk.Entry(target_frame, width=80)
        self.target_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(target_frame, text="📂 Durchsuchen", command=self.browse_target).grid(row=0, column=1, padx=5)

        # Optionen
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
        
        # Initial mode setup
        self.toggle_mode()

    def toggle_mode(self):
        if self.mode.get() == "folder_mode":
            self.file_frame.grid_forget()
            self.folder_frame.grid(row=0, column=0, sticky="ew")
            self.options_menu.entryconfig(0, state=tk.NORMAL)  # Enable "Unterordner integrieren" option
        else:  # file_mode
            self.folder_frame.grid_forget()
            self.file_frame.grid(row=0, column=0, sticky="ew")
            self.options_menu.entryconfig(0, state=tk.DISABLED)  # Disable "Unterordner integrieren" option

    def browse_source(self):
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

    def browse_files(self):
        files = filedialog.askopenfilenames(
            title="Wählen Sie PDF-Dateien aus",
            initialdir=self.last_folder,
            filetypes=[("PDF-Dateien", "*.pdf")],
            parent=self
        )
        if files:
            for file in files:
                if file not in self.file_listbox.get(0, tk.END):
                    self.file_listbox.insert(tk.END, file)
            self.last_folder = os.path.dirname(files[-1])

    def remove_source_folder(self):
        selected = self.source_listbox.curselection()
        for index in selected[::-1]:
            self.source_listbox.delete(index)

    def remove_source_files(self):
        selected = self.file_listbox.curselection()
        for index in selected[::-1]:
            self.file_listbox.delete(index)

    def browse_target(self):
        folder = filedialog.askdirectory(title="Zielordner wählen", initialdir=self.last_folder)
        if folder:
            self.target_folder = folder
            self.target_entry.delete(0, tk.END)
            self.target_entry.insert(0, folder)
            self.last_folder = folder

    def get_pdf_files(self):
        if self.mode.get() == "folder_mode":
            self.source_folders = self.source_listbox.get(0, tk.END)
            fm = FileManager(self.source_folders, self.target_folder, self.include_subfolders.get())
            return fm.get_pdf_files()
        else:  # file_mode
            pdf_files = []
            self.source_files = self.file_listbox.get(0, tk.END)
            
            for input_path in self.source_files:
                if not input_path.lower().endswith(".pdf"):
                    continue
                
                filename = os.path.basename(input_path)
                output_dir = self.target_folder
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, filename)
                
                # Using the directory of the file as pdf_folder for logging
                file_dir = os.path.dirname(input_path)
                pdf_files.append((input_path, output_path, file_dir))
                
            return pdf_files

    def start_processing(self):
        if self.mode.get() == "folder_mode":
            self.source_folders = self.source_listbox.get(0, tk.END)
            if not self.source_folders:
                messagebox.showerror("Fehler", "Bitte wählen Sie mindestens einen Quellordner aus.")
                return
        else:  # file_mode
            self.source_files = self.file_listbox.get(0, tk.END)
            if not self.source_files:
                messagebox.showerror("Fehler", "Bitte wählen Sie mindestens eine PDF-Datei aus.")
                return
        
        if not self.target_folder:
            messagebox.showerror("Fehler", "Bitte wählen Sie einen Zielordner aus.")
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

        log_handler = LogHandler(self.log_file_path, self.logfile_enabled.get())
        log_handler.set_lock(log_lock)

        self.pool = multiprocessing.Pool(
            processes=os.cpu_count(),
            initializer=OCRProcessor.init_worker,
            initargs=(log_lock,)
        )

        self.tasks = []
        for args in files:
            processor = OCRProcessor(self.use_internal_parallelism.get(), log_handler, args[2])
            res = self.pool.apply_async(
                processor.process_pdf,
                args=(args[0], args[1]),
                callback=self.task_callback
            )
            self.tasks.append(res)

        self.update_progress()

    def stop_processing(self):
        if self.pool:
            self.pool.terminate()
            self.pool.join()

        self.processing = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        messagebox.showinfo("Gestoppt", "Die Verarbeitung wurde gestoppt.")

    def update_progress(self):
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
            self.display_logfile()

    def task_callback(self, result):
        self.processed_files += 1
        self.progress_bar["value"] = self.processed_files

    def display_logfile(self):
        if not os.path.exists(self.log_file_path):
            messagebox.showinfo("Logfile", "Kein Logfile gefunden.")
            return

        log_win = tk.Toplevel(self)
        log_win.title("OCR Logfile")
        log_win.geometry("800x600")

        columns = ("datum", "uhrzeit", "dateipfad", "dateiname")
        tree = ttk.Treeview(log_win, columns=columns, show="headings")
        tree.heading("datum", text="Datum")
        tree.heading("uhrzeit", text="Uhrzeit")
        tree.heading("dateipfad", text="Dateipfad")
        tree.heading("dateiname", text="Dateiname")
        tree.column("datum", anchor="w", width=120)
        tree.column("uhrzeit", anchor="w", width=100)
        tree.column("dateipfad", anchor="w", width=400)
        tree.column("dateiname", anchor="w", width=150)
        tree.pack(fill="both", expand=True)

        with open(self.log_file_path, "r", encoding="utf-8") as logfile:
            for line in logfile:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" - ", 1)
                if len(parts) == 2:
                    timestamp = parts[0].strip()
                    relpath = parts[1].strip()
                    if " " in timestamp:
                        datum, uhrzeit = timestamp.split(" ", 1)
                    else:
                        datum, uhrzeit = timestamp, ""
                    filename = os.path.basename(relpath)
                    tree.insert("", tk.END, values=(datum, uhrzeit, relpath, filename))
                else:
                    tree.insert("", tk.END, values=(line, "", "", ""))

        scrollbar = ttk.Scrollbar(log_win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

if __name__ == "__main__":
    app = OcrApp()
    app.mainloop()