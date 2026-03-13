import os
import subprocess
import winreg


def remove_send_to_shortcut():
    shortcut_path = os.path.join(
        os.getenv('APPDATA'), 'Microsoft', 'Windows', 'SendTo', 'Find Records.lnk'
    )
    try:
        os.remove(shortcut_path)
        print("Send To shortcut removed.")
    except FileNotFoundError:
        print("Send To shortcut not found (already removed).")
    except Exception as e:
        print(f"Error removing Send To shortcut: {e}")


def remove_tray_startup():
    key_path = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, 'RecordsFinderTray')
        print("Tray startup entry removed.")
    except FileNotFoundError:
        print("Tray startup entry not found (already removed).")
    except Exception as e:
        print(f"Error removing tray startup entry: {e}")


def remove_scheduled_update_check():
    task_name = "RecordsFinderUpdateCheck"
    try:
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", task_name, "/f"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"Scheduled task '{task_name}' removed successfully.")
        else:
            if "cannot find" in result.stderr.lower() or "does not exist" in result.stderr.lower():
                print(f"Scheduled task '{task_name}' not found (already removed).")
            else:
                print(f"Failed to remove scheduled task: {result.stderr.strip()}")
    except Exception as e:
        print(f"Error removing scheduled task: {e}")


if __name__ == "__main__":
    remove_send_to_shortcut()
    remove_tray_startup()
    remove_scheduled_update_check()
