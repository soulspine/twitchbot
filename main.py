from twitchAPI.helper import first
from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.oauth import UserAuthenticationStorageHelper
from twitchAPI.twitch import Twitch
from twitchAPI.object.eventsub import ChannelPointsCustomRewardRedemptionAddEvent

from dotenv import load_dotenv
import os
import asyncio

if not os.path.exists(".env"):
    print (".env file not found!")
    os._exit(1)

load_dotenv()

from modules import ytm_integration

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
CLIENT_SCOPE = [AuthScope.CHAT_READ, AuthScope.MODERATOR_READ_CHAT_MESSAGES, AuthScope.CHANNEL_READ_REDEMPTIONS]

async def run():
    # AUTHENTICATION
    twitch = await Twitch(CLIENT_ID, CLIENT_SECRET)
    helper = UserAuthenticationStorageHelper(twitch, CLIENT_SCOPE)
    await helper.bind()

    user = await first(twitch.get_users())
    eventSub = EventSubWebsocket(twitch)
    eventSub.start() # THIS HAS TO BE STARTED OUTRIGHT

    await eventSub.listen_channel_points_custom_reward_redemption_add(user.id, ytm_integration.on_point_reward)

    try: input("[MAIN] Program initialized succesfully.\nPress Enter to exit...\n")
    finally:
        await eventSub.stop()
        await twitch.close()

asyncio.run(run())