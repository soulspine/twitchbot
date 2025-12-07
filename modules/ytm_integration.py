import requests
import os
from enum import Enum
import websockets
import asyncio
import json
import time
import threading
from colorama import Fore, Back, Style
from modules.config import cfg
from twitchAPI.chat import ChatMessage

def log(message: str):
    print(f"{Style.BRIGHT}{Back.RED}{Fore.WHITE}[YTM]{Style.RESET_ALL} " + message)

class QueueItem():
    def __init__(self, videoId: str, title: str, author: str, youtubeMusicId: str = ""):
        self.VideoId = videoId
        self.Title = title
        self.Author = author
        self.YoutubeMusicId = youtubeMusicId
    
    def __repr__(self):
        return f"\"{self.Title}\" by {self.Author} ({self.VideoId})"

class ApiHandler:
    class SocketMessage(str, Enum):
        PLAYER_POSITION_CHANGED = "POSITION_CHANGED"
        VIDEO_CHANGED = "VIDEO_CHANGED"
        REPEAT_MODE_CHANGED = "REPEAT_CHANGED"
        SHUFFLE_MODE_CHANGED = "SHUFFLE_CHANGED"

    class Method(str, Enum):
        GET = "GET"
        POST = "POST"
        DELETE = "DELETE"
        PATCH = "PATCH"


    _base_url = f"{cfg["youtube_music"]["host"]}:{cfg["youtube_music"]["port"]}/"
    _api_url = f"{_base_url}api/v1/"
    _session = requests.Session()
    _socket = None

    @classmethod
    def Request(cls, method: str, endpoint: str, data: dict = None):
        return cls._session.request(method, f"http://{cls._api_url}{endpoint}", json=data)

    @classmethod
    def IsConnected(cls) -> bool:
        try:
            r = cls.Request(ApiHandler.Method.GET, "song")
            return r.status_code == 200
        except:
            return False

    @classmethod
    async def Authenticate(cls):
        try:
            r = requests.request(ApiHandler.Method.POST, f"http://{cls._base_url}auth/twitchbot")
            if not r.status_code == 200:
                raise()
        except Exception as e:
                log(f"Failed to authenticate with YTM API. Retrying in {cfg["youtube_music"]["connection_retry_time"]} seconds.")
                return
        
        header = {"Authorization": f"Bearer {r.json()['accessToken']}"}
        cls._session.headers.update(header)
        cls._socket = await websockets.connect(f"ws://{cls._api_url}ws", additional_headers=header)
        asyncio.create_task(cls._socketListener())

        log("Authenticated with YTM API.")

    @classmethod
    async def _socketListener(cls):
        async with cls._socket as ws:
            while True:
                try:
                    msg = await ws.recv()
                    
                    msg = json.loads(msg)
                    match msg.get("type"):
                        case cls.SocketMessage.VIDEO_CHANGED:
                            song = msg.get("song")
                            videoId = song.get("videoId")
                            
                            if len(twitchQueue) == 0: return

                            if videoId == twitchQueue[0].VideoId or videoId == twitchQueue[0].YoutubeMusicId:
                                twitchQueue.pop(0)
                            else: # playlist must have been changed manually
                                log("Playlist was changed and queue cleared. Repopulating it with song requests.")
                                queueLen = len(twitchQueue)
                                for i in range(queueLen):
                                    SongInsert(f"https://www.youtube.com/watch?v={twitchQueue[i].VideoId}", True, queueLen - i - 1)




                except websockets.ConnectionClosed:
                    log("Lost connection to YTM API")
                    break
                except Exception as e:
                    log(f"WebSocket error")
                    break

twitchQueue: list[QueueItem] = []

def getQueue() -> tuple[list[QueueItem], int | None] | None:
    if not ApiHandler.IsConnected():
        log("Not connected to YTM API.")
        return None

    r = ApiHandler.Request(
        method=ApiHandler.Method.GET,
        endpoint="queue"
    )

    if r.status_code != 200:
        log(f"Failed to get queue with status code {r.status_code}.")
        return None

    outList = []
    currentIndex = None
    for item in r.json().get("items", []):
        base = None

        youtubeMusicId = None

        if item.get("playlistPanelVideoRenderer"):
            base = item["playlistPanelVideoRenderer"]
        elif item.get("playlistPanelVideoWrapperRenderer"):
            base = item["playlistPanelVideoWrapperRenderer"]["primaryRenderer"]["playlistPanelVideoRenderer"]
            youtubeMusicId = item["playlistPanelVideoWrapperRenderer"]["counterpart"][0]["counterpartRenderer"]["playlistPanelVideoRenderer"]["videoId"]

        if base:
            outList.append(QueueItem(
                base["videoId"],
                base["title"]["runs"][0]["text"],
                base["longBylineText"]["runs"][0]["text"],
                youtubeMusicId
            ))
            if base.get("selected"):
                currentIndex = len(outList) - 1


    return outList, currentIndex

def isYoutubeURL(url: str) -> bool:
    return url.startswith("https://www.youtube.com/watch?v=") \
    or url.startswith("https://youtu.be/") \
    or url.startswith("https://music.youtube.com/watch?v=")

def getYoutubeID(url: str) -> str:
    pos = 0
    if url.startswith("https://www.youtube.com/watch?v="):
        pos = len("https://www.youtube.com/watch?v=")
    elif url.startswith("https://youtu.be/"):
        pos = len("https://youtu.be/")
    elif url.startswith("https://music.youtube.com/watch?v="):
        pos = len("https://music.youtube.com/watch?v=")
    
    return url[pos:pos+11]

def SongInsert(url, noTwitchQueueUpdate = False, overrideShift = None):
    if not ApiHandler.IsConnected():
        log("Not connected to Youtube Music API. Skipping song insert request.")
        return
    
    if not isYoutubeURL(url):
        log(f"Invalid URL was provided: {url}. Skipping song insert request.")
        # TODO: Add refund here
        return

    videoId = getYoutubeID(url)

    insertRequest = ApiHandler.Request(
        method=ApiHandler.Method.POST,
        endpoint="queue",
        data={
            "videoId": videoId,
            "insertPosition": "INSERT_AFTER_CURRENT_VIDEO",
        }
    )

    if insertRequest.status_code != 204:
        log(f"Failed to insert {videoId} into song queue with status code {insertRequest.status_code}.")
        # TODO: Add refund here too
        return

    time.sleep(2) # Wait a bit for the queue to update

    queue, currentIndex = getQueue()
    if queue:
        log(f"Succesfully inserted {queue[currentIndex + 1]} into song queue.")

    if not noTwitchQueueUpdate:
        twitchQueue.append(queue[currentIndex + 1])

    shift = len(twitchQueue)
    if overrideShift is not None:
        shift = shift - overrideShift

    if shift > 0:
        ApiHandler.Request(ApiHandler.Method.PATCH,
            endpoint=f"queue/{currentIndex + 1}",
            data={
                "toIndex": currentIndex + shift
            }
        )

def SongSkip():
    if not ApiHandler.IsConnected():
        log("Not connected to Youtube Music API. Skipping song skip request.")
        return

    playerInfoRequest = ApiHandler.Request(
        method=ApiHandler.Method.GET,
        endpoint="song"
    )

    if not playerInfoRequest.status_code == 200:
        log(f"Failed to get player info with status code {playerInfoRequest.status_code}.")
        return

    isPlaying = not playerInfoRequest.json()["isPaused"]
    
    if not isPlaying:
        log("Music is paused, not skipping.")
        return

    skipRequest = ApiHandler.Request(
        method=ApiHandler.Method.POST,
        endpoint="next"
    )

    if skipRequest.status_code == 204:
        log("Succesfully skipped current song.")

    else:
        log(f"Failed to skip current song with status code {skipRequest.status_code}.")

async def SongInfoRequest(ctx:ChatMessage):
    if not ApiHandler.IsConnected():
        log("Not connected to Youtube Music API. Skipping song info request.")
        await ctx.reply("Nothing playing at the moment")
        return
    
    infoRequest = ApiHandler.Request(
        method=ApiHandler.Method.GET,
        endpoint="song"
    )

    data = infoRequest.json()

    if infoRequest.status_code != 200 or data["isPaused"]:
        await ctx.reply("Nothing playing at the moment")
    else:
        await ctx.reply(f"\"{data["title"]}\" by {data["artist"]} - https://youtu.be/{data["videoId"]}")

def start_api_handler_thread():
    def _thread_func():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _check_loop():
            await ApiHandler.Authenticate()
            while True:
                await asyncio.sleep(cfg["youtube_music"]["connection_retry_time"])
                if not ApiHandler.IsConnected():
                    await ApiHandler.Authenticate()

        loop.run_until_complete(_check_loop())

    threading.Thread(target=_thread_func, daemon=True).start()

start_api_handler_thread()