#!/usr/bin/python
import smtplib
from dbc import connection

def email_warning(subject, msg):
     db = connection()
     host = db.get_setting('email_server_port')[1]
     # port = db.get_setting('email_port')
     password = db.get_setting('email_password')[1]
     fromaddress = db.get_setting('email_from')[1]
     toaddress = db.get_setting('email_recipient')[1]
     toaddress = (toaddress.replace(" ", "").replace(";", ",")).split(",")
     station_id = db.get_setting('station_id')[1]

     smtp_connection = smtplib.SMTP(host = str(host), timeout = 10)
     mailheader = "From: {}\r\nTo: {}\r\nSubject: {}: {}\r\n\r\n".format(fromaddress, ",".join(toaddress), station_id, subject)
     mailbody = msg
     smtp_connection.starttls()
     smtp_connection.login(fromaddress, password)
     smtp_connection.sendmail(fromaddress, toaddress, mailheader + mailbody)
     print('email sent')