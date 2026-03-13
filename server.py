import time
import logging
import schedule
from file_db_builder import DatabaseBuilder, DEFAULT_CONFIG_PATH
from archive_db_builder import ArchiveDatabaseBuilder, DEFAULT_ARCHIVE_ROOT, DEFAULT_DB_PATH

logging.basicConfig(
    filename='server.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console)


def build_folder_db():
    logging.info("Scheduled job: building folder database")
    try:
        builder = DatabaseBuilder(DEFAULT_CONFIG_PATH)
        total = builder.build_database(full_scan=False)
        logging.info(f"Folder database build complete. {total} folders indexed.")
    except Exception as e:
        logging.error(f"Folder database build failed: {e}")


def build_archive_db():
    logging.info("Scheduled job: building archive database")
    try:
        builder = ArchiveDatabaseBuilder(DEFAULT_ARCHIVE_ROOT, DEFAULT_DB_PATH)
        total = builder.build_database()
        logging.info(f"Archive database build complete. {total} files indexed.")
    except Exception as e:
        logging.error(f"Archive database build failed: {e}")


def run_all_builds():
    build_folder_db()
    build_archive_db()


if __name__ == "__main__":
    logging.info("Records Finder server started")

    # Run both builds on startup
    run_all_builds()

    # Schedule daily at 7 PM
    schedule.every().day.at("19:00").do(run_all_builds)

    logging.info("Scheduled daily database builds at 19:00")

    while True:
        schedule.run_pending()
        time.sleep(60)
