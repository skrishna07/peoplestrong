from modules.helpers import log_event  
from libraries import *


# =====================================================
# Core SMTP Engine
# =====================================================

def send_smtp_email(subject, html_body):
    """
    Handles the actual SMTP conversation with Gmail.
    Includes explicit EHLO sequence to avoid '503 Out of Sequence' errors.
    """
    server = None
    try:
        # Create Message Container
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECIPIENTS
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        log_event(f"Attempting to send SMTP email: {subject}")
        
        # 1. Establish Connection
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.set_debuglevel(0) # Set to 1 only for deep troubleshooting
        
        # 2. Strict Gmail Handshake Sequence
        server.ehlo()          # Identify to server
        server.starttls()      # Secure the connection
        server.ehlo()          # Re-identify after encryption (Critical for Gmail)
        
        # 3. Authentication
        try:
            server.login(SENDER_EMAIL, SENDER_PASS)
        except smtplib.SMTPAuthenticationError:
            log_event("SMTP Auth Failed: Check App Password or 2FA status.", is_error=True)
            return False

        # 4. Send Email
        server.sendmail(SENDER_EMAIL, RECIPIENTS, msg.as_string())
        
        log_event(f"SUCCESS: Email '{subject}' sent via SMTP.")
        return True

    except Exception as e:
        log_event(f"CRITICAL SMTP ERROR: {str(e)}", is_error=True)
        return False
    
    finally:
        if server:
            try:
                server.quit()
            except:
                pass

# =====================================================
# Summary Functions (Business Logic)
# =====================================================

def send_push_summary_email(push_data):
    """Generates HTML for PeopleStrong to ERP Push and sends via SMTP."""
    
    def build_html_table(data):
        if not data: 
            return "<p>No records available</p>"
        
        rows = ""
        for r in data:
            rows += f"<tr><td>{r.get('ERPID','')}</td><td>{r.get('status','')}</td><td>{r.get('comments','')}</td></tr>"
            
        return f"""
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-family:Calibri; font-size:13px;">
            <tr style="background-color:#d9e1f2;">
                <th>Candidate ID</th>
                <th>Push Status</th>
                <th>BOT Comments</th>
            </tr>
            {rows}
        </table>
        """

    push_table = build_html_table(push_data)
    subject = f"PeopleStrong to ERP Automation Summary | {datetime.now().strftime('%d-%m-%Y')}"
    
    body = f"""
    <html>
    <body>
        <p>Dear Team,</p>
        <p>BOT successfully completed the run, please find the summary below.</p>
        <h3>Incremental Candidate Push – PeopleStrong to ERP</h3>
        {push_table}
        <p>Regards,<br><b>RPA BOT</b></p>
    </body>
    </html>
    """
    
    # Execute Send
    if send_smtp_email(subject, body):
        print(f"INFO: {subject} triggered successfully.")
    else:
        print(f"ERROR: Failed to send {subject}.")

def send_pull_summary_email(pull_data, subject=None):
    """Generates HTML for ERP to PeopleStrong Pull and sends via SMTP."""
    
    if not subject:
        subject = f"ERP to PeopleStrong Pull Summary | {datetime.now().strftime('%d-%m-%Y')}"

    def build_html_table(data):
        if not data: 
            return "<p>No records available</p>"
            
        headers = ["Candidate ID", "Data Extracted (files)", "Pull Status", "BOT Comments"]
        rows = ""
        for row in data:
            rows += "<tr>" + "".join(f"<td>{row.get(h,'')}</td>" for h in headers) + "</tr>"

        return f"""
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-family:Calibri; font-size:13px;">
            <tr style="background-color:#d9e1f2;">
                {''.join(f'<th>{h}</th>' for h in headers)}
            </tr>
            {rows}
        </table>
        """

    pull_table = build_html_table(pull_data)
    
    body = f"""
    <html>
    <body>
        <p>Dear Team,</p>
        <p>BOT successfully completed the ERP → PeopleStrong pull.</p>
        <h3>ERP to PeopleStrong Pull Candidate Data</h3>
        {pull_table}
        <p>Regards,<br><b>RPA BOT</b></p>
    </body>
    </html>
    """

    # Execute Send
    if send_smtp_email(subject, body):
        print(f"INFO: {subject} triggered successfully.")
    else:
        print(f"ERROR: Failed to send {subject}.")


