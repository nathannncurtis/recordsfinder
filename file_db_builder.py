import os
import json
import time
import logging
import sqlite3
import argparse

# Configure logging
logging.basicConfig(
    filename='file_db_builder.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Also log to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console)

BATCH_SIZE = 5000

DEFAULT_CONFIG_PATH = r'\\ronsin277\Users\sorting\Desktop\Scripts\Records Finder\scan_config.json'


class DatabaseBuilder:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.roots = self.config.get('folders', [])
        self.db_path = os.path.join(os.path.dirname(config_path), 'file_locations.db')

        self.folder_batch = []
        self.folder_size_batch = []
        self.conn = None

    def init_database(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            c.execute('''
            CREATE TABLE IF NOT EXISTS folder_locations (
                folder_name TEXT NOT NULL,
                folder_path TEXT PRIMARY KEY,
                source_root TEXT NOT NULL,
                last_updated REAL NOT NULL
            )
            ''')
            c.execute('''
            CREATE INDEX IF NOT EXISTS idx_folder_name
            ON folder_locations(folder_name)
            ''')

            c.execute('''
            CREATE TABLE IF NOT EXISTS folder_sizes (
                folder_path TEXT PRIMARY KEY,
                total_size INTEGER NOT NULL,
                file_count INTEGER NOT NULL,
                last_updated REAL NOT NULL
            )
            ''')

            conn.commit()
            conn.close()
            logging.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logging.error(f"Error initializing database: {e}")

    def open_connection(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA synchronous = OFF")
        self.conn.execute("PRAGMA journal_mode = MEMORY")
        self.conn.execute("PRAGMA cache_size = 100000")

    def close_connection(self):
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def flush_batches(self):
        if not self.conn:
            return

        c = self.conn.cursor()

        if self.folder_batch:
            c.executemany(
                "INSERT OR REPLACE INTO folder_locations VALUES (?, ?, ?, ?)",
                self.folder_batch
            )
            self.folder_batch = []

        if self.folder_size_batch:
            c.executemany(
                "INSERT OR REPLACE INTO folder_sizes VALUES (?, ?, ?, ?)",
                self.folder_size_batch
            )
            self.folder_size_batch = []

        self.conn.commit()

    def get_folder_size(self, folder_path):
        total_size = 0
        file_count = 0
        try:
            for item in os.listdir(folder_path):
                item_path = os.path.join(folder_path, item)
                if os.path.isfile(item_path):
                    total_size += os.path.getsize(item_path)
                    file_count += 1
        except Exception as e:
            logging.error(f"Error calculating size for {folder_path}: {e}")
        return total_size, file_count

    def get_stored_folder_size(self, folder_path):
        for item in self.folder_size_batch:
            if item[0] == folder_path:
                return item[1], item[2]
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT total_size, file_count FROM folder_sizes WHERE folder_path = ?", (folder_path,))
            result = c.fetchone()
            conn.close()
            if result:
                return result[0], result[1]
            return 0, 0
        except Exception as e:
            logging.error(f"Error getting folder size from database: {e}")
            return 0, 0

    def has_folder_changed(self, folder_path):
        stored_size, stored_count = self.get_stored_folder_size(folder_path)
        current_size, current_count = self.get_folder_size(folder_path)
        return current_size != stored_size or current_count != stored_count

    def update_folder_size(self, folder_path):
        total_size, file_count = self.get_folder_size(folder_path)
        self.folder_size_batch.append((folder_path, total_size, file_count, time.time()))
        if len(self.folder_size_batch) >= BATCH_SIZE:
            self.flush_batches()
        return total_size, file_count

    def add_folder_to_database(self, folder_name, folder_path, source_root):
        self.folder_batch.append((folder_name, folder_path, source_root, time.time()))
        if len(self.folder_batch) >= BATCH_SIZE:
            self.flush_batches()

    def scan_root(self, root_path, source_root, full_scan=False):
        start_time = time.time()
        folders_added = 0
        last_progress_log = 0

        if not os.path.exists(root_path):
            logging.warning(f"Root directory does not exist: {root_path}")
            return 0

        logging.info(f"Scanning root: {root_path}")

        try:
            for dirpath, dirnames, filenames in os.walk(root_path):
                # Skip the root directory itself
                if dirpath == root_path:
                    # Still check incremental change at root level
                    if not full_scan and not self.has_folder_changed(root_path):
                        logging.info(f"Root unchanged, skipping: {root_path}")
                        return 0
                    self.update_folder_size(root_path)
                    continue

                # For incremental scans, check if parent has changed
                parent = os.path.dirname(dirpath)
                if not full_scan and not self.has_folder_changed(parent):
                    dirnames.clear()
                    continue

                folder_name = os.path.basename(dirpath)
                self.add_folder_to_database(folder_name, dirpath, source_root)
                self.update_folder_size(dirpath)
                folders_added += 1

                if folders_added - last_progress_log >= 10000:
                    elapsed = time.time() - start_time
                    rate = folders_added / elapsed if elapsed > 0 else 0
                    logging.info(f"Progress: {folders_added:,} folders indexed ({rate:.0f} folders/sec)")
                    last_progress_log = folders_added

        except Exception as e:
            logging.error(f"Error scanning root {root_path}: {e}")

        elapsed_time = time.time() - start_time
        logging.info(f"Scan of {root_path} completed in {elapsed_time:.2f}s, indexed {folders_added} folders")
        return folders_added

    def cleanup_stale_entries(self, active_roots):
        if not self.conn:
            return
        try:
            if not active_roots:
                return
            placeholders = ','.join('?' for _ in active_roots)
            self.conn.execute(
                f"DELETE FROM folder_locations WHERE source_root NOT IN ({placeholders})",
                active_roots
            )
            self.conn.commit()
            logging.info("Cleaned up stale entries for removed roots")
        except Exception as e:
            logging.error(f"Error cleaning up stale entries: {e}")

    def build_database(self, full_scan=False):
        logging.info(f"Starting database {'full' if full_scan else 'incremental'} build")
        start_time = time.time()

        self.init_database()
        self.open_connection()

        try:
            total_count = 0
            active_roots = []

            for root_entry in self.roots:
                root_path = root_entry.get('path', '')
                label = root_entry.get('label', root_path)
                if not root_path:
                    continue
                active_roots.append(root_path)
                logging.info(f"Processing root: {label} ({root_path})")
                count = self.scan_root(root_path, root_path, full_scan)
                total_count += count

            self.flush_batches()
            self.cleanup_stale_entries(active_roots)
        finally:
            self.close_connection()

        elapsed_time = time.time() - start_time
        logging.info(f"Database build completed in {elapsed_time:.2f}s, indexed {total_count} folders total")
        return total_count


def main():
    parser = argparse.ArgumentParser(description='Build folder location database')
    parser.add_argument('--config', default=DEFAULT_CONFIG_PATH, help='Path to scan_config.json')
    parser.add_argument('--full', action='store_true', help='Perform a full scan instead of incremental')
    args = parser.parse_args()

    try:
        logging.info("Starting database builder")
        builder = DatabaseBuilder(args.config)
        total = builder.build_database(full_scan=args.full)
        logging.info(f"Database build completed successfully. Total folders: {total}")
    except Exception as e:
        logging.critical(f"Critical error: {e}")
        raise


if __name__ == "__main__":
    main()
