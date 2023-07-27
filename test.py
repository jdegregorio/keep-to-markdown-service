import os
import re
import requests
import gkeepapi
import mimetypes
from dotenv import load_dotenv
import shutil
from pathlib import Path

# Define config variables
MIGRATE_LABEL = 'Ready to Export'
SUCCESSFUL_MIGRATION_LABEL = 'Succesfully Exported'
OUTPUT_DIR = './notes/'
MEDIA_DIR = './media/'

# Define illegal characters
ILLEGAL_FILE_CHARS = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', '&', '\n', '\r', '\t']
ILLEGAL_TAG_CHARS = ['~', '`', '!', '@', '$', '%', '^', '(', ')', '+', '=', '{', '}', '[', \
    ']', '<', '>', ';', ':', ',', '.', '"', '/', '\\', '|', '?', '*', '&', '\n', '\r']

# Maximum filename length
MAX_FILENAME_LENGTH = 255

# A list to store all note names
namelist = []

# Authenticate Google Account
load_dotenv()
user = os.getenv('GOOGLE_KEEP_USERNAME')
password = os.getenv('GOOGLE_KEEP_PASSWORD')

# Authenticate
keep = gkeepapi.Keep()
keep.login(user, password)
token = keep.getMasterToken()

# Clear the notes and media directory before running the script
if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR)

if os.path.exists(MEDIA_DIR):
    shutil.rmtree(MEDIA_DIR)
os.makedirs(MEDIA_DIR)

# Function to format the note title
def format_title(title):
    return re.sub(
        '[' + re.escape(''.join(ILLEGAL_FILE_CHARS)) + ']', 
        ' ', 
        title[0:MAX_FILENAME_LENGTH]
    )

# Function to check and handle duplicate note names
def handle_duplicate_name(note_title):
    base_title = note_title
    index = 1

    while note_title in namelist:
        note_title = f"{base_title}_{index}"
        index += 1

    namelist.append(note_title)

    return note_title

# Sync and download all notes with the "migrate" label
keep.sync()
label = keep.findLabel(MIGRATE_LABEL)

# Find all notes that are ready to migrate
notes =  keep.find(labels=[label])

for note in notes:
    # Convert note to markdown
    text = note.text

    # Format checkboxes
    text = text.replace(u"\u2610", '- [ ]').replace(u"\u2611", ' - [x]')

    # Format URLs
    urls = re.findall(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[~#$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        text
    )
    for url in urls:
        text = text.replace(url, f"[{url}]({url})")

    # Handle duplicate names
    formatted_title = format_title(note.title.replace(" ", "_"))
    unique_title = handle_duplicate_name(formatted_title)

    # Save note
    with open(os.path.join(OUTPUT_DIR, unique_title + '.md'), 'w') as f:
        f.write(text)

    # Save blobs
    for idx, blob in enumerate(note.blobs):
        blob_name = unique_title + str(idx)
        url = keep.getMediaLink(blob)

        response = requests.get(url, allow_redirects=True)

        # Identify the extension of the file from the Content-Type header
        content_type = response.headers['content-type']
        ext = mimetypes.guess_extension(content_type)

        with open(os.path.join(MEDIA_DIR, blob_name + ext), 'wb') as media_file:
            media_file.write(response.content)

        # Append the media link at the end of the note
        with open(os.path.join(OUTPUT_DIR, unique_title + '.md'), 'a') as f:
            f.write(f"\n![{blob_name}]({os.path.join(MEDIA_DIR, blob_name + ext)})")

    # Once successfully saved, add a "Successfully Migrated" label to the Google Keep Note
    label_success = keep.findLabel(SUCCESSFUL_MIGRATION_LABEL)
    if not label_success:
        label_success = keep.createLabel(SUCCESSFUL_MIGRATION_LABEL)
    note.labels.add(label_success)

    # # Remove the "Ready to Export" label
    # note.labels.remove(label)

    keep.sync()
