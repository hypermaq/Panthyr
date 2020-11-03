#! /usr/bin/python
# coding: utf-8
"""Function to grab frames from IP camera.

Project: Hypermaq
Dieter Vansteenwegen, VLIZ Belgium
Copyright?

Takes one frame from the camera and saves it to disk.
User has the choice to include a path/filename and to save a resized version as well.
"""

from cv2 import VideoCapture, imwrite, resize, INTER_AREA
import urllib2  # access to network
import datetime
import os
import numpy  # processing of image data
import logging
from file_utils import change_own_perm  # to change ownership and permissions of files


"""Functions."""

log = logging.getLogger("__main__.{}".format(__name__))

class ipcam(object):
    def __init__(self, ip="rtsp://192.168.100.104/axis-media/media.amp"):
        self.ip = ip
    
    def __check_path(self, absolute_filepath):
        """Checks is absolute filepath exists, else creates it.
        """
        if not os.path.isdir(absolute_filepath):  # check to see whether file path exists,
            try:
                os.makedirs(absolute_filepath)  # else, create it, makedirs is recursive (in contradiction to os.mkdir)
            except:
                raise Exception("(CHECK_PATH): Creating the non-existent path {} failed".format(absolute_filepath))


    def __create_full_path(self, absolute_filepath, filetype, resized = False):
        """Returns valid filename in the absolute filepath
        
        If file ("still_" + datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S") + ext) already exist, a counter is added at the end.
        If resized = True, _resized is added at the end of the filename, before the extention (before counter as well)
        Returns: full path + filename + ext
        """
        time = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ext = ".{}".format(filetype.lower())
        base_filename = "still_" + time  # base filename is based on timestamp
        if resized: 
            base_filename += "_resized"

        if os.path.isfile(os.path.join(absolute_filepath, (base_filename + ext))):  # filename exists already, add suffix to avoid overwriting
            fmt = base_filename + "({})" + ext  # placeholder for long string
            cnt = 1

            while os.path.isfile(os.path.join(absolute_filepath, fmt.format(cnt))):
                cnt += 1
            return os.path.join(absolute_filepath, fmt.format(cnt))
        else:
            return os.path.join(absolute_filepath, (base_filename + ext))
    

    def grab_frame(self,
        absolute_filepath="/home/hypermaq/data/stills/", 
        full = True,
        resize = False,
        filetype="jpg",
        quality = 50):
        """Grabs a frame from the IP Camera.

        filename is still_[date(yyymmdd)]_[time(hhmmss)].[extention in lowercase]. Example: still_21102017_145923.png
        If full = True, a full resolution image is saved.
        If resize = True, an image with half the width and height is saved as well
        Filetype determines the image filetype. Defaults to jpg. Other options: JPG, bmp, tiff.
        Quality sets jpeg compression quality (resulting in different filesize). Range 0 - 100.
        OpenCV uses the filename extention as reference

        TODO: check IP before continuing (is camera running?)
        """
        try: 
            # try:
            # response = urllib2.urlopen(urllib2.Request(ip), timeout=5)

            # log.debug('checking path and filename')
            self.__check_path(absolute_filepath)  # check/create path
            full_path = self.__create_full_path(absolute_filepath, filetype)  # check for available filename

            log.debug('opening stream')
            vc = VideoCapture(self.ip)  # open the stream
            log.debug('start capturing 5 frames')
            for _ in range(0,5):
                ret,frame = vc.read()  # throw away first few frames as they contain garbage
            # ret (boolean) will read True even if camera sent a black frame or jagged because it wasn't ready yet
            # frame is a numpy.ndarray object

            if not type(frame) == numpy.ndarray:  # return from cam was not a valid frame
                raise Exception("No frame returned from camera")

            encoding = [1, quality]  # sets encoding options, 1 is the index for CV_IMWRITE_JPEG_QUALITY

            if full:  # save full resolution version
                result = imwrite(full_path, frame, encoding)
                if not result:  # something went wrong during saving of the image
                    raise Exception("Error saving image (result: {})".format(result))
                change_own_perm(full_path, user = 'hypermaq', group = 'hypermaq')  # change ownership (we're running as root)

            if resize:  # if resize we'll save a resized version
                resized = resize(frame, None, fx=0.5, fy=0.5, interpolation=INTER_AREA)  # resizes to half height/width
                full_path_resized = self.__create_full_path(absolute_filepath, filetype, resized = True)  # check for available filename
                result = imwrite(full_path_resized, resized, encoding)  # store return from the write function in "result_resized"
                if not result:  # something went wrong during saving of the image, but 
                    # does not give any information on what went wrong exactly. 
                    # Maybe add a check to see if file exists and its size, and send with exception as info?
                    raise Exception("Saving resized image failed(result:{})".format(result))
                change_own_perm(full_path_resized, user = 'hypermaq', group = 'hypermaq')  # change ownership (we're running as root)

            return 'OK'

        except Exception as e:
            log.error("{}".format(e), exc_info=True)
            return e


"""Main loop"""
if __name__ == "__main__":
    print("This module does nothing on its own, exiting now...")