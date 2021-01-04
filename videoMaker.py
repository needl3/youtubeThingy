'''
Usage       :   python imagetovideo.py -i /home/administrator/Documents/dl/images 
                            -o /home/administrator/Documents/dl/images/video.avi 
                            -f 20                
'''
import argparse
import cv2
import numpy as np
import os
from PIL import Image, FontFile, ImageFont, ImageDraw


class RenderText2Image:
    
    ##Defines
    FULL_PATH_TO_FONT = '/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf'
    _bgcolor = None
    _fontColor = None
    _text = None
    _error, _errmsg = 1, None
    _outputFileName = None
    _img = None
    _font = None
    _draw = None
    
    def __init__(self, text, bgColor='#FFFFFF', fontColor='#000000', outputFileName="this"):
        ##Set global vars
        self._text, self._bgcolor, self._fontColor = text, bgColor, fontColor
        self._outputFileName = outputFileName
        self.makeBackground()
        
    def makeBackground(self):
        try:
            self._img = Image.new("RGB", (800, 800), self._bgcolor)
            self._draw = ImageDraw.Draw(self._img)
            self.setFontSize()
        except Exception:
            self._error, self._errmsg = 0, "Background could not be rendered ERR_MSG:"
    
    def setFontSize(self):
        print("set font size")
        fontsize = 1
        img_fraction = 1.7
        try:
            self._font = ImageFont.truetype(self.FULL_PATH_TO_FONT, fontsize)
            while self._font.getsize(self._text)[0] < img_fraction * self._img.size[0]:
                fontsize += 1
                self._font = ImageFont.truetype(self.FULL_PATH_TO_FONT, fontsize)
        except Exception:
            print("ERROR WITH FONT")
            
        self.addText2Image()
    
    def parseText(self):
        import textwrap
        lines = textwrap.wrap(self._text, 50)
        return lines
    
    def addText2Image(self):
        lines = self.parseText()
        try:
            count = 0
            for line in lines:
                width, height = self._font.getsize(line)
                self._draw.text((0,(count*height)+2), line, fill=self._fontColor, font=self._font)
                count += 1
            self._img.save(self._outputFileName, "PNG")
            print("Image saved as: ", self._outputFileName+".png")
        except Exception:
            print("Exception while addind text ot image")
            
    def getImage(self):
        return self._outputFileName if self._error else self._error

class ImageToVideo:
    def __init__(self, output):
        self.output = output

    def generate_frames(self, filename, sec, exception=False):
        frame_array = []
        if filename.endswith(".jpg") or filename.endswith(".jpeg") or filename.endswith(".png") or exception:
            img = cv2.imread(filename)
            height, width, layers = img.shape
            size = (width,height)
        else:
            print("[Task failed]***Input valid image***")
            return
        print("Appending images")
        i = 1
        for filename in range(int(sec)):
            frame_array.append(img)
            print("Appended ", i, "times")
            i += 1
        print("Total Frames: ", len(frame_array))
        fps=0.1
        print("Framerate set as ", fps," frame/sec.")

        out = cv2.VideoWriter(self.output,cv2.VideoWriter_fourcc(*'DIVX'), fps, size)
        
        print("Creating video stream")
        for i in range(len(frame_array)):
            out.write(frame_array[i])
            out.release()
        print("Video released as ", self.output)


# Define Argument Parser for the script
ap = argparse.ArgumentParser()
ap.add_argument("-i", "--input", required=True)
ap.add_argument("-o", "--output", required=True)
ap.add_argument("-t", "--time", required=True)

args = vars(ap.parse_args())

# Set user parameters
videoId = args["input"]
output = args["output"]
time = args["time"]

# Create ImageToVideo Class object
image_to_video = ImageToVideo(output)
image_to_video.generate_frames(
    RenderText2Image(
        "This video has it's video url of: https://www.youtube.com/watch?v="+videoId
        ).getImage(), time, exception=True)
