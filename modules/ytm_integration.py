from twitchAPI.object.eventsub import ChannelPointsCustomRewardRedemptionAddEvent
import requests
import os

YTM_HOST = os.getenv("YTM_HOST")
YTM_PORT = os.getenv("YTM_PORT")

SONG_REQUEST_EVENT_NAME = os.getenv("SONG_REQUEST_EVENT_NAME")

POST = "POST"
GET = "GET"
PATCH = "PATCH"
DELETE = "DELETE"

base_url = f"http://{YTM_HOST}:{YTM_PORT}/"
base_url_api = f"{base_url}api/v1/"

session = requests.Session()

def log(message: str):
    print("[YTM] " + message)

def api_request(method: str, endpoint: str, data: dict = None):
    return session.request(
        method = method,
        url = base_url_api + endpoint,
        json = data,
    )


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

def try_insert_song(url: str) -> bool:
    succeeded = False

    if isYoutubeURL(url):
        r = api_request(
            method=POST,
            endpoint="queue",
            data={
                "videoId": getYoutubeID(url),
                "insertPosition": "INSERT_AFTER_CURRENT_VIDEO",
            }
        )

        if r.status_code == 204: succeeded = True
    
    log((f"Succesfully inserted" if succeeded else "Failed to insert") + f" {getYoutubeID(url)} into song queue.")
    return succeeded

async def on_point_reward(event: ChannelPointsCustomRewardRedemptionAddEvent):
    if event.event.reward.title == SONG_REQUEST_EVENT_NAME:
        log(f"Received song request from {event.event.user_name}: {event.event.user_input}")
        try_insert_song(event.event.user_input)