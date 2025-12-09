from twitchAPI.helper import first
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.type import AuthScope, CustomRewardRedemptionStatus
from twitchAPI.oauth import UserAuthenticationStorageHelper
from twitchAPI.twitch import Twitch
from twitchAPI.object.eventsub import ChannelPointsCustomRewardRedemptionAddEvent
from twitchAPI.object.api import TwitchUser
from twitchAPI.chat import Chat, ChatMessage
from twitchAPI.type import ChatEvent
from colorama import Fore, Back, Style
from modules.config import cfg
from modules import ytm_integration
import asyncio
import re

SCOPES = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT, AuthScope.MODERATOR_READ_CHAT_MESSAGES, AuthScope.CHANNEL_READ_REDEMPTIONS, AuthScope.CHANNEL_MANAGE_REDEMPTIONS]

def log(message: str):
    message = f"{Style.BRIGHT}{Back.MAGENTA}[MAIN]{Style.RESET_ALL} {message}"
    print(message)

def logError(message:str):
    log(f"{Style.BRIGHT}{Back.RED}[ERROR]{Style.RESET_ALL} {Fore.LIGHTRED_EX}{message}{Style.RESET_ALL}")

twitch:Twitch = None
chat:Chat = None
user:TwitchUser = None

async def run():
    global chat, twitch, user
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

    allRewards = await twitch.get_custom_reward(broadcaster_id=user.id, only_manageable_rewards=False)
    allTitles = [r.title for r in allRewards]
    manageableRewards = await twitch.get_custom_reward(broadcaster_id=user.id, only_manageable_rewards=True)
    manageableTitles = [mr.title for mr in manageableRewards]

    # this is here because an app can only manage events that have been created by this specific app
    for event in cfg["redemption_events"].values():
        # if event is in manageable, skip
        if event in manageableTitles: 
            log (f"Redemption reward \"{event}\" confirmed as manageable.")
            continue
        
        #event is already there so app cannot app its own
        if event in allTitles:
            logError(f"Reward \"{event}\" already exists. Please remove it, then let the program add it by running it again. After doing that, modify the newly added reward using twitch's panel (https://dashboard.twitch.tv/u/{user.login}/viewer-rewards/channel-points/rewards). Otherwise program won't be able to mark redemptions as completed or refund them.")
            continue

        log(f"Creating redemption reward \"{event}\". Setting it to un-claimable. Modify it in twitch's panel (https://dashboard.twitch.tv/u/{user.login}/viewer-rewards/channel-points/rewards).")

        newReward = await twitch.create_custom_reward(
            broadcaster_id=user.id,
            title=event,
            cost=1,
            is_enabled=False
        )

        log(f"New redemption reward created with id {newReward.id}.")

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
    status = CustomRewardRedemptionStatus.CANCELED
    if event.event.reward.title == cfg["redemption_events"]["song_request"]:
        out = ytm_integration.SongInsert(event.event.user_input)
        if out is not None:
            status = CustomRewardRedemptionStatus.FULFILLED
            song, sequenceId = out
            await chat.send_message(event.event.broadcaster_user_login, f"{song} was added to the queue. Its position is {sequenceId}.")
        else:
            await chat.send_message(event.event.broadcaster_user_login, f"Something went wrong.")
    elif event.event.reward.title == cfg["redemption_events"]["song_skip"]:
        if ytm_integration.SongSkip():
            status = CustomRewardRedemptionStatus.FULFILLED
    else:
        log(f"Event {Fore.GREEN}{event.event.reward.title}{Style.RESET_ALL} is not associated with any action. Ignoring it.")
        return
    
    try:
        await twitch.update_redemption_status(
            event.event.broadcaster_user_id,
            event.event.reward.id,
            [event.event.id],
            status
        )

        log(f"Marked {Fore.GREEN}{event.event.reward.title}{Style.RESET_ALL} redeemed by {Fore.CYAN}{event.event.user_name}{Style.RESET_ALL} as {Fore.LIGHTMAGENTA_EX}{str(status).replace('CustomRewardRedemptionStatus.', '')}{Style.RESET_ALL}")
    except: pass

async def onChatMessage(msg: ChatMessage):
    text = msg.text.strip()
    if cfg["commands"]["song_info"] in text:
        await msg.reply(ytm_integration.SongInfoRequest())
    elif cfg["commands"]["queue_info"] in text:
        n = int(re.search(r'\d+', text).group()) if re.search(r'\d+', text) else 10
        responses = ytm_integration.QueueInfoRequest(n)
        for r in responses:
            await msg.reply(r)
    else: pass

asyncio.run(run())
