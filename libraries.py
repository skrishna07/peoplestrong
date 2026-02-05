# --- STANDARD LIBRARIES ---
import os
import io
import re
import json
import logging
import traceback
import base64
import sqlite3
import smtplib
import http
from datetime import datetime

# --- THIRD-PARTY LIBRARIES ---
import pandas as pd
import requests
import paramiko
from dotenv import load_dotenv
import time
# --- EMAIL UTILITIES ---
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
LOG_DIR = os.getenv("LOG_DIR")
ERP_HOST= os.getenv("ERP_HOST")
ERP_ENDPOINT = os.getenv("ERP_ENDPOINT")




SMTP_SERVER =os.getenv("SMTP_SERVER")
SMTP_PORT =os.getenv("SMTP_PORT")
SENDER_EMAIL =os.getenv("SENDER_EMAIL")
SENDER_PASS =os.getenv("SENDER_PASS")
RECIPIENTS =os.getenv("RECIPIENTS") 
# ------------------------------
# Logger setup
# ------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)




