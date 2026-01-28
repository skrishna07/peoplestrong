import os
import io
import logging
import traceback
import re
import json
from datetime import datetime
import win32com.client as win32


import requests
import paramiko
import pandas as pd
from dotenv import load_dotenv


# ------------------------------
# Load environment variables
# ------------------------------
load_dotenv()

# SFTP configuration
SFTP_HOST = os.getenv("SFTP_HOST")
SFTP_USER = os.getenv("SFTP_USER")
SFTP_PASS = os.getenv("SFTP_PASS")
SFTP_PORT = int(os.getenv("SFTP_PORT"))

# ERP API configuration
ERP_URL = os.getenv("ERP_API_URL")
AUTH_TOKEN = os.getenv("ERP_AUTH_TOKEN")
ERP_TEST_IDS = os.getenv("ERP_TEST_IDS")

# Data processing configuration
JOIN_KEY = os.getenv("JOIN_KEY")

# Directory paths
DOC_DIR = os.getenv("DOC_DIR")
INPUT_DIR = os.getenv("INPUT_DIR")
ARCHIVE_DIR = os.getenv("ARCHIVE_DIR")
IMPORT_DIR = os.getenv("IMPORT_DIR")

# ------------------------------
# Logger setup
# ------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)




