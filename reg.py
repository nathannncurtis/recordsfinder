import os
import subprocess
import winreg


def create_send_to_shortcut():
    exe_path = os.path.join(os.getenv('APPDATA'), 'Records Finder', 'Records Finder.exe')
    sendto_dir = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'SendTo')
    shortcut_path = os.path.join(sendto_dir, 'Find Records.lnk')

    ps_script = (
        '$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{shortcut_path}"); '
        f'$s.TargetPath = "{exe_path}"; '
        f'$s.IconLocation = "{exe_path},0"; '
        '$s.Save()'
    )

    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"Send To shortcut created: {shortcut_path}")
        else:
            print(f"Failed to create Send To shortcut: {result.stderr.strip()}")
    except Exception as e:
        print(f"Error creating Send To shortcut: {e}")


def add_tray_startup():
    tray_path = os.path.join(os.getenv('APPDATA'), 'Records Finder', 'Records Finder Tray.exe')
    key_path = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, 'RecordsFinderTray', 0, winreg.REG_SZ, f'"{tray_path}"')
        print(f"Tray startup entry added: {tray_path}")
    except Exception as e:
        print(f"Error adding tray startup entry: {e}")


def add_scheduled_update_check():
    checker_path = os.path.join(os.getenv('APPDATA'), 'Records Finder', 'update_checker.exe')
    task_name = "RecordsFinderUpdateCheck"

    try:
        result = subprocess.run(
            [
                "schtasks", "/create",
                "/tn", task_name,
                "/tr", f'"{checker_path}"',
                "/sc", "daily",
                "/st", "01:00",
                "/f",
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"Scheduled task '{task_name}' created successfully (daily at 1:00 AM).")
        else:
            print(f"Failed to create scheduled task: {result.stderr.strip()}")
    except Exception as e:
        print(f"Error creating scheduled task: {e}")


if __name__ == "__main__":
    create_send_to_shortcut()
    add_tray_startup()
    add_scheduled_update_check()
