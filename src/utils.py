import os
import logging

def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

def setup_logging(log_file):
    logging.basicConfig(filename=log_file, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

def log_message(message):
    logging.info(message)
