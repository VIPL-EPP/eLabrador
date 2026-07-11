import traceback
import uuid
import time

def format_error(e):
    return traceback.format_exception(e.__class__, value=e, tb=e.__traceback__)

def generate_temp_filepath(suffix=''):
    cur_time = time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())
    temp_filename = str(uuid.uuid4())

    return f"uploaded_files/{cur_time}-{temp_filename}{suffix}"