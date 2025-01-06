import requests
import mimetypes
import os
import magika
import pathlib
import json
from typing import *
from PIL import Image
import datetime
import pytz
import aiohttp
import asyncio
import colorama
import time
import cv2
import io
import aiohttp
from assorted_utils import generate_random_string, extract_html_metadata_tag
import discord
from discord.ext import commands
import re

STYLE = colorama.Style
RESET = STYLE.RESET_ALL

BRIGHT = STYLE.BRIGHT
DIM = STYLE.DIM
NORMAL = STYLE.NORMAL

FORE = colorama.Fore

BLACK = FORE.BLACK
BLUE = FORE.BLUE
CYAN = FORE.CYAN
GREEN = FORE.GREEN
MAGENTA = FORE.MAGENTA
RED = FORE.RED
OFFWHITE = FORE.WHITE
WHITE = FORE.LIGHTWHITE_EX
GOLD = FORE.YELLOW
GREY = FORE.LIGHTBLACK_EX
YELLOW = FORE.LIGHTYELLOW_EX
PINK = FORE.LIGHTMAGENTA_EX

LBLUE = FORE.LIGHTBLUE_EX
LCYAN = FORE.LIGHTCYAN_EX
LGREEN = FORE.LIGHTGREEN_EX
LRED = FORE.LIGHTRED_EX

magic = magika.Magika()
videos_path = ""


class BlueskyImage:
    def __init__(self, file_path: str, upload: bool = False):
        self.file_path = file_path
        self.uploaded = False
        self.data = {}
        self.width: int = 0
        self.height: int = 0
        self.aspect_ratio_set = False
        if upload:
            self._upload()

    def _set_aspect_ratio(self):
        if self.aspect_ratio_set:
            return
        
        img = Image.open(self.file_path)
        self.width, self.height = img.size
        img.close()
        
        self.aspect_ratio_set = True

    def _upload(self):
        if self.uploaded:
            return
        mime_type = magic.identify_path(pathlib.Path(self.file_path)).output.mime_type
        url = "https://ganoderma.us-west.host.bsky.network/xrpc/com.atproto.repo.uploadBlob"
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "atproto-accept-labelers": "",
            "authorization": "",
            "cache-control": "no-cache",
            "content-type": mime_type,
            "pragma": "no-cache",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"130\", \"Opera GX\";v=\"115\", \"Not?A_Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "Referer": "https://bsky.app/",
            "Referrer-Policy": "origin-when-cross-origin"
        }

        try:
            with open(self.file_path, 'rb') as file:
                response = requests.post(url, headers=headers, data=file)
                response.raise_for_status()
                self.data = response.json()
                self.uploaded = True
        except Exception as e:
            print("An error occurred:", e)

    def _to_data(self):
        if not self.uploaded:
            self._upload()
        if not self.aspect_ratio_set:
            self._set_aspect_ratio()
        
        new_data = {
            "image": self.data["blob"],
            "alt": "",
            "aspectRatio": {"width": self.width, "height": self.height}
        }
        
        return new_data

class AsyncBlueskyImage:
    def __init__(self, file_path: str | io.BytesIO):
        self.file_path = file_path
        self.uploaded = False
        self.data = {}
        self.width: int = 0
        self.height: int = 0
        self.aspect_ratio_set = False

    def _set_aspect_ratio(self):
        if self.aspect_ratio_set:
            return
        
        img = Image.open(self.file_path)
        self.width, self.height = img.size
        img.close()
        
        self.aspect_ratio_set = True

    def _upload(self):
        self._set_aspect_ratio()
        if self.uploaded:
            return
        if isinstance(self.file_path, str):
            mime_type = magic.identify_path(pathlib.Path(self.file_path)).output.mime_type
        else:
            self.file_path.seek(0)
            mime_type = magic.identify_bytes(self.file_path.getvalue()).output.mime_type
        url = "https://ganoderma.us-west.host.bsky.network/xrpc/com.atproto.repo.uploadBlob"
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "atproto-accept-labelers": "",
            "authorization": "",
            "cache-control": "no-cache",
            "content-type": mime_type,
            "pragma": "no-cache",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"130\", \"Opera GX\";v=\"115\", \"Not?A_Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "Referer": "https://bsky.app/",
            "Referrer-Policy": "origin-when-cross-origin"
        }

        try:
            upload_bytes: io.BytesIO = None
            if isinstance(self.file_path, str):
                with open(self.file_path, 'rb') as f:
                    upload_bytes = io.BytesIO(f.read())
            else:
                upload_bytes = self.file_path
            
            response = requests.post(url, headers=headers, data=upload_bytes.getvalue())
            response.raise_for_status()
            self.data = response.json()
            self.uploaded = True
        except Exception as e:
            print("An error occurred:", e)

    async def _to_data(self):
        if not self.uploaded:
            await asyncio.get_event_loop().run_in_executor(None, self._upload)
        if not self.aspect_ratio_set:
            self._set_aspect_ratio()
        
        new_data = {
            "image": self.data["blob"],
            "alt": "",
            "aspectRatio": {"width": self.width, "height": self.height}
        }
        
        return new_data

class BlueskyVideo:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_name = file_path.split("/")[-1]
        self.began_upload = False
        self.finished_upload = False
        self.ready = False
        self.data = {}
        self.job_id: str = None
        self.state: str = None
        self.message: str = None
        self.width: int = 0
        self.height: int = 0
        self.aspect_ratio_set = False
    
    def _set_aspect_ratio(self):
        if self.aspect_ratio_set:
            return

        video = cv2.VideoCapture(self.file_path)
        
        width = video.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = video.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        video.release()
        
        self.width = int(width)
        self.height = int(height)
        self.aspect_ratio_set = True
    
    def _update_job_state(self, data: dict):
        if self.finished_upload:
            return
        possible_job_states = [
            "JOB_STATE_CREATED",
            "JOB_STATE_ENCODING", # has `progress` integer
            "JOB_STATE_SCANNING",
            "JOB_STATE_SCANNED",
            "JOB_STATE_COMPLETED" # has full data: `blob` contains the video data needed for upload, `message` contains a message
        ]
        self.job_id = data["jobId"]
        self.state = data["state"]
        
        printmsg = f"{CYAN}[{RESET}{PINK}BlueskyUploadJob{RESET}{CYAN}]{RESET}{WHITE}:{RESET}{RED}{self.job_id}{RESET}{WHITE}-{RESET}{GREEN}{self.state}{RESET}"
        
        if self.state == "JOB_STATE_COMPLETED":
            self.data = data["blob"]
            self.message = data["message"]
            self.finished_upload = True
            printmsg += f"{WHITE}:{RESET}{MAGENTA}{self.message}{RESET}"
        elif self.state == "JOB_STATE_ENCODING":
            progress = data.get("progress", 0)
            printmsg += f"{WHITE}:{RESET}{MAGENTA}{progress}{RESET}"
        print(printmsg)
    
    def _fetch_update_job_status(self):
        url = f"https://video.bsky.app/xrpc/app.bsky.video.getJobStatus?jobId={self.job_id}"
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "atproto-accept-labelers": "",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"130\", \"Opera GX\";v=\"115\", \"Not?A_Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "Referer": "https://bsky.app/",
            "Referrer-Policy": "origin-when-cross-origin"
        }
        self._update_job_state(requests.get(url=url, headers=headers).json()["jobStatus"])
    
    def _upload(self):
        if self.began_upload:
            return
        mime_type = magic.identify_path(pathlib.Path(self.file_path)).output.mime_type
        url = f"https://video.bsky.app/xrpc/app.bsky.video.uploadVideo?did=&name={self.file_name}"
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "authorization": "",
            "cache-control": "no-cache",
            "content-type": mime_type,
            "pragma": "no-cache",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"130\", \"Opera GX\";v=\"115\", \"Not?A_Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "Referer": "https://bsky.app/",
            "Referrer-Policy": "origin-when-cross-origin"
        }
        
        try:
            with open(self.file_path, 'rb') as file:
                response = requests.post(url, headers=headers, data=file)
                response.raise_for_status()
                self.began_upload = True
                data = response.json()
                self._update_job_state(data)

            while not self.finished_upload:
                time.sleep(5)
                self._fetch_update_job_status()
        except Exception as e:
            print("An error occurred:", e)
    
    def _to_data(self):
        if not self.began_upload:
            self._upload()
        while not self.finished_upload:
            time.sleep(1)
        if not self.aspect_ratio_set:
            self._set_aspect_ratio()
        
        new_data = {
            "video": self.data["blob"],
            "aspectRatio": {"width": self.width, "height": self.height}
        }
        
        return new_data

class AsyncBlueskyVideo:
    def __init__(self, file_path: str = None, bytesio_obj: io.BytesIO = None):
        if file_path is None and bytesio_obj is None:
            raise NoContentException()
        if file_path is None and bytesio_obj is not None:
            file_path = videos_path + "eepyfemboi_" + generate_random_string(5) + ".mp4"
            with open(file_path, "wb") as f:
                f.write(bytesio_obj.getvalue())
        self.file_path = file_path
        self.file_name = file_path.split("/")[-1]
        self.began_upload = False
        self.finished_upload = False
        self.ready = False
        self.data = {}
        self.job_id: str = None
        self.state: str = None
        self.message: str = None
        self.width: int = 0
        self.height: int = 0
        self.aspect_ratio_set = False
    
    def _set_aspect_ratio(self):
        if self.aspect_ratio_set:
            return

        video = cv2.VideoCapture(self.file_path)
        
        width = video.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = video.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        video.release()
        
        self.width = int(width)
        self.height = int(height)
        self.aspect_ratio_set = True
    
    def _update_job_state(self, data: dict):
        if self.finished_upload:
            return
        possible_job_states = [
            "JOB_STATE_CREATED",
            "JOB_STATE_ENCODING", # has `progress` integer
            "JOB_STATE_SCANNING",
            "JOB_STATE_SCANNED",
            "JOB_STATE_COMPLETED" # has full data: `blob` contains the video data needed for upload, `message` contains a message
        ]
        self.job_id = data["jobId"]
        self.state = data["state"]
        
        printmsg = f"{CYAN}[{RESET}{PINK}BlueskyUploadJob{RESET}{CYAN}]{RESET}{WHITE}:{RESET}{RED}{self.job_id}{RESET}{WHITE}-{RESET}{GREEN}{self.state}{RESET}"
        
        if self.state == "JOB_STATE_COMPLETED":
            self.data = data["blob"]
            self.message = data["message"]
            self.finished_upload = True
            printmsg += f"{WHITE}:{RESET}{MAGENTA}{self.message}{RESET}"
        elif self.state == "JOB_STATE_ENCODING":
            progress = data.get("progress", 0)
            printmsg += f"{WHITE}:{RESET}{MAGENTA}{progress}{RESET}"
        print(printmsg)
    
    def _fetch_update_job_status(self):
        url = f"https://video.bsky.app/xrpc/app.bsky.video.getJobStatus?jobId={self.job_id}"
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "atproto-accept-labelers": "",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"130\", \"Opera GX\";v=\"115\", \"Not?A_Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "Referer": "https://bsky.app/",
            "Referrer-Policy": "origin-when-cross-origin"
        }
        self._update_job_state(requests.get(url=url, headers=headers).json()["jobStatus"])
    
    def _upload(self):
        self._set_aspect_ratio()
        if self.began_upload:
            return
        mime_type = magic.identify_path(pathlib.Path(self.file_path)).output.mime_type
        url = f"https://video.bsky.app/xrpc/app.bsky.video.uploadVideo?did=&name={self.file_name}"
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "authorization": "",
            "cache-control": "no-cache",
            "content-type": mime_type,
            "pragma": "no-cache",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"130\", \"Opera GX\";v=\"115\", \"Not?A_Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "Referer": "https://bsky.app/",
            "Referrer-Policy": "origin-when-cross-origin"
        }
        
        try:
            with open(self.file_path, 'rb') as file:
                response = requests.post(url, headers=headers, data=file)
                response.raise_for_status()
                self.began_upload = True
                data = response.json()
                self._update_job_state(data)

            while not self.finished_upload:
                time.sleep(5)
                self._fetch_update_job_status()
        except Exception as e:
            print("An error occurred:", e)
    
    async def _to_data(self):
        if not self.began_upload:
            await asyncio.get_event_loop().run_in_executor(None, self._upload)
        while not self.finished_upload:
            await asyncio.sleep(1)
        if not self.aspect_ratio_set:
            self._set_aspect_ratio()
        
        new_data = {
            "video": self.data["blob"],
            "aspectRatio": {"width": self.width, "height": self.height}
        }
        
        return new_data

class MultipleFileTypeException(Exception):
    def __init__(self):
        self.message = "A BlueSky post cannot have both an image and a video."
        super().__init__(self.message)

class NoContentException(Exception):
    def __init__(self):
        self.message = "A BlueSky post must have some sort of content."
        super().__init__(self.message)

class TooManyFilesException(Exception):
    def __init__(self):
        self.message = "A BlueSky post can contain up to 4 images."
        super().__init__(self.message)

def send_bluesky_post(
            text: str = None, 
            images: List[BlueskyImage] = None, 
            video: BlueskyVideo = None
        ):
    # checks
    if (images is not None and len(images) > 0) and (video is not None):
        raise MultipleFileTypeException()
    
    has_file = False
    if (images is not None and len(images) > 0) or (video is not None):
        has_file = True
    
    if (text is None or text.strip() == "") and not has_file:
        raise NoContentException()
    
    if images is not None and len(images) > 4:
        raise TooManyFilesException()
    
    url = "https://ganoderma.us-west.host.bsky.network/xrpc/com.atproto.repo.applyWrites"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "atproto-accept-labelers": "",
        "authorization": "",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "sec-ch-ua": "\"Chromium\";v=\"130\", \"Opera GX\";v=\"115\", \"Not?A_Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "Referer": "https://bsky.app/",
        "Referrer-Policy": "origin-when-cross-origin"
    }
    
    
    body = {
        "repo": "",
        "writes": [
            {
                "$type": "com.atproto.repo.applyWrites#create",
                "collection": "app.bsky.feed.post",
                "rkey": "",
                "value": {
                    "$type": "app.bsky.feed.post",
                    "langs": ["en"]
                }
            }
        ],
        "validate": True
    }
    
    if text is not None and text.strip() != "":
        body["writes"]["value"]["text"] = text
    
    if images is not None and len(images) > 0:
        embed_data = {
            "$type": "app.bsky.embed.images",
            "images": []
        }
        for image in images:
            embed_data["images"].append(image._to_data())
        
        body["writes"]["value"]["embed"] = embed_data
    if video is not None:
        embed_data = {
            "$type": "app.bsky.embed.video",
            "video": video._to_data()
        }
        
        body["writes"]["value"]["embed"] = embed_data

    body["writes"]["value"]["createdAt"] = datetime.datetime.now(pytz.timezone('UTC')).isoformat()

    try:
        response = requests.post(url, headers=headers, data=json.dumps(body))
        response.raise_for_status()
        print("Request successful:", response.json())
    except Exception as e:
        print("An error occurred:", e)

async def async_send_bluesky_post(
            text: str = None, 
            images: List[AsyncBlueskyImage] = None, 
            video: AsyncBlueskyVideo = None
        ):
    # checks
    if (images is not None and len(images) > 0) and (video is not None):
        raise MultipleFileTypeException()
    
    has_file = False
    if (images is not None and len(images) > 0) or (video is not None):
        has_file = True
    
    if (text is None or text.strip() == "") and not has_file:
        raise NoContentException()
    
    if images is not None and len(images) > 4:
        raise TooManyFilesException()
    
    url = "https://ganoderma.us-west.host.bsky.network/xrpc/com.atproto.repo.applyWrites"
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "atproto-accept-labelers": "",
        "authorization": "",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "sec-ch-ua": "\"Chromium\";v=\"130\", \"Opera GX\";v=\"115\", \"Not?A_Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "Referer": "https://bsky.app/",
        "Referrer-Policy": "origin-when-cross-origin"
    }
    
    
    body = {
        "repo": "",
        "writes": [
            {
                "$type": "com.atproto.repo.applyWrites#create",
                "collection": "app.bsky.feed.post",
                "rkey": "",
                "value": {
                    "$type": "app.bsky.feed.post",
                    "langs": ["en"]
                }
            }
        ],
        "validate": True
    }
    
    if text is not None and text.strip() != "":
        body["writes"]["value"]["text"] = text
    
    if images is not None and len(images) > 0:
        embed_data = {
            "$type": "app.bsky.embed.images",
            "images": []
        }
        for image in images:
            data = await image._to_data()
            embed_data["images"].append(data)
        
        body["writes"]["value"]["embed"] = embed_data
    if video is not None:
        data = await video._to_data()
        embed_data = {
            "$type": "app.bsky.embed.video",
            "video": data
        }
        
        body["writes"]["value"]["embed"] = embed_data

    body["writes"]["value"]["createdAt"] = datetime.datetime.now(pytz.timezone('UTC')).isoformat()

    try:
        response = await asyncio.get_event_loop().run_in_executor(None, lambda: requests.post(url, headers=headers, data=json.dumps(body)))
        response.raise_for_status()
        print("Request successful:", response.json())
    except Exception as e:
        print("An error occurred:", e)


class AutoReUploadCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.loop = bot.loop

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id != 1325934249378975858:
            return
        if message.author.id != 1174332637322674186:
            return
        if message.content is None or message.content.strip() == "":
            return
        if "[⤵]" not in message.content:
            print("e")
            return
        
        def _inner():
            nonlocal message
            #text_content = ""
            has_video = False
            has_image = False
            
            url = message.content.split("[⤵]")[-1].replace("(", "").replace(")", "")
            response = requests.get(url)
            data = response.text
            if "og:video" in data:
                has_video = True
            elif "og:image" in data and not "pbs.twimg.com/profile_images" in data:
                has_image = True
            
            
            text_content = extract_html_metadata_tag("og:description")
            if text_content is None or text_content.strip() == "":
                text_content = ""
            
            if len(text_content) > 300: #truncate posts that might be longer than the limit
                text_content = text_content[:297] + "..."
            
            if has_video:
                video_url = extract_html_metadata_tag("og:video", data)
                video_data = io.BytesIO(requests.get(video_url).content)
                video_object = AsyncBlueskyVideo(bytesio_obj=video_data)
                return {
                    "text": text_content,
                    "has_file": True,
                    "file_type": "video",
                    "file": video_object
                }
            elif has_image:
                image_url = extract_html_metadata_tag("og:image", data)
                image_data = io.BytesIO(requests.get(image_url).content)
                image_object = AsyncBlueskyImage(image_data)
                return {
                    "text": text_content,
                    "has_file": True,
                    "file_type": "image",
                    "file": image_object
                }
            else:
                return {
                    "text": text_content,
                    "has_file": False
                }

        result = await self.loop.run_in_executor(None, _inner)
        if result["has_file"] is True:
            if result["file_type"] == "video":
                return await async_send_bluesky_post(text=result["text"], video=result["file"])
            return await async_send_bluesky_post(text=result["text"], images=[result["file"]])
        return await async_send_bluesky_post(text=result["text"])


