from twitchAPI.helper import first
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.type import AuthScope, ChatEvent, CustomRewardRedemptionStatus
from twitchAPI.oauth import UserAuthenticationStorageHelper
from twitchAPI.twitch import Twitch
from twitchAPI.object.eventsub import ChannelPointsCustomRewardRedemptionAddEvent
from enum import Enum

from dotenv import load_dotenv
import os
import asyncio

if not os.path.exists(".env"):
    print (".env file not found!")
    exit(1)

load_dotenv()

from modules import ytm_integration

class ClientInfo(str, Enum):
    ID = os.getenv("CLIENT_ID")
    SECRET = os.getenv("CLIENT_SECRET")
    SCOPE = [AuthScope.CHAT_READ, AuthScope.MODERATOR_READ_CHAT_MESSAGES, AuthScope.CHANNEL_READ_REDEMPTIONS, AuthScope.CHANNEL_MANAGE_REDEMPTIONS]

class RedemptionEvent(str, Enum):
    SONG_REQUEST = os.getenv("YTM_SONG_REQUEST_EVENT_NAME")
    SKIP_SONG = os.getenv("YTM_SKIP_SONG_EVENT_NAME")

def log(message: str, onlyFormat = False) -> str:
    message = f"[MAIN] {message}"
    if not onlyFormat: print(message)
    return message

async def run():
    # AUTHENTICATION
    twitch = await Twitch(ClientInfo.ID, ClientInfo.SECRET)
    helper = UserAuthenticationStorageHelper(twitch, ClientInfo.SCOPE)
    await helper.bind()

    user = await first(twitch.get_users())
    eventSub = EventSubWebsocket(twitch)
    eventSub.start() # THIS HAS TO BE STARTED OUTRIGHT

    await eventSub.listen_channel_points_custom_reward_redemption_add(user.id, onChannelRedemption)

    try: input(log("Program initialized succesfully.\nPress Enter to exit...\n", True))
    finally:
        await eventSub.stop()
        await twitch.close()

async def onChannelRedemption(event: ChannelPointsCustomRewardRedemptionAddEvent):
    log (f"Redemption event received: {event.event.reward.title} by {event.event.user_name}: {event.event.user_input}")
    match event.event.reward.title:
        case RedemptionEvent.SONG_REQUEST: ytm_integration.SongInsert(event.event.user_input)
        case RedemptionEvent.SKIP_SONG: ytm_integration.SongSkip()

asyncio.run(run())