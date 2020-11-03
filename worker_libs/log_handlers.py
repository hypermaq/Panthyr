#! /usr/bin/python
# coding: utf-8
"""Log handlers.

05 sep 2019

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

Handlers (buffered email/smtp and logging to db).
"""

import logging
import logging.handlers
import smtplib

MAX_MSG_TO_BUFFER = 50  # number of log messages to send in one email

class buffered_SMTP_Handler(logging.handlers.BufferingHandler):

    def __init__(self, host, password, fromaddress, toaddress, id = ''):
        logging.handlers.BufferingHandler.__init__(self, MAX_MSG_TO_BUFFER)
        self.host = host
        self.port = 587
        self.password = password
        self.fromaddress = fromaddress
        self.toaddress = (toaddress.replace(" ", "").replace(";", ",")).split(",")
        self.subject = 'Error log from PANTHYR "{}"'.format(id)  # add id so recipient knows which panthyr has sent the mail

    def flush(self):
        if len(self.buffer) <> 0:
            connection = smtplib.SMTP(host = self.host, timeout = 10)
            # connection.set_debuglevel(1)
            mailheader = "From: {}\r\nTo: {}\r\nSubject: {}\r\n\r\n".format(self.fromaddress, ",".join(self.toaddress), self.subject)            
            mailbody = ''
            criticalbody = ''  # messages with the critical level are treated and send separately
            for log in self.buffer:
                mailbody += "{}\r\n".format(self.format(log))  # keep critical log messages in between others as well
                if self.format(log)[0:8] == 'CRITICAL':
                    criticalbody += '{}\r\n'.format(self.format(log))

            connection.starttls()
            connection.login(self.fromaddress, self.password)
            connection.sendmail(self.fromaddress, self.toaddress, mailheader + mailbody)
            if len(criticalbody) > 0:  # there were critical log messages, send those in a separate mail
                criticalheader = "From: {}\r\nTo: {}\r\nSubject: CRITICAL PANTHYR LOG\r\n\r\n".format(self.fromaddress, ",".join(self.toaddress))
                connection.sendmail(self.fromaddress, self.toaddress, criticalheader + criticalbody)
            connection.quit()
                
            super(buffered_SMTP_Handler, self).flush()

class db_Handler(logging.Handler):
    def __init__(self, db):
        logging.Handler.__init__(self)
        self.db = db

    def emit(self, record):
        db_level = record.levelname  # log level
        db_source = '{}.{}({})'.format(record.module, record.funcName, record.lineno)  # combine module/function and line number
        db_log = record.msg  # the log text
        if record.exc_info:  # an exception was thrown, log additional data such as traceback
            import traceback
            tb = traceback.format_list(traceback.extract_tb(record.exc_info[2]))  # get the traceback as string
            # process the string to make it shorter/neater
            tb = tb[0][7:-1].replace('/home/hypermaq/scripts', '.')  # shorten pad + get rid of ' File' and newline at the end
            tb = tb.replace('  ', ' ')  # remove double spaces
            tb = tb.replace('\n  ', '\n')  # remove whitespace after newline
            db_log = 'EXC {0} | {1[0]} | {1[1]} |{2}'.format(db_log, record.exc_info, tb)  # combine everything, start with EXC

        self.db.add_log(db_log, db_source, db_level)

if __name__ == "__main__":

    exit()

    # everything below is a test script
    # to add before this works: get host/fromaddress/password from file or arguments
    
    # log = logging.getLogger("mylogger")
    # fmt="%(asctime)s |%(levelname)-7s |%(module)s:%(lineno)s |%(funcName)s |%(message)s"
    # datefmt='%d/%m/%Y %H:%M:%S'
    # log.setLevel(logging.DEBUG)
    # h1 = logging.StreamHandler()
    # h1.setLevel(logging.DEBUG)
    # h1.setFormatter(logging.Formatter(fmt, datefmt))
    # h2 = buffered_SMTP_Handler(host = email_server_port,
    #                         fromaddress = email_user,
    #                         toaddress = "dieterv@vliz.be",
    #                         password = email_password)
    #                         # secure = ())
    # h2.setLevel(logging.INFO)
    # h2.setFormatter(logging.Formatter(fmt, datefmt))
    # log.addHandler(h1)
    # log.addHandler(h2)
    # for i in range(1, 51):
    #     log.info("_info message  {:03d}".format(i))
    #     log.debug("_debug message {:03d}".format(i))
    # logging.shutdown()