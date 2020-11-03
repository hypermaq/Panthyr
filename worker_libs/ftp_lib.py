from ftplib import FTP
import os
import logging

__metaclass__ = type  # use new-style classes

log = logging.getLogger("__main__.{}".format(__name__))

class FTP_class(object):  # using subclass 'object' to use a new-style class in Python 2

     def __init__(self, server = '', 
                         timeout = 10):
          self.server = server
          self.timeout = timeout
          try:
               self.ftp = FTP(server, timeout = self.timeout)
          except Exception as e:
               log.error('Something went wrong while initializing the ftp connection: {}'.format(e))

     def login(self, user = '', password = ''):
          try:
               self.user = user
               self.password = password
               self.ftp.login(self.user, self.password)
               return (True,'')

          except Exception as e:
               message = 'Problem logging "{}" in to "{}" using password "{}": {}'.format(self.user, self.server, self.password, e)
               log.error(message)
               return(False, message)
               
     def cwd(self, target_dir):
          try:
               r = self.ftp.cwd(target_dir)
               return(True, r)

          except Exception as e:
               log.error(e)
               return(False, e)
     
     def pwd(self):
          s = self.ftp.pwd()
          return(True,s)

     def get_contents(self, dir = '.', only_dirs = False, only_files = False):
          if only_dirs == only_files == True:
               return(False, 'Cannot filter on both files and directories')

          command = 'LIST {}'.format(dir)  # command to be sent to the server
          ret = []  # empty list to hold lines returned by ftp command
          self.ftp.retrlines(command, callback=ret.append)
          
          if only_dirs:
               gen = (' '.join(line.split()[8:]) for line in ret if line[0] == 'd')  
               # lines that start with d (directories) are split at spaces, then everything starting at the eight item is the directory name
          elif only_files:
               gen = (' '.join(line.split()[8:]) for line in ret if not line[0] == 'd')
          else:
               gen = (' '.join(line.split()[8:]) for line in ret)

          return(True, list(gen))
     
     def upload_file(self, file):
          """uploads file to current working directory.
          If file exists, it is silently overwritten.
          """
          if not os.path.isfile(file): 
               return (False, 'File doesn\' exist')
          
          filename_base = os.path.basename(file)
          r = self.ftp.storbinary('STOR {}'.format(filename_base), open(file, 'rb'))
          # !!! appendix to STOR is the target filename on the server, including path!!!
          if self.check_exists(filename_base):
               return (True, r)
          else:
               return (False, r)

     def check_exists(self, target):
          """checks if [target] (the filename) exist in current directory
          Ignores case (README.txt == rEaDmE.tXt)
          """
          try:
               assert type(target) == str, 'Not a valid filename'
               file_list = self.get_contents(only_files = True)[1]
               if any(target.lower() == file.lower() for file in file_list):
                    return (True, )
               else:
                    return (False, 'File doesn\'t exist')
          except Exception as e:
               log.error(e)
               return (False, e)
          
     def size(self, target):
          try:
               self.ftp.voidcmd('TYPE I')  # some servers respond with 550 SIZE not allowed in ASCII mode if not set to TYPE I
               size = int(self.ftp.size(target))
               if size  == None:
                    raise Exception('failed or file doesn\'t exist')
               return (True, size)
          
          except Exception as e:
               log.error(e)
               return(False, e)



if __name__ == "__main__":
     pass