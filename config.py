import os
import sys
import json
import logging

NETWORK_SHARE_PATH = r'\\ronsin277\Users\sorting\Desktop\Scripts\Records Finder'
DB_PATH = os.path.join(NETWORK_SHARE_PATH, 'file_locations.db')
ARCHIVE_DB_PATH = os.path.join(NETWORK_SHARE_PATH, 'archive_locations.db')
SCAN_CONFIG_PATH = os.path.join(NETWORK_SHARE_PATH, 'scan_config.json')

ARCHIVE_ROOT = r'\\nas-prod\archive\records received'

LOCAL_CONFIG_DIR = os.path.join(os.environ.get('APPDATA', ''), 'Records Finder')
USER_CONFIG_PATH = os.path.join(LOCAL_CONFIG_DIR, 'user_config.json')


def get_app_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_icon_path():
    return os.path.join(get_app_path(), 'records_finder_comline.ico')


def read_scan_config():
    try:
        with open(SCAN_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Could not read scan config: {e}")
        return {"folders": []}


def write_scan_config(config):
    try:
        with open(SCAN_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Could not write scan config: {e}")
        return False


def read_user_config():
    try:
        with open(USER_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.debug(f"Could not read user config: {e}")
        return {"enabled_folders": []}


def write_user_config(config):
    try:
        os.makedirs(LOCAL_CONFIG_DIR, exist_ok=True)
        with open(USER_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Could not write user config: {e}")
        return False


def get_enabled_folders():
    user_cfg = read_user_config()
    enabled = user_cfg.get("enabled_folders", [])
    if enabled:
        return enabled
    # First run: all folders from scan config enabled by default
    scan_cfg = read_scan_config()
    return [f["path"] for f in scan_cfg.get("folders", [])]
