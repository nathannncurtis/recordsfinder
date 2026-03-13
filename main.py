import os
import sys
import shutil
import ctypes
import time
import logging
import traceback
import sqlite3
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import DB_PATH, ARCHIVE_DB_PATH, ARCHIVE_ROOT, get_enabled_folders

logging.disable(logging.CRITICAL)

NETWORK_TIMEOUT = 180


def unique_name(destination):
    base, ext = os.path.splitext(destination)
    counter = 1
    while os.path.exists(destination):
        destination = f"{base} ({counter}){ext}"
        counter += 1
    return destination


def query_matching_folders(folder_name, enabled_roots):
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        placeholders = ','.join('?' for _ in enabled_roots)
        query = (
            f"SELECT folder_name, folder_path, source_root "
            f"FROM folder_locations "
            f"WHERE folder_name = ? AND source_root IN ({placeholders})"
        )
        params = [folder_name] + list(enabled_roots)
        cursor = conn.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        logging.error(f"DB query error for '{folder_name}': {e}")
        return []


def copy_folder_with_timeout(source_folder, dest_folder, timeout=NETWORK_TIMEOUT):
    file_count = 0
    operation_start = time.time()

    try:
        for root, dirs, files in os.walk(source_folder):
            if time.time() - operation_start > timeout:
                logging.error(f"Timeout exceeded ({timeout}s) while copying from {source_folder}")
                return file_count

            rel_path = os.path.relpath(root, source_folder)
            dest_path = os.path.join(dest_folder, rel_path) if rel_path != '.' else dest_folder
            os.makedirs(dest_path, exist_ok=True)

            for file in files:
                if time.time() - operation_start > timeout:
                    logging.error(f"Timeout exceeded ({timeout}s) while copying from {source_folder}")
                    return file_count

                src_file = os.path.join(root, file)
                dest_file = os.path.join(dest_path, file)

                if os.path.exists(dest_file):
                    dest_file = unique_name(dest_file)

                try:
                    shutil.copy2(src_file, dest_file)
                    file_count += 1
                except (IOError, PermissionError) as e:
                    logging.warning(f"Could not copy {src_file}: {e}")
                except Exception as e:
                    logging.error(f"Error copying {src_file}: {e}")
    except Exception as e:
        logging.error(f"Error during folder copy: {e}")

    return file_count


# ── Records finding logic (existing) ─────────────────────────────────────────

def process_single_pdf(tmp_path, original_dir, enabled_roots):
    """Find matching record folders and copy them + the PDF to a new folder
    next to the original location. Works from the tmp copy of the file."""
    pdf_name = os.path.basename(tmp_path)
    prompt_base = os.path.splitext(pdf_name)[0]

    matches = query_matching_folders(prompt_base, enabled_roots)
    if not matches:
        return (prompt_base, False, 0)

    dest_folder = os.path.join(original_dir, prompt_base)
    os.makedirs(dest_folder, exist_ok=True)

    total_files = 0
    for folder_name, folder_path, source_root in matches:
        if os.path.isdir(folder_path):
            count = copy_folder_with_timeout(folder_path, dest_folder)
            total_files += count

    if total_files == 0:
        try:
            if not os.listdir(dest_folder):
                os.rmdir(dest_folder)
        except Exception:
            pass
        return (prompt_base, False, 0)

    # Copy (not move) the PDF into the results folder — tmp cleanup handles deletion
    pdf_dest = os.path.join(dest_folder, pdf_name)
    if os.path.exists(pdf_dest):
        renamed = unique_name(pdf_dest)
        os.rename(pdf_dest, renamed)
    shutil.copy2(tmp_path, pdf_dest)

    return (prompt_base, True, total_files)


# ── Archive logic (new) ──────────────────────────────────────────────────────

def get_current_date_folder():
    now = datetime.now()
    year = now.strftime('%Y')
    month_year = now.strftime('%m-%Y')
    day = now.strftime('%m_%d')
    # e.g. \\nas-prod\archive\records received\2026\03-2026\03_13
    return os.path.join(ARCHIVE_ROOT, year, month_year, day)


def query_archive_match(file_name):
    try:
        conn = sqlite3.connect(ARCHIVE_DB_PATH, timeout=10)
        cursor = conn.execute(
            "SELECT file_path FROM archive_files WHERE file_name = ?",
            (file_name,)
        )
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logging.error(f"Archive DB query error for '{file_name}': {e}")
        return None


def archive_single_file(tmp_path):
    """Archive a file: overwrite if it exists in the archive, otherwise copy to today's date folder."""
    file_name = os.path.basename(tmp_path)

    try:
        existing_path = query_archive_match(file_name)

        if existing_path:
            # Overwrite the existing file in the archive
            os.makedirs(os.path.dirname(existing_path), exist_ok=True)
            shutil.copy2(tmp_path, existing_path)
            logging.info(f"Archive overwrite: {file_name} -> {existing_path}")
        else:
            # Copy to today's date folder
            date_folder = get_current_date_folder()
            os.makedirs(date_folder, exist_ok=True)
            dest = os.path.join(date_folder, file_name)
            if os.path.exists(dest):
                dest = unique_name(dest)
            shutil.copy2(tmp_path, dest)
            logging.info(f"Archive new: {file_name} -> {dest}")

        return (file_name, True)
    except Exception as e:
        logging.error(f"Archive error for {file_name}: {e}")
        return (file_name, False)


# ── Main entry ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        ctypes.windll.user32.MessageBoxW(
            0, "No files or directory provided.\nUse Send To > Find Records.",
            "Records Finder", 0
        )
        sys.exit(1)

    # Collect PDF paths from arguments
    pdf_paths = []
    for arg in sys.argv[1:]:
        if os.path.isfile(arg) and arg.lower().endswith('.pdf'):
            pdf_paths.append(arg)
        elif os.path.isdir(arg):
            for entry in os.scandir(arg):
                if entry.is_file() and entry.name.lower().endswith('.pdf'):
                    pdf_paths.append(entry.path)

    if not pdf_paths:
        ctypes.windll.user32.MessageBoxW(0, "No PDF files found to process.", "Records Finder", 0)
        sys.exit(0)

    enabled_roots = get_enabled_folders()
    if not enabled_roots:
        ctypes.windll.user32.MessageBoxW(
            0, "No search folders configured.\nOpen the Records Finder tray app to configure folders.",
            "Records Finder", 0
        )
        sys.exit(0)

    # Move all input files to tmp so both threads can work from copies
    tmp_dir = tempfile.mkdtemp(prefix="records_finder_")
    # Track (tmp_path, original_dir) pairs
    work_items = []
    for pdf_path in pdf_paths:
        original_dir = os.path.dirname(pdf_path)
        tmp_dest = os.path.join(tmp_dir, os.path.basename(pdf_path))
        if os.path.exists(tmp_dest):
            tmp_dest = unique_name(tmp_dest)
        try:
            shutil.move(pdf_path, tmp_dest)
            work_items.append((tmp_dest, original_dir))
        except Exception as e:
            logging.error(f"Failed to move {pdf_path} to tmp: {e}")

    if not work_items:
        ctypes.windll.user32.MessageBoxW(0, "Failed to prepare files for processing.", "Records Finder", 0)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        sys.exit(1)

    total_count = len(work_items)
    matched_count = 0
    archive_count = 0

    with ThreadPoolExecutor(max_workers=min(8, total_count * 2)) as executor:
        # Submit find-records tasks
        find_futures = {
            executor.submit(process_single_pdf, tmp_path, orig_dir, enabled_roots): tmp_path
            for tmp_path, orig_dir in work_items
        }
        # Submit archive tasks
        archive_futures = {
            executor.submit(archive_single_file, tmp_path): tmp_path
            for tmp_path, orig_dir in work_items
        }

        for future in as_completed(find_futures):
            try:
                name, success, file_count = future.result(timeout=NETWORK_TIMEOUT)
                if success:
                    matched_count += 1
            except Exception as e:
                logging.error(f"Error processing {find_futures[future]}: {e}")
                logging.error(traceback.format_exc())

        for future in as_completed(archive_futures):
            try:
                name, success = future.result(timeout=NETWORK_TIMEOUT)
                if success:
                    archive_count += 1
            except Exception as e:
                logging.error(f"Error archiving {archive_futures[future]}: {e}")
                logging.error(traceback.format_exc())

    # Clean up tmp directory
    shutil.rmtree(tmp_dir, ignore_errors=True)

    # Display results
    lines = []
    if matched_count > 0:
        lines.append(f"Records found for {matched_count} of {total_count} files.")
    else:
        lines.append("No matching records found.")
    lines.append(f"Archived {archive_count} of {total_count} files.")

    ctypes.windll.user32.MessageBoxW(0, "\n".join(lines), "Records Finder", 0)
