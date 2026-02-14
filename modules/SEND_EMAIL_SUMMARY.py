from modules.Helpers import log_event  
from libraries import *
from email.header import Header

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
        # msg['Subject'] = subject
        msg['Subject'] = Header(subject, 'utf-8') 
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



def send_mapping_alert_email(mapping_file_name, missing_ids=None):
    """
    Sends an alert email for Mapping CSV issues.

    Scenarios handled:
    1. No candidate IDs at all → missing_ids=None
    2. Some IDs present but ERP or PeopleStrong IDs missing → missing_ids=list of IDs
    """

    today_str = datetime.now().strftime('%d-%m-%Y')
    subject = f"PeopleStrong <> ERP Mapping Alert | {today_str}"

    if missing_ids is None:
        # Scenario 1: No candidate IDs in the mapping file
        body = f"""
        <html>
        <body style="font-family:Calibri, sans-serif; font-size:14px; color:#333;">
            <p>Dear Team,</p>
            <p>The Mapping file <b>{mapping_file_name}</b> was received but contains <b>no candidate IDs</b>.</p>
            <p><b>Automation stopped</b> due to missing candidate IDs in the mapping file.</p>
            <p>Regards,<br><b>RPA BOT</b></p>
        </body>
        </html>
        """
    else:
        # Scenario 2: Some IDs missing ERP or PeopleStrong IDs
        missing_rows = "".join([f"<tr><td>{cid}</td></tr>" for cid in missing_ids])
        body = f"""
        <html>
        <body style="font-family:Calibri, sans-serif; font-size:14px; color:#333;">
            <p>Dear Team,</p>
            <p>The Mapping file <b>{mapping_file_name}</b> contains candidate IDs, but the following IDs are missing ERP or PeopleStrong IDs:</p>
            <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-family:Calibri; font-size:13px; width:40%; text-align:center;">
                <tr style="background-color:#f4cccc;">
                    <th>Candidate IDs with Missing Mapping</th>
                </tr>
                {missing_rows}
            </table>
            <p><b>Automation stopped</b> for these IDs because relevant mapping fields are missing.</p>
            <p>Regards,<br><b>RPA BOT</b></p>
        </body>
        </html>
        """

    # Execute send
    if send_smtp_email(subject, body):
        logging.info(f"[ALERT] Mapping alert email sent successfully for {mapping_file_name}")
    else:
        logging.error(f"[ALERT] Failed to send mapping alert email for {mapping_file_name}")


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
    """Generates HTML for ERP to PeopleStrong Pull and sends via SMTP with aggregated candidate view."""
    
    if not subject:
        subject = f"ERP to PeopleStrong Pull Summary | {datetime.now().strftime('%d-%m-%Y')}"

    from collections import defaultdict
    import csv, io

    # Step 1: Aggregate files per candidate
    aggregated = defaultdict(lambda: {"files": [], "status": "SUCCESS", "failed_files": []})

    for entry in pull_data:
        emp_id = entry["Candidate ID"]
        file_name = entry["Data Extracted (files)"]
        aggregated[emp_id]["files"].append(file_name)

        if entry["Pull Status"] == "FAILED":
            aggregated[emp_id]["status"] = "FAILED"
            aggregated[emp_id]["failed_files"].append(f"{file_name} ({entry['BOT Comments']})")

    # Step 2: Prepare data for HTML table
    html_data = []
    for emp_id, info in aggregated.items():
        if info["status"] == "FAILED":
            bot_comment = "Failed: " + ", ".join(info["failed_files"])
        else:
            bot_comment = "File synced successfully"
        html_data.append({
            "Candidate ID": emp_id,
            "Data Extracted (files)": ", ".join(info["files"]),
            "Pull Status": info["status"],
            "BOT Comments": bot_comment
        })

    # Step 3: Build HTML table
    headers = ["Candidate ID", "Data Extracted (files)", "Pull Status", "BOT Comments"]
    rows = ""
    for row in html_data:
        rows += "<tr>" + "".join(f"<td>{row.get(h,'')}</td>" for h in headers) + "</tr>"

    pull_table = f"""
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-family:Calibri; font-size:13px;">
        <tr style="background-color:#d9e1f2;">
            {''.join(f'<th>{h}</th>' for h in headers)}
        </tr>
        {rows}
    </table>
    """

    # Step 4: Optional: attach full CSV for audit
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=headers)
    writer.writeheader()
    for row in html_data:  # aggregated view
        writer.writerow(row)
    csv_content = csv_buffer.getvalue()
    csv_buffer.close()

    # Step 5: Build email body
    body = f"""
    <html>
    <body>
        <p>Dear Team,</p>
        <p>BOT successfully completed the ERP → PeopleStrong pull.</p>
        <h3>ERP to PeopleStrong Pull Candidate Data (Aggregated)</h3>
        {pull_table}
        <p>Full file-level details attached as CSV.</p>
        <p>Regards,<br><b>RPA BOT</b></p>
    </body>
    </html>
    """

    # Step 6: Send email
    try:
        send_smtp_email(subject, body)
    except Exception as e:
        # Fallback: simple text email if HTML fails
        fallback_body = "BOT successfully completed the ERP → PeopleStrong pull.\n\n"
        fallback_body += "\n".join(
            [f"{r['Candidate ID']} | {r['Data Extracted (files)']} | {r['Pull Status']} | {r['BOT Comments']}" for r in html_data]
        )
        send_smtp_email(subject, fallback_body)
