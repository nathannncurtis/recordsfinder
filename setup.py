from cx_Freeze import setup, Executable
import sys

# Dependencies are automatically detected, but it might need fine-tuning.
build_exe_options = {
    "packages": ["os", "shutil", "ctypes", "sys", "concurrent.futures"],  # Added concurrent.futures
    "excludes": [],
    "include_files": ["records_finder_comline.ico"], #["ocr_finder_comline_no_folder.ico"] # Ensure the icon file is included
}

# Base setting for Windows
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # This will prevent the console window from appearing, change to None if you want the console

# Define the executables with the correct icon
executables = [
    #Executable("client_services_finder_comline.py", base=base, icon="ocr_finder_comline_no_folder.ico"),
    #Executable("cnr_finder_comline.py", base=base, icon="ocr_finder_comline_no_folder.ico"),
    #Executable("e-fax_finder_comline.py", base=base, icon="ocr_finder_comline_no_folder.ico"),
    #Executable("ocr_finder_comline.py", base=base, icon="ocr_finder_comline_no_folder.ico", target_name= "OCR Puller"), 
    #Executable("ocr_finder_comline_no_folder.py", base=base, icon="ocr_finder_comline_no_folder.ico", target_name="OCR Puller"), 
    #Executable("records_finder_comline.py", base=base, icon="records_finder_comline.ico", target_name="Records Finder"),
    Executable("temp_ocr_finder_comline_no_folder.py", base=base, icon="ocr_finder_comline_no_folder.ico", target_name="Temp OCR Puller"), 
    
]

# Setup function
setup(
    name="TEMP OCR Puller",
    version="1.0",
    description="Batch Record Finder Tools",
    options={"build_exe": build_exe_options},
    executables=executables
)
