#!/usr/bin/python

import argparse
import httplib2
import os
import random
import time
import pickle

import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

MAX_RETRIES = 10

RETRIABLE_STATUS_CODES = [500, 502, 503, 504]

CLIENT_SECRETS_FILE = 'client_secret.json'

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

VALID_PRIVACY_STATUSES = ('public', 'private', 'unlisted')


# Authorize the request and store authorization credentials.
def get_authenticated_service():
  credentials = None
  #Load creds if available
  if os.path.exists('creds'):
    print("Cred file found. Using it to authenticate access the youtube...")
    try:
      with open('creds','rb') as file:
        credentials = pickle.load(file)
    except:
      print("Error in credential file...Removing and re-authenticating...")
      os.remove('creds')
      return get_authenticated_service()

  if not credentials or not credentials.valid:
    if credentials and credentials.expired and credentials.refresh_token:
      print("Refreshing access token...")
      credentials.refresh(Request())
    else:
      print("Fetching new tokens...Please authenticate..")
      flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
      flow.run_local_server(port=8080,
                           prompt="consent",
                            authorization_prompt_message="")
      credentials = flow.credentials
      with open('creds','wb') as file:
        print("Saving credentials...")
        pickle.dump(credentials,file)

  return build(API_SERVICE_NAME, API_VERSION, credentials = credentials)

def initialize_upload(youtube, options):
  tags = None
  if options.keywords:
    tags = options.keywords.split(',')

  body=dict(
    snippet=dict(
      title=options.title,
      description=options.description,
      tags=tags,
      categoryId=options.category
    ),
    status=dict(
      privacyStatus=options.privacyStatus
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
    media_body=MediaFileUpload(options.file, chunksize=10*10, resumable=True)
  )

  resumable_upload(insert_request)

# This method implements an exponential backoff strategy to resume a
# failed upload.
def resumable_upload(request):
  response = None
  error = None
  retry = 0
  while response is None:
    try:
      print( 'Uploading file...')
      status, response = request.next_chunk()
      if response is not None:
        if 'id' in response:
          print( 'Video id "%s" was successfully uploaded.' % response['id'])
        else:
          exit('The upload failed with an unexpected response: %s' % response)
    except:
      error = 'A retriable HTTP error occurred:\n'
      raise

    if error is not None:
      print( error)
      retry += 1
      if retry > MAX_RETRIES:
        exit('No longer attempting to retry.')

      max_sleep = 2 ** retry
      sleep_seconds = random.random() * max_sleep
      print( 'Sleeping %f seconds and then retrying...' % sleep_seconds)
      time.sleep(sleep_seconds)

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--file', required=True, help='Video file to upload')
  parser.add_argument('--title', help='Video title', default='Test Title')
  parser.add_argument('--description', help='Video description',
    default='Test Description')
  parser.add_argument('--category', default='22',
    help='Numeric video category. ' +
      'See https://developers.google.com/youtube/v3/docs/videoCategories/list')
  parser.add_argument('--keywords', help='Video keywords, comma separated',
    default='')
  parser.add_argument('--privacyStatus', choices=VALID_PRIVACY_STATUSES,
    default='private', help='Video privacy status.')
  args = parser.parse_args()

  youtube = get_authenticated_service()

  initialize_upload(youtube, args)
  