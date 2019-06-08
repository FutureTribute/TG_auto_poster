import telebot
import time
import pytz
import logging

try:
    import ujson as json
except ImportError:
    import json

from datetime import datetime
import concurrent.futures

logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

with open("config.json", "r") as file:
    config = json.load(file)

BOT_TOKEN = config["bot_token"]
ALLOWED_USERS = config["allowed_users"]
CHANNEL = config["channel"]
CHANNEL_USERNAME = config["channel_string"]  # Optional, make it "" if not needed
PICS_COUNT = config["pics_count"]
POSTING_HOURS = config["posting_hours"]

TEMP_PIC = None
TEMP_POST_ID = -1
SWITCHER = True
TZ = pytz.timezone("Europe/Kiev")

try:
    with open("data.json", "r") as file:
        DATA = json.load(file)
except OSError:
    DATA = []
    with open("data.json", "w") as file:
        json.dump(DATA, file)

bot = telebot.TeleBot(BOT_TOKEN, skip_pending=True)


# bot.enable_save_next_step_handlers(delay=2)
# bot.load_next_step_handlers()


def send_pics():
    while True:
        now = datetime.now(TZ).time()
        if SWITCHER and now.hour in POSTING_HOURS:
            print("Time:", now)
            poster()
            time.sleep(5400)  # experimental value
        else:
            time.sleep(60)  # experimental value


@bot.message_handler(content_types=["photo"])
def store_pic(message):
    if checker(message.chat.id):
        return
    if message.caption:
        global TEMP_PIC
        TEMP_PIC = {"id": message.photo[0].file_id, "caption": message.caption}
        msg = bot.send_message(message.chat.id, "Good. Now send the document.")
        bot.register_next_step_handler(msg, store_doc)
    else:
        bot.send_message(message.chat.id, "Picture without caption can't be stored.")


def store_doc(message):
    if message.document:
        if message.document.thumb:
            global TEMP_PIC, DATA
            TEMP_PIC["doc_id"] = message.document.file_id
            DATA.append(TEMP_PIC)
            with open("data.json", "w") as f:
                json.dump(DATA, f)
            TEMP_PIC = None
            bot.send_message(message.chat.id, "Successfully saved.")
        else:
            msg = bot.send_message(message.chat.id, "Not an image, try again.")
            bot.register_next_step_handler(msg, store_doc)
    elif message.text == "/cancel":
        bot.send_message(message.chat.id, "Operation canceled.")
    else:
        msg = bot.send_message(message.chat.id, "Not an image, try again.")
        bot.register_next_step_handler(msg, store_doc)


@bot.message_handler(commands=["all_posts"])  # NEED REWORK
def all_posts(message):
    if checker(message.chat.id):
        return
    if len(DATA) == 0:
        bot.send_message(message.chat.id, "You've run out of posts.")
    else:
        posts_string = "All posts:\n\n"
        posts_string += "\n".join(["{:03d}. {}".format
                                   (i, DATA[i]["caption"].replace("\n", " → ")) for i in range(len(DATA))])
        bot.send_message(message.chat.id, posts_string)


@bot.message_handler(commands=["posts_count"])
def posts_count(message):
    if checker(message.chat.id):
        return
    bot.send_message(message.chat.id, len(DATA))


@bot.message_handler(commands=["show_post"])
def show_post(message):
    if checker(message.chat.id):
        return
    try:
        post_id = int(message.text[11:])
        if post_id not in range(0, len(DATA)):
            raise IndexError
        pic = DATA[post_id]
        bot.send_photo(message.chat.id, photo=pic["id"], caption=pic["caption"])
        bot.send_document(message.chat.id, pic["doc_id"])
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "Incorrect usage, try again.")


@bot.message_handler(commands=["del_post"])
def del_post(message):
    if checker(message.chat.id):
        return
    try:
        post_id = int(message.text[10:])
        if post_id not in range(0, len(DATA)):
            raise IndexError
        global TEMP_POST_ID
        TEMP_POST_ID = post_id
        msg = bot.send_message(message.chat.id, "Are you sure that you want to delete post? [Yes]\n「{}」\n"
                                                "(be sure that bot haven't made posts in channel while you was here, "
                                                "making decision).".
                               format(DATA[TEMP_POST_ID]["caption"].replace("\n", " → ")))
        bot.register_next_step_handler(msg, del_step)
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "Incorrect usage, try again.")


def del_step(message):
    if message.text and message.text == "Yes":
        global TEMP_POST_ID
        try:
            DATA.pop(TEMP_POST_ID)
            with open("data.json", "w") as f:
                json.dump(DATA, f)
            TEMP_POST_ID = -1
            bot.send_message(message.chat.id, "Successfully deleted.")
        except IndexError:
            bot.send_message(message.chat.id, "Seems like it took so long for you to make a decision.")
    else:
        bot.send_message(message.chat.id, "Post deletion canceled.")


@bot.message_handler(commands=["edit_post"])
def edit_post(message):
    if checker(message.chat.id):
        return
    try:
        post_id = int(message.text[10:])
        if post_id not in range(0, len(DATA)):
            raise IndexError
        global TEMP_POST_ID
        TEMP_POST_ID = post_id
        msg = bot.send_message(message.chat.id, "Old caption (arrow is new line): 「{}」\nNow send a new one"
                                                "\n(be sure that bot haven't made posts in channel while you was here, "
                                                "making decision).".
                               format(DATA[TEMP_POST_ID]["caption"].replace("\n", " → ")))
        bot.register_next_step_handler(msg, edit_step)
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "Incorrect usage, try again.")


def edit_step(message):
    if message.text and not message.text.startswith("/cancel"):
        global TEMP_POST_ID
        try:
            DATA[TEMP_POST_ID]["caption"] = message.text
            with open("data.json", "w") as f:
                json.dump(DATA, f)
            TEMP_POST_ID = -1
            bot.send_message(message.chat.id, "Successfully edited.")
        except IndexError:
            bot.send_message(message.chat.id, "Seems like it took so long for you to make a decision.")
    else:
        bot.send_message(message.chat.id, "Post edition canceled.")


@bot.message_handler(commands=['force_post'])
def force_post(message):
    if checker(message.chat.id):
        return
    msg = bot.send_message(message.chat.id, "Are you sure that you want to do force post? [Yes].")
    bot.register_next_step_handler(msg, force_post_step)


def force_post_step(message):
    if message.text and message.text == "Yes":
        poster()
    else:
        bot.send_message(message.chat.id, "Post deletion canceled.")


@bot.message_handler(commands=["switcher"])
def switch(message):
    if checker(message.chat.id):
        return
    try:
        split = message.text.split()
        global SWITCHER
        if len(split) > 1:
            arg = int(split[1])
            if arg == 0:
                SWITCHER = False
                bot.send_message(message.chat.id, "Pictures posting is disabled.")
            elif arg == 1:
                SWITCHER = True
                bot.send_message(message.chat.id, "Pictures posting is enabled.")
            else:
                raise ValueError
        else:
            bot.send_message(message.chat.id, "Pictures posting is {}.".format("enabled" if SWITCHER else "disabled"))
    except ValueError:
        bot.send_message(message.chat.id, "Incorrect usage, try again.")


@bot.message_handler(commands=["posting_rules"])
def posting_rules(message):
    if checker(message.chat.id):
        return
    bot.send_message(message.chat.id, "Amount of pics per post: {}\nPosting hours: {}".
                     format(str(PICS_COUNT), POSTING_HOURS))


@bot.message_handler(commands=["ping"])
def ping(message):
    bot.send_message(message.chat.id, "Pong.")


def poster():
    try:
        if len(DATA) < PICS_COUNT:
            raise IndexError
        pics = [DATA.pop(0) for _ in range(PICS_COUNT)]
        for pic in pics:
            caption = pic["caption"]
            split = caption.split(", ")
            caption = ""
            if len(split) > 1:
                caption += split[0] + ", "
            split = split[-1].split("\nby ")
            caption += "\nby ".join(["#{}".format(i.replace(" ", "_")) for i in split])
            # bot.send_photo(CHANNEL, photo=pic["id"], caption=pic["caption"]+"\n"+CHANNEL_USERNAME)
            bot.send_photo(CHANNEL, photo=pic["id"], caption=caption+"\n"+CHANNEL_USERNAME)
            time.sleep(1)
            bot.send_document(CHANNEL, pic["doc_id"])
            time.sleep(1)
        with open("data.json", "w") as f:
            json.dump(DATA, f)
    except IndexError:
        for user in ALLOWED_USERS:
            bot.send_message(user, "You've run out of posts; posting failed.")


def checker(cid):
    if cid not in ALLOWED_USERS:
        bot.send_message(cid, "You're not allowed to do this. Go away.")
        return True
    return False


def bot_runner():
    while True:
        try:
            print(bot.get_me())
            bot.polling(none_stop=True)
        except Exception:
            time.sleep(15)


if __name__ == '__main__':
    print("Starting...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        polling = executor.submit(bot_runner)
        checking = executor.submit(send_pics)
