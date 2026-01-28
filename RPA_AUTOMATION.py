
from modules.helpers import *
from modules.SEND_EMAIL_SUMMARY import send_push_summary_email, send_pull_summary_email
import curlify
from modules.FILE_MAPPER_WITH_ERP import map_sftp_to_erp
from modules.ERP_PULL import ERP_to_PS_Pull
from modules.PEOPLE_STRONG_PUSH import PS_to_ERP_Push
from libraries import *



# =====================================================
# CALL FUNCTIONS DIRECTLY
# =====================================================
if __name__ == "__main__":
    PS_to_ERP_Push()
    ERP_to_PS_Pull()
