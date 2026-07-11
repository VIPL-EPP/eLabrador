import asyncio
import requests
import PIL.Image
import numpy as np
import io
import time
import json
import os

import websocket

url = "http://127.0.0.1:"+os.environ["NVI_HOST_PORT"]+"/mask2former/predict"

image = PIL.Image.open("test.png").convert("RGB")
image = np.array(image)
image = PIL.Image.fromarray(image)

times = list()

# predict test
for i in range(2):
    start = time.time()
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=50)
    response = requests.post(url, files={"image": buffer.getvalue()}, data={"return_probs": True})
    end = time.time()
    times.append(end-start)
    probs = np.load(io.BytesIO(response.content), allow_pickle=True)['arr_0'].reshape(65, image.size[1], image.size[0])
    mask = np.argmax(probs, axis=0)
    colored_img = np.zeros((mask.shape[0], mask.shape[1], 3), dtype=np.uint8)
    assert mask.shape[0]==image.size[1] and mask.shape[1]==image.size[0]

print("HTTP: average time: {:.3f}s, min time: {:.3f}s, max time: {:.3f}s".format(np.mean(times), np.min(times), np.max(times)))

# predict_ws test
uri = "ws://127.0.0.1:"+os.environ["NVI_HOST_PORT"]+"/mask2former/predict_ws"

times = list()  # reset times for WebSocket test
ws = websocket.WebSocket()
ws.connect(uri)
# check connection
for i in range(2):
    start = time.time()
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=50)
    ws.send(buffer.getvalue(), opcode=websocket.ABNF.OPCODE_BINARY)
    
    buffer = io.BytesIO()
    np.savez_compressed(buffer, return_probs=True)
    ws.send(buffer.getvalue(), opcode=websocket.ABNF.OPCODE_BINARY)

    response = ws.recv()
    end = time.time()
    times.append(end-start)
    buffer = io.BytesIO(response)
    response = np.load(buffer)
    probs = response['probs']
    assert probs.shape[0]==65

print("WebSocket: average time: {:.3f}s, min time: {:.3f}s, max time: {:.3f}s".format(np.mean(times), np.min(times), np.max(times)))