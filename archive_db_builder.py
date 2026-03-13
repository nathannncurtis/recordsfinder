import os
import time
import logging
import sqlite3
import argparse

logging.basicConfig(
    filename='archive_db_builder.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console)

BATCH_SIZE = 5000

DEFAULT_ARCHIVE_ROOT = r'\\nas-prod\archive\records received'
DEFAULT_DB_PATH = r'\\ronsin277\Users\sorting\Desktop\Scripts\Records Finder\archive_locations.db'


class ArchiveDatabaseBuilder:
    def __init__(self, archive_root, db_path):
        self.archive_root = archive_root
        self.db_path = db_path
        self.file_batch = []
        self.conn = None

    def init_database(self):
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            c.execute('''
            CREATE TABLE IF NOT EXISTS archive_files (
                file_name TEXT NOT NULL,
                file_path TEXT PRIMARY KEY,
                last_updated REAL NOT NULL
            )
            ''')
            c.execute('''
            CREATE INDEX IF NOT EXISTS idx_archive_file_name
            ON archive_files(file_name)
            ''')

            conn.commit()
            conn.close()
            logging.info(f"Archive database initialized at {self.db_path}")
        except Exception as e:
            logging.error(f"Error initializing archive database: {e}")

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
        if self.file_batch:
            self.conn.executemany(
                "INSERT OR REPLACE INTO archive_files VALUES (?, ?, ?)",
                self.file_batch
            )
            self.file_batch = []
            self.conn.commit()

    def add_file(self, file_name, file_path):
        self.file_batch.append((file_name, file_path, time.time()))
        if len(self.file_batch) >= BATCH_SIZE:
            self.flush_batches()

    def build_database(self):
        logging.info(f"Starting archive database build for {self.archive_root}")
        start_time = time.time()

        self.init_database()
        self.open_connection()

        try:
            # Clear and rebuild — archive is authoritative
            self.conn.execute("DELETE FROM archive_files")
            self.conn.commit()

            files_indexed = 0
            last_progress_log = 0

            if not os.path.exists(self.archive_root):
                logging.warning(f"Archive root does not exist: {self.archive_root}")
                return 0

            for dirpath, dirnames, filenames in os.walk(self.archive_root):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    self.add_file(filename, file_path)
                    files_indexed += 1

                    if files_indexed - last_progress_log >= 10000:
                        elapsed = time.time() - start_time
                        rate = files_indexed / elapsed if elapsed > 0 else 0
                        logging.info(f"Progress: {files_indexed:,} files indexed ({rate:.0f} files/sec)")
                        last_progress_log = files_indexed

            self.flush_batches()
        finally:
            self.close_connection()

        elapsed_time = time.time() - start_time
        logging.info(f"Archive database build completed in {elapsed_time:.2f}s, indexed {files_indexed:,} files")
        return files_indexed


def main():
    parser = argparse.ArgumentParser(description='Build archive file location database')
    parser.add_argument('--root', default=DEFAULT_ARCHIVE_ROOT, help='Path to archive records received root')
    parser.add_argument('--db', default=DEFAULT_DB_PATH, help='Path to output database')
    args = parser.parse_args()

    try:
        logging.info("Starting archive database builder")
        builder = ArchiveDatabaseBuilder(args.root, args.db)
        total = builder.build_database()
        logging.info(f"Archive database build completed successfully. Total files: {total}")
    except Exception as e:
        logging.critical(f"Critical error: {e}")
        raise


if __name__ == "__main__":
    main()
