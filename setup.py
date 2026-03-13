from cx_Freeze import setup, Executable
import sys

with open("version.txt", "r") as _vf:
    APP_VERSION = _vf.read().strip()

build_exe_options = {
    "packages": [
        "os", "sys", "shutil", "ctypes", "sqlite3", "json",
        "threading", "concurrent.futures", "subprocess",
        "time", "logging", "tempfile", "traceback",
        "urllib.request", "urllib.error",
        "PyQt5.QtWidgets", "PyQt5.QtCore", "PyQt5.QtGui",
    ],
    "excludes": [
        "tkinter", "matplotlib", "pandas", "scipy",
        "numpy", "PIL",
    ],
    "include_files": [
        "records_finder_comline.ico",
        "version.txt",
    ],
    "optimize": 2,
    "zip_include_packages": ["*"],
    "zip_exclude_packages": [],
}

# cx_Freeze 7+ renamed "Win32GUI" to "gui"
import cx_Freeze
_cx_major = int(cx_Freeze.__version__.split(".")[0]) if hasattr(cx_Freeze, "__version__") else 6
base_gui = ("gui" if _cx_major >= 7 else "Win32GUI") if sys.platform == "win32" else None

executables = [
    Executable("main.py", base=base_gui, icon="records_finder_comline.ico", target_name="Records Finder"),
    Executable("tray.py", base=base_gui, icon="records_finder_comline.ico", target_name="Records Finder Tray"),
    Executable("update_checker.py", base=base_gui, icon="records_finder_comline.ico"),
    Executable("reg.py", base=None, icon="records_finder_comline.ico"),
    Executable("unreg.py", base=None, icon="records_finder_comline.ico"),
]

setup(
    name="Records Finder",
    version=APP_VERSION,
    description="Records Finder with Database-Backed Search and System Tray Configuration",
    options={"build_exe": build_exe_options},
    executables=executables,
)
