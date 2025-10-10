import os
import shutil
import sys
import ctypes
import tempfile
import time
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging with more detailed format
log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, "file_processor.log")
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Add console handler to see logs in real-time
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# Configuration - Primary directories
FOLDER_MERGE_DIRS = [r'\\ronsyn\ClientServices', r'\\ronsyn\FaxDocs']
FILE_COPY_DIR = r'\\ronsyn\CSRs\CNR'

# Configuration - Completed directories (only used if needed)
COMPLETED_MERGE_DIRS = [
    r'\\ronsyn\ClientServices\_COMPLETED',
    r'\\ronsyn\FaxDocs\(completed)'
]
COMPLETED_FILE_DIR = r'\\ronsyn\CSRs\CNR\_COMPLETED'

# Add timeout for network operations
NETWORK_TIMEOUT = 180  # seconds

def get_files_from_directory(directory):
    """Returns a list of file names in the directory with optimized scanning."""
    try:
        logging.info(f"Scanning directory for files: {directory}")
        start_time = time.time()
        result = [entry.name for entry in os.scandir(directory) if entry.is_file()]
        elapsed = time.time() - start_time
        logging.info(f"Scan complete. Found {len(result)} files in {elapsed:.2f} seconds")
        return result
    except (FileNotFoundError, PermissionError) as e:
        logging.warning(f"Could not access directory {directory}: {str(e)}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error accessing directory {directory}: {str(e)}")
        logging.error(traceback.format_exc())
        return []

def check_folder_exists(directory, folder_name):
    """Fast check if a folder exists in a directory without listing all content."""
    try:
        path = os.path.join(directory, folder_name)
        result = os.path.isdir(path)
        logging.debug(f"Checked if folder {folder_name} exists in {directory}: {result}")
        return result
    except Exception as e:
        logging.error(f"Error checking if folder {folder_name} exists in {directory}: {str(e)}")
        return False

def unique_name(destination):
    """Generate a unique filename by appending a counter if needed."""
    base, ext = os.path.splitext(destination)
    counter = 1
    while os.path.exists(destination):
        destination = f"{base} ({counter}){ext}"
        counter += 1
    return destination

def search_directory_recursive(base_dir, prompt_base):
    """Search through a directory for a folder matching prompt_base with optimizations."""
    try:
        logging.debug(f"Searching directory {base_dir} for folder {prompt_base}")
        
        # First try direct match at top level (most common case)
        direct_match = os.path.join(base_dir, prompt_base)
        if os.path.isdir(direct_match):
            logging.debug(f"Found direct match: {direct_match}")
            return direct_match
        
        # Use a more targeted approach for subdirectories
        for entry in os.scandir(base_dir):
            if entry.is_dir():
                # Check if the current directory is the one we're looking for
                if entry.name == prompt_base:
                    logging.debug(f"Found match in subdirectory: {entry.path}")
                    return entry.path
                
                # Check immediate subdirectories (one level deep) for common patterns
                if entry.name.startswith(prompt_base[:1]) or entry.name in ["0-9", "A-F", "G-M", "N-Z"]:
                    subdir_match = os.path.join(entry.path, prompt_base)
                    if os.path.isdir(subdir_match):
                        logging.debug(f"Found match in pattern subdirectory: {subdir_match}")
                        return subdir_match
                    
                    # Try one more level for common date-based organization
                    try:
                        for subentry in os.scandir(entry.path):
                            if subentry.is_dir():
                                subsubdir_match = os.path.join(subentry.path, prompt_base)
                                if os.path.isdir(subsubdir_match):
                                    logging.debug(f"Found match in date subdirectory: {subsubdir_match}")
                                    return subsubdir_match
                    except (FileNotFoundError, PermissionError) as e:
                        logging.warning(f"Could not access subdirectory {entry.path}: {str(e)}")
                        continue
                    except Exception as e:
                        logging.error(f"Error accessing subdirectory {entry.path}: {str(e)}")
                        continue
        
        logging.debug(f"No match found for {prompt_base} in {base_dir}")
        return None
    except (FileNotFoundError, PermissionError) as e:
        logging.warning(f"Could not access directory {base_dir} for search: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Error searching directory {base_dir} for {prompt_base}: {str(e)}")
        logging.error(traceback.format_exc())
        return None

def copy_folder_with_timeout(source_folder, dest_folder, timeout=NETWORK_TIMEOUT):
    """
    Copy a folder with a timeout to prevent hanging on network issues.
    
    Args:
        source_folder: Source folder path
        dest_folder: Destination folder path
        timeout: Timeout in seconds
    
    Returns:
        int: Number of files copied
    """
    file_count = 0
    start_time = time.time()
    
    try:
        # Record the start time for the operation
        operation_start = time.time()
        
        # Recursively copy the entire folder structure
        for root, dirs, files in os.walk(source_folder):
            # Check if we've exceeded the timeout
            current_time = time.time()
            if current_time - operation_start > timeout:
                logging.error(f"Timeout exceeded ({timeout}s) while copying from {source_folder}")
                return file_count
                
            # Calculate the relative path from source_folder
            rel_path = os.path.relpath(root, source_folder)
            
            # Create the corresponding destination directory
            dest_path = os.path.join(dest_folder, rel_path) if rel_path != '.' else dest_folder
            os.makedirs(dest_path, exist_ok=True)
            
            # Copy all files in the current directory
            for file in files:
                # Check timeout again
                current_time = time.time()
                if current_time - operation_start > timeout:
                    logging.error(f"Timeout exceeded ({timeout}s) while copying from {source_folder}")
                    return file_count
                    
                src_file = os.path.join(root, file)
                dest_file = os.path.join(dest_path, file)
                
                # Handle name conflicts properly
                if os.path.exists(dest_file):
                    # Create a unique name for the incoming file
                    dest_file = unique_name(dest_file)
                
                # Copy the file with the unique name
                try:
                    shutil.copy2(src_file, dest_file)
                    file_count += 1
                except (IOError, PermissionError) as e:
                    logging.warning(f"Could not copy {src_file} to {dest_file}: {str(e)}")
                    continue
                except Exception as e:
                    logging.error(f"Error copying {src_file} to {dest_file}: {str(e)}")
                    logging.error(traceback.format_exc())
                    continue
        
        elapsed = time.time() - start_time
        logging.info(f"Copy operation completed in {elapsed:.2f} seconds")
    except Exception as e:
        logging.error(f"Error during folder copy operation: {str(e)}")
        logging.error(traceback.format_exc())
        
    return file_count

def process_prompt_base_folders(prompt_dir, folder_merge_dirs, completed_merge_dirs, prompt_base):
    """Process folder merging for a single prompt base across multiple directories with recursive copying."""
    matched = False
    
    try:
        # First do fast existence checks before creating any folders
        matching_dirs = []
        for search_dir in folder_merge_dirs:
            if check_folder_exists(search_dir, prompt_base):
                matching_dirs.append(search_dir)
        
        # If no match in primary directories, check completed directories
        if not matching_dirs and completed_merge_dirs:
            for search_dir in completed_merge_dirs:
                if check_folder_exists(search_dir, prompt_base):
                    matching_dirs.append(search_dir)
        
        # If still no matches, return None
        if not matching_dirs:
            logging.info(f"No matching folders found for {prompt_base}")
            return None
        
        # Create a destination folder only when needed
        dest_folder = os.path.join(prompt_dir, prompt_base)
        os.makedirs(dest_folder, exist_ok=True)
        
        # Process all matching directories to ensure ALL matches are found
        for search_dir in matching_dirs:
            source_folder = os.path.join(search_dir, prompt_base)
            if os.path.isdir(source_folder):
                try:
                    logging.info(f"Starting manual copy from {source_folder} to {dest_folder}")
                    file_count = copy_folder_with_timeout(source_folder, dest_folder)
                    
                    if file_count > 0:
                        logging.info(f"Copied {file_count} files from {source_folder} into {dest_folder} (including subfolders)")
                        matched = True
                except Exception as e:
                    logging.error(f"Error copying from {source_folder} to {dest_folder}: {str(e)}")
                    logging.error(traceback.format_exc())
        
        # If nothing was found or copied, clean up the empty destination folder
        if not matched and os.path.exists(dest_folder):
            try:
                if not os.listdir(dest_folder):
                    os.rmdir(dest_folder)
                    logging.info(f"Removed empty folder {dest_folder}")
            except Exception as e:
                logging.error(f"Error cleaning up empty folder {dest_folder}: {str(e)}")
                logging.error(traceback.format_exc())
    
    except Exception as e:
        logging.error(f"Error in process_prompt_base_folders for {prompt_base}: {str(e)}")
        logging.error(traceback.format_exc())
            
    return prompt_base if matched else None

def process_prompt_base_files(prompt_dir, hardcoded_dir, completed_file_dir, prompt_base, hardcoded_files, completed_files):
    """Process file copying for a single prompt base with optimized filename matching."""
    matched = False
    
    try:
        matching_files = []
        
        # Use faster string operations to filter the file list
        prompt_base_lower = prompt_base.lower()
        
        # Collect all matching files first - much faster than copying one by one
        for filename in hardcoded_files:
            file_base_lower = os.path.splitext(filename)[0].lower()
            if prompt_base_lower in file_base_lower:
                matching_files.append((os.path.join(hardcoded_dir, filename), filename))
        
        # Check completed files if provided and no matches found in primary
        if not matching_files and completed_file_dir and completed_files:
            for filename in completed_files:
                file_base_lower = os.path.splitext(filename)[0].lower()
                if prompt_base_lower in file_base_lower:
                    matching_files.append((os.path.join(completed_file_dir, filename), filename))
        
        # Only create destination folder if we have files to copy
        if matching_files:
            dest_folder = os.path.join(prompt_dir, prompt_base)
            os.makedirs(dest_folder, exist_ok=True)
            
            # Copy all matching files in a batch
            file_count = 0
            start_time = time.time()
            
            for src, filename in matching_files:
                # Check timeout
                current_time = time.time()
                if current_time - start_time > NETWORK_TIMEOUT:
                    logging.error(f"Timeout exceeded ({NETWORK_TIMEOUT}s) while copying files for {prompt_base}")
                    break
                    
                dest = os.path.join(dest_folder, filename)
                
                # Handle name conflicts properly
                if os.path.exists(dest):
                    # Create a unique name for the incoming file
                    dest = unique_name(dest)
                
                try:
                    shutil.copy2(src, dest)
                    logging.info(f"Copied {filename} to {dest_folder}")
                    file_count += 1
                    matched = True
                except Exception as e:
                    logging.error(f"Error copying {src} to {dest}: {str(e)}")
                    logging.error(traceback.format_exc())
            
            if file_count > 0:
                logging.info(f"Copied {file_count} files for {prompt_base}")
    
    except Exception as e:
        logging.error(f"Error in process_prompt_base_files for {prompt_base}: {str(e)}")
        logging.error(traceback.format_exc())
    
    return prompt_base if matched else None

def move_input_file(prompt_dir, prompt_base):
    """Moves input file to its respective directory if it exists, handling name conflicts."""
    try:
        pdf_file = f"{prompt_base}.pdf"
        src = os.path.join(prompt_dir, pdf_file)
        if os.path.exists(src):
            dest_folder = os.path.join(prompt_dir, prompt_base)
            dest = os.path.join(dest_folder, pdf_file)
            
            try:
                os.makedirs(dest_folder, exist_ok=True)
                
                # Handle name conflicts for the input file
                if os.path.exists(dest) and os.path.samefile(src, dest):
                    # Same file, no need to move
                    logging.info(f"File {pdf_file} is already in the correct location")
                    return
                elif os.path.exists(dest):
                    # Create a temporary directory
                    with tempfile.TemporaryDirectory() as temp_dir:
                        # Create a unique name
                        base, ext = os.path.splitext(pdf_file)
                        counter = 1
                        temp_filename = f"{base} ({counter}){ext}"
                        temp_path = os.path.join(temp_dir, temp_filename)
                        
                        # Copy to temp with new name
                        shutil.copy2(src, temp_path)
                        
                        # Move from temp to final destination with the new name
                        final_dest = unique_name(dest)
                        shutil.move(temp_path, final_dest)
                        
                        # Remove original
                        os.remove(src)
                        logging.info(f"Moved and renamed {pdf_file} to {os.path.basename(final_dest)}")
                else:
                    # No conflict, simple move
                    shutil.move(src, dest)
                    logging.info(f"Moved {pdf_file} to {dest_folder}")
            except Exception as e:
                logging.error(f"Error moving {src} to {dest}: {str(e)}")
                logging.error(traceback.format_exc())
    except Exception as e:
        logging.error(f"Error in move_input_file for {prompt_base}: {str(e)}")
        logging.error(traceback.format_exc())

def process_prompt_bases_in_batches(prompt_dir, prompt_bases, batch_size=20):
    """
    Process prompt bases in batches to avoid memory issues with large sets.

    Args:
        prompt_dir: Destination directory
        prompt_bases: List of prompt bases to process
        batch_size: Number of prompt bases to process in each batch

    Returns:
        set: Set of successfully matched prompt bases
    """
    all_matched = set()
    folder_matched = set()
    file_matched = set()

    # Pre-fetch file list for primary directory - cache to avoid repeated network access
    try:
        hardcoded_files = get_files_from_directory(FILE_COPY_DIR) if os.path.exists(FILE_COPY_DIR) else []
        logging.info(f"Found {len(hardcoded_files)} files in primary directory")
    except Exception as e:
        logging.error(f"Error getting files from primary directory: {str(e)}")
        hardcoded_files = []

    # Pre-fetch file list for completed files directory - only if needed
    completed_files = []
    if os.path.exists(COMPLETED_FILE_DIR):
        try:
            completed_files = get_files_from_directory(COMPLETED_FILE_DIR)
            logging.info(f"Found {len(completed_files)} files in completed directory")
        except Exception as e:
            logging.error(f"Error getting files from completed directory: {str(e)}")

    # Process in batches
    total_batches = (len(prompt_bases) + batch_size - 1) // batch_size
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(prompt_bases))
        batch = prompt_bases[start_idx:end_idx]

        logging.info(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch)} prompt bases)")

        # Process the folder copies
        with ThreadPoolExecutor(max_workers=min(4, len(batch))) as executor:
            folder_tasks = {}
            for pb in batch:
                folder_tasks[executor.submit(
                    process_prompt_base_folders,
                    prompt_dir,
                    FOLDER_MERGE_DIRS,
                    COMPLETED_MERGE_DIRS,
                    pb
                )] = pb

            # Collect results as they complete
            for task in as_completed(folder_tasks):
                try:
                    result = task.result(timeout=NETWORK_TIMEOUT)  # Use network timeout
                    if result:
                        all_matched.add(result)
                        folder_matched.add(result)
                except Exception as e:
                    prompt_base = folder_tasks[task]
                    logging.error(f"Error in folder task for {prompt_base}: {str(e)}")
                    logging.error(traceback.format_exc())

        # Process file copies for all unmatched prompt bases
        unmatched_in_batch = [pb for pb in batch if pb not in all_matched]
        if unmatched_in_batch:
            with ThreadPoolExecutor(max_workers=min(4, len(unmatched_in_batch))) as executor:
                file_tasks = {}
                for pb in unmatched_in_batch:
                    file_tasks[executor.submit(
                        process_prompt_base_files,
                        prompt_dir,
                        FILE_COPY_DIR,
                        COMPLETED_FILE_DIR,
                        pb,
                        hardcoded_files,
                        completed_files
                    )] = pb

                # Collect results as they complete
                for task in as_completed(file_tasks):
                    try:
                        result = task.result(timeout=NETWORK_TIMEOUT)  # Use network timeout
                        if result:
                            all_matched.add(result)
                            file_matched.add(result)
                    except Exception as e:
                        prompt_base = file_tasks[task]
                        logging.error(f"Error in file task for {prompt_base}: {str(e)}")
                        logging.error(traceback.format_exc())

    # Report batch processing results
    logging.info(f"Total matches: {len(all_matched)} ({len(folder_matched)} folders and {len(file_matched)} files)")

    return all_matched, folder_matched, file_matched

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("No directory provided via 'Send To'.")
        sys.exit(1)

    prompt_dir = sys.argv[1]
    if not os.path.isdir(prompt_dir):
        print(f"The directory {prompt_dir} does not exist.")
        sys.exit(1)
        
    # Start timing
    start_time = time.time()
    logging.info(f"Starting processing at {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Get prompt bases from PDF files - optimize by only scanning once
    try:
        pdf_files = []
        with os.scandir(prompt_dir) as it:
            for entry in it:
                if entry.is_file() and entry.name.lower().endswith('.pdf'):
                    pdf_files.append(entry.name)
        
        prompt_bases = [os.path.splitext(f)[0] for f in pdf_files]
    except Exception as e:
        logging.error(f"Error scanning directory: {str(e)}")
        logging.error(traceback.format_exc())
        prompt_bases = []
    
    # Skip processing if no PDF files found
    if not prompt_bases:
        print("No PDF files found to process.")
        ctypes.windll.user32.MessageBoxW(0, "No PDF files found to process.", "Information", 0)
        sys.exit(0)
    
    logging.info(f"Found {len(prompt_bases)} PDF files to process")

    try:
        # Process in batches to avoid memory issues
        logging.info("Processing prompt bases...")
        all_matched, folder_matched, file_matched = process_prompt_bases_in_batches(prompt_dir, prompt_bases)
        
        # Report final matches
        logging.info(f"Total matched: {len(all_matched)} out of {len(prompt_bases)} prompt bases")
        logging.info(f"Total matches: {len(folder_matched)} folders and {len(file_matched)} files")
        
        # Move input files for matched bases
        if all_matched:
            logging.info(f"Moving {len(all_matched)} input PDF files to their destination folders")
            for pb in all_matched:
                move_input_file(prompt_dir, pb)
        
        # Report timing information
        elapsed_time = time.time() - start_time
        logging.info(f"Processing completed in {elapsed_time:.2f} seconds")

        # Display completion message
        message = f"Records copied for {len(all_matched)} out of {len(prompt_bases)} initial files"
        if len(all_matched) > 0:
            ctypes.windll.user32.MessageBoxW(0, message, "Finished", 1)
        else:
            ctypes.windll.user32.MessageBoxW(0, "No matching records found.", "Information", 0)
    
    except Exception as e:
        # Catch any unhandled exceptions in the main process
        logging.error(f"Unhandled exception in main process: {str(e)}")
        logging.error(traceback.format_exc())
        ctypes.windll.user32.MessageBoxW(0, f"An error occurred: {str(e)[:200]}", "Error", 0)