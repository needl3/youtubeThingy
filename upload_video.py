#!/usr/bin/python

import argparse
import httplib2
import os
import random
import time
import pickle
import videoMaker

import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError, ResumableUploadError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

MAX_RETRIES = 10

RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

CLIENT_SECRETS_FILE = '.quotaExceededCreds/anish/client_secret.json'

SCOPES = {'upload':['https://www.googleapis.com/auth/youtube.upload'],'read':['https://www.googleapis.com/auth/youtube.readonly']}
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

VALID_PRIVACY_STATUSES = ('public', 'private', 'unlisted')

videoTitle = "Youtube video url"
cred_prefix = ".quotaExceededCreds/anish/creds_"
VIDEO_TIME = 10


# Authorize the request and store authorization credentials.
def getVideoId(videoTitle:str) -> str:
  try:
    print("[+]  Grabbing currently uploading videoId")
    youtube = get_authenticated_service(mode='read')
  except:
    print('[-]  Request failed. Check your internet connection.')
    exit()

  response = youtube.search().list(
      part='snippet',
      forMine=True,
      type='video'
    )
  data = response.execute()
  for item in data['items']:
    if item['snippet']['title'] == videoTitle:
      print("[+]  Grabbed videoId as: ",item['id']['videoId'])
      return item['id']['videoId']
  print(f"[X]  No video uploaded with video title: {videoTitle}. Appending dummy id.")
  return "dummyVideoId"


def get_authenticated_service(mode='upload'):
  credentials = None
  file = f'{cred_prefix}{mode}'

  #Load creds if available
  if os.path.exists(file):
    print("[+]  Credentials found. Using it to authenticate...    Auth Mode: ",mode)
    try:
      with open(file,'rb') as f:
        credentials = pickle.load(f)
    except:
      print("[+]  Error in credential file...Removing and re-authenticating...")
      os.remove(file)
      return get_authenticated_service()

  if not credentials or not credentials.valid:
    if credentials and credentials.expired and credentials.refresh_token:
      print("[+]  Refreshing access token...")
      credentials.refresh(Request())
      
    else:
      print(f"[+]  Fetching new tokens for {mode}...Please authenticate..")
      flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES[mode])
      flow.run_local_server(port=8080,
                           prompt="consent",
                            authorization_prompt_message="")
      print("[+]  Waiting for port to be released from service...")
      time.sleep(5)
      credentials = flow.credentials
      with open(file,'wb') as f:
        print("[+]  Saving credentials...")
        pickle.dump(credentials,f)

  return build(API_SERVICE_NAME, API_VERSION, credentials = credentials)

def initialize_upload(youtube, options):
  body = dict(
    snippet=dict(
        title=options['title'],
        description="Test description",
        tags='youtube id',
        categoryId='22',
      ),
      status=dict(
          privacyStatus='private'
        )
    )
  # Call the API's videos.insert method to create and upload the video.
  insert_request = youtube.videos().insert(
    part=','.join(body.keys()),
    body=body,
    # The chunksize parameter specifies the size of each chunk of data, in
    # bytes, that will be uploaded at a time. Set a higher value for
    # reliable connections as fewer chunks lead to faster uploads. Set a lower
    # value for better recovery on less reliable connections.
    #
    # Setting 'chunksize' equal to -1 in the code below means that the entire
    # file will be uploaded in a single HTTP request. (If the upload fails,
    # it will still be retried where it left off.) This is usually a best
    # practice, but if you're using Python older than 2.6 or if you're
    # running on App Engine, you should set the chunksize to something like
    # 1024 * 1024 (1 megabyte).

    media_body=MediaFileUpload(options.get('file'), chunksize=256*1024, resumable=True)
  )
  if not os.path.exists(f'{cred_prefix}read'):
    get_authenticated_service(mode='read')
  resumable_upload(insert_request)

# This method implements an exponential backoff strategy to resume a
# failed upload.
def resumable_upload(request):
  response = None
  error = None
  retry = 10
  print('[+]  Uploading file...')
  chunkNo = 1
  while response is None:
    try:
      status, response = request.next_chunk()
      if response is not None:
        if 'id' in response:
          print('[+]  Video successfully uploaded.\nVideo URL: https://www.youtube.com/watch?v="%s"' % response['id'])
        else:
          exit('[-] The upload failed with an unexpected response: %s' % response)
      else:
        print(f"[+] Uploaded {status.progress()*100}%")
        print(f"[+] Chunk {chunkNo} sent...")
        if chunkNo == 1:
          replaceVideo()
        chunkNo+=1
    except:
      error = '[X]  A retriable HTTP error occurred:\n'
      raise

    if error is not None:
      print( error)
      retry += 1
      if retry > MAX_RETRIES:
        exit('[-] No longer attempting to retry.')

      max_sleep = 2 ** retry
      sleep_seconds = random.random() * max_sleep
      print('[-]  Sleeping %f seconds and then retrying...' % sleep_seconds)
      time.sleep(sleep_seconds)

def replaceVideo():
  print("[-] Replacing video file")
  videoId = getVideoId(videoTitle)
  image = videoMaker.RenderText2Image("This video's url is \nhttps://www.youtube.com/watch?v="+videoId, outputFileName="img").getImage()
  videoFile = videoMaker.ImageToVideo("temp.mkv").generate_frames(image, VIDEO_TIME, exception=True)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Process some integers.')
  parser.add_argument('--title', default="Default title",help="Title of the video")
  args = parser.parse_args()


  print("[+]  Preparing video")
  image = videoMaker.RenderText2Image(" ", outputFileName="img").getImage()
  videoFile = videoMaker.ImageToVideo("temp.mkv").generate_frames(image, VIDEO_TIME, exception=True)

  args = dict(
      title=args.title,
      file=videoFile
    )
  print("[+]  Uploading video...")
  youtube = get_authenticated_service()
  initialize_upload(youtube,args)