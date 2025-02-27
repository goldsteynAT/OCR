class FileManager:
    def __init__(self, source_folders, target_folder, include_subfolders=True):
        self.source_folders = source_folders
        self.target_folder = target_folder  # Will be None when "Zielordner = Quellordner" is active
        self.include_subfolders = include_subfolders

    def get_pdf_files(self):
        pdf_files = []
        for source_folder in self.source_folders:
            if not os.path.isdir(source_folder):
                continue
            if self.include_subfolders:
                for root, _, files in os.walk(source_folder):
                    for file in files:
                        if file.lower().endswith(".pdf"):
                            input_path = os.path.join(root, file)
                            rel = os.path.relpath(root, source_folder)
                            base_folder = os.path.basename(source_folder)
                            
                            if self.target_folder is None:
                                # If target folder is same as source folder, we need to create a temporary output path
                                # We'll use a temporary filename by adding "_ocr" before the extension
                                file_name, file_ext = os.path.splitext(file)
                                temp_file = f"{file_name}_ocr{file_ext}"
                                output_dir = root
                                output_path = os.path.join(output_dir, temp_file)
                            else:
                                output_dir = os.path.join(self.target_folder, base_folder, rel)
                                os.makedirs(output_dir, exist_ok=True)
                                output_path = os.path.join(output_dir, file)
                            
                            pdf_files.append((input_path, output_path, source_folder))
            else:
                for file in os.listdir(source_folder):
                    if file.lower().endswith(".pdf"):
                        input_path = os.path.join(source_folder, file)
                        base_folder = os.path.basename(source_folder)
                        
                        if self.target_folder is None:
                            # If target folder is same as source folder, create a temporary filename
                            file_name, file_ext = os.path.splitext(file)
                            temp_file = f"{file_name}_ocr{file_ext}"
                            output_dir = source_folder
                            output_path = os.path.join(output_dir, temp_file)
                        else:
                            output_dir = os.path.join(self.target_folder, base_folder)
                            os.makedirs(output_dir, exist_ok=True)
                            output_path = os.path.join(output_dir, file)
                            
                        pdf_files.append((input_path, output_path, source_folder))
        return pdf_files