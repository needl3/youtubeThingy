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


SCOPES = {'upload':['https://www.googleapis.com/auth/youtube.upload'],'read':['https://www.googleapis.com/auth/youtube.readonly']}
SCOPES = ['https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.readonly']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

VALID_PRIVACY_STATUSES = ('public', 'private', 'unlisted')


# Authorize the request and store authorization credentials.
def getVideoId(youtube, title) -> str:
  print("[+]  Grabbing currently uploading videoId")

  response = youtube.search().list(
      part='snippet',
      forMine=True,
      type='video'
    )
  data = response.execute()
  try:
    for item in data['items']:
      if item['snippet']['title'] == title:
        print("[+]  Grabbed videoId as: ",item['id']['videoId'])
        return item['id']['videoId']
  except KeyError:
    print(f"[X]  No video uploaded with video title: {title}. Appending dummy id.")
    return "dummyVideoId"


def get_authenticated_service(args):
  credentials = None
  file = f"{args['cred']}"

  #Load creds if available
  if os.path.exists(file):
    print("[+]  Credentials found. Using it to authenticate...")
    try:
      with open(file,'rb') as f:
        credentials = pickle.load(f)
    except:
      print("[+]  Error in credential file...Removing and re-authenticating...")
      os.remove(file)
      return get_authenticated_service(args)

  if not credentials or not credentials.valid:
    if credentials and credentials.expired and credentials.refresh_token:
      print("[+]  Refreshing access token...")
      credentials.refresh(Request())
      
    else:
      print(f"[+]  Fetching new tokens for ...Please authenticate..")
      flow = InstalledAppFlow.from_client_secrets_file(args['CLIENT_SECRETS_FILE'], SCOPES)
      flow.run_local_server(port=9999,
                           prompt="consent",
                            authorization_prompt_message="")
      print("[+]  Waiting for port to be released from service...")
      while not os.system("fuser -i 9999/tcp"):
        time.sleep(1)

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
          privacyStatus=options['privacy']
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
  if not os.path.exists(f"{options['cred']}"):
    get_authenticated_service(options)
  resumable_upload(youtube, insert_request, options)

# This method implements an exponential backoff strategy to resume a
# failed upload.
def resumable_upload(youtube, request, options):
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
          print('[+]  Video successfully uploaded.\nVideo URL: https://www.youtube.com/watch?v=%s' % response['id'])
        else:
          exit('[-] The upload failed with an unexpected response: %s' % response)
      else:
        print(f"[+] Uploaded {status.progress()*100}%")
        if chunkNo == 1:
          replaceVideo(youtube, options)
          chunkNo=0
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

def replaceVideo(youtube, args):
  print("[-] Replacing video file")
  videoId = getVideoId(youtube, args['title'])
  image = videoMaker.RenderText2Image(args["message"]+videoId, outputFileName="img").getImage()
  videoFile = videoMaker.ImageToVideo("temp.mkv").generate_frames(image, args['videoTime'], exception=True)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Process some integers.')
  parser.add_argument('--title', default="Default title",help="Title of the video")
  parser.add_argument('--privacy', default="private",help="Video accessibility")
  parser.add_argument('--credDir', required=True, help="Directory containing client_secrets.json")
  parser.add_argument('--time',default=10,help="Video length")
  parser.add_argument('--message',default="You are watching\nhttps:/www./youtube.com/watch?v=",help="Text you want to upload as video")
  args = parser.parse_args()


  print("[+]  Preparing video")
  image = videoMaker.RenderText2Image(outputFileName="img").getImage()
  videoFile = videoMaker.ImageToVideo("temp.mkv").generate_frames(image, args.time, exception=True)

  fileDir = args.credDir if args.credDir[-1]!='/' else args.credDir[:-1]
  args = dict(
      title=args.title,
      file=videoFile,
      privacy=args.privacy,
      videoTime=args.time,
      prefix=fileDir+"/creds_",
      CLIENT_SECRETS_FILE=fileDir+"/client_secret.json",
      cred=fileDir+"/cred",
      message=str(args.message)
    )


  print("[+]  Uploading video...")
  youtube = get_authenticated_service(args)
  initialize_upload(youtube,args)