from twitchAPI.helper import first
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.type import AuthScope
from twitchAPI.oauth import UserAuthenticationStorageHelper
from twitchAPI.twitch import Twitch
from twitchAPI.object.eventsub import ChannelPointsCustomRewardRedemptionAddEvent
from twitchAPI.chat import Chat, ChatMessage
from twitchAPI.type import ChatEvent
from colorama import Fore, Back, Style
from modules.config import cfg
from modules import ytm_integration
import asyncio

SCOPES = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT, AuthScope.MODERATOR_READ_CHAT_MESSAGES, AuthScope.CHANNEL_READ_REDEMPTIONS]

def log(message: str, onlyFormat = False) -> str:
    message = f"{Style.BRIGHT}{Back.MAGENTA}[MAIN]{Style.RESET_ALL} {message}"
    if not onlyFormat: print(message)
    return message

async def run():
    # AUTHENTICATION
    twitch = await Twitch(cfg["client_id"], cfg["client_secret"])
    helper = UserAuthenticationStorageHelper(twitch, SCOPES)
    await helper.bind()

    user = await first(twitch.get_users())
    eventSub = EventSubWebsocket(twitch)
    eventSub.start() # THIS HAS TO BE STARTED OUTRIGHT
    await eventSub.listen_channel_points_custom_reward_redemption_add(user.id, onChannelRedemption)
    #await eventSub.listen_channel_chat_message(user.id, user.id, onChatMessage)

    chat = await Chat(twitch)
    chat.register_event(ChatEvent.MESSAGE, onChatMessage)
    chat.start()
    await chat.join_room(user.login)

    try:
        log("Program initialized succesfully. Press Enter to exit...")
        ytm_integration.Init()
        input()

    finally:
        await eventSub.stop()
        chat.stop()
        await twitch.close()

async def onChannelRedemption(event: ChannelPointsCustomRewardRedemptionAddEvent):
    log(f"Redemption event received: {Fore.GREEN}{event.event.reward.title}{Style.RESET_ALL} by {Fore.CYAN}{event.event.user_name}{Style.RESET_ALL}{f": {Fore.LIGHTMAGENTA_EX}" + event.event.user_input + Style.RESET_ALL if len(event.event.user_input) > 0 else "" }")
    if event.event.reward.title == cfg["redemption_events"]["song_request"]: ytm_integration.SongInsert(event.event.user_input)
    elif event.event.reward.title == cfg["redemption_events"]["song_skip"]: ytm_integration.SongSkip()
    else: log(f"Event {Fore.GREEN}{event.event.reward.title}{Style.RESET_ALL} is not associated with any action. Ignoring it.")

async def onChatMessage(msg: ChatMessage):
    text = msg.text.strip()
    if text.startswith(cfg["commands"]["song_info"]):
        await msg.reply(ytm_integration.SongInfoRequest())
    else: pass

asyncio.run(run())
