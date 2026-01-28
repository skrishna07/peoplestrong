# import win32com.client as win32
# from datetime import datetime
# import logging

# recipients = ["th187@o365sg.xyz"]

# # =====================================================
# # Email Function
# # =====================================================


# def send_push_summary_email(push_data):
#     try:

#         def build_html_table(data):
#             if not data:
#                 return "<p>No records available</p>"

#             rows = ""
#             for row in data:
#                 candidate_id = row.get("ERPID", "")
#                 #data_extracted = row.get("data_extracted", "")
#                 ##<td><pre style="white-space: pre-wrap;">{data_extracted}</pre></td>
#                 ##                    <th>Data Extracted</th>


#                 status = row.get("status", "")
#                 comments = row.get("comments", "")
#                 rows += f"""
#                     <tr>
#                         <td>{candidate_id}</td>
#                         <td>{status}</td>
#                         <td>{comments}</td>
#                     </tr>
#                 """

#             return f"""
#             <table border="1" cellpadding="6" cellspacing="0"
#                    style="border-collapse:collapse; font-family:Calibri; font-size:13px;">
#                 <tr style="background-color:#d9e1f2;">
#                     <th>Candidate ID</th>
#                     <th>Push Status</th>
#                     <th>BOT Comments</th>
#                 </tr>
#                 {rows}
#             </table>
#             """

#         push_table = build_html_table(push_data)

#         body = f"""
#         <html>
#         <body>
#             <p>Dear Team,</p>

#             <p>
#                 BOT successfully completed the run, please find the summary below.
#             </p>

#             <h3>Incremental Candidate Push – PeopleStrong to ERP</h3>
#             {push_table}

#             <p>
#                 Please review the summary.
#             </p>

#             <p>
#                 Regards,<br>
#                 <b>RPA BOT</b>
#             </p>
#         </body>
#         </html>
#         """

#         outlook = win32.Dispatch("Outlook.Application")
#         mail = outlook.CreateItem(0)
#         mail.To = "; ".join(recipients)
#         mail.Subject = f"PeopleStrong to ERP Automation Summary | {datetime.now().strftime('%d-%m-%Y')}"
#         mail.HTMLBody = body
#         mail.Send()

#         logging.info("SUCCESS: Summary email sent successfully.")

#     except Exception as e:
#         logging.error("ERROR: Email sending failed: %s", e)







# def send_pull_summary_email(pull_data, subject=None):
#     try:

#         # Default subject if not provided
#         if not subject:
#             subject = f"ERP to PeopleStrong Pull Summary | {datetime.now().strftime('%d-%m-%Y')}"

#         # Build HTML table
#         def build_html_table(data):
#             if not data:
#                 return "<p>No records available</p>"

#             headers = ["Candidate ID", "Data Extracted (files)", "Pull Status", "BOT Comments"]
#             rows = ""
#             for row in data:
#                 rows += "<tr>" + "".join(f"<td>{row.get(h,'')}</td>" for h in headers) + "</tr>"

#             return f"""
#             <table border="1" cellpadding="6" cellspacing="0"
#                    style="border-collapse:collapse; font-family:Calibri; font-size:13px;">
#                 <tr style="background-color:#d9e1f2;">
#                     {''.join(f'<th>{h}</th>' for h in headers)}
#                 </tr>
#                 {rows}
#             </table>
#             """

#         pull_table = build_html_table(pull_data)

#         # Compose email body
#         body = f"""
#         <html>
#         <body>
#             <p>Dear Team,</p>

#             <p>
#                 BOT successfully completed the ERP → PeopleStrong pull. Please find the summary below:
#             </p>

#             <h3>ERP to PeopleStrong Pull Candidate Data</h3>
#             {pull_table}

#             <p>
#                 Please review the summary attachment.
#             </p>

#             <p>
#                 Regards,<br>
#                 <b>RPA BOT</b>
#             </p>
#         </body>
#         </html>
#         """

#         # Send email via Outlook
#         outlook = win32.Dispatch("Outlook.Application")
#         mail = outlook.CreateItem(0)
#         mail.To = "; ".join(recipients)
#         mail.Subject = subject
#         mail.HTMLBody = body
#         mail.Send()

#         print("SUCCESS: Pull summary email sent successfully.")

#     except Exception as e:
#         print("ERROR: Pull summary email sending failed:", e)

