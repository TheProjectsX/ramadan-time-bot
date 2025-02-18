import json
import os
import re
import time
from typing import Callable, Union
import requests
from datetime import datetime, date
import dotenv
import pytz

dotenv.load_dotenv()


import telegram
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Global variables
BOT_TOKEN = os.getenv("BOT_TOKEN")

Ramadan_Time_Data = {}
Time_Difference_Data = {}
District_List = [
    "Bagerhat",
    "Bandarban",
    "Barguna",
    "Barishal",
    "Bhola",
    "Bogura",
    "Brahmanbaria",
    "Chandpur",
    "Chapaiawabganj",
    "Chattogram",
    "Chuadanga",
    "Cox's Bazar",
    "Cumilla",
    "Dhaka",
    "Dinajpur",
    "Faridpur",
    "Feni",
    "Gaibandha",
    "Gazipur",
    "Gopalganj",
    "Habiganj",
    "Jamalpur",
    "Jashore",
    "Jhalokati",
    "Jhenaidah",
    "Joypurhat",
    "Khagrachari",
    "Khulna",
    "Kishoreganj",
    "Kurigram",
    "Kushtia",
    "Lakshmipur",
    "Lalmonirhat",
    "Madaripur",
    "Magura",
    "Manikganj",
    "Maulvibazar",
    "Meherpur",
    "Munshiganj",
    "Mymensingh",
    "Naogaon",
    "Narail",
    "Narayanganj",
    "Narsingdi",
    "Natore",
    "Netrokona",
    "Nilphamari",
    "Noakhali",
    "Pabna",
    "Panchagarh",
    "Patuakhali",
    "Pirojpur",
    "Rajbari",
    "Rajshahi",
    "Rangamati",
    "Rangpur",
    "Satkhira",
    "Shariatpur",
    "Sherpur",
    "Sirajgonj",
    "Sunamganj",
    "Sylhet",
    "Tangail",
    "Thakurgaon",
]


# Check and Set Ramadan Time Data
def checkAndSetTimeData() -> None:
    global Ramadan_Time_Data, Time_Difference_Data

    with open("timeData.json", "r") as f:
        Ramadan_Time_Data = json.load(f)

    with open("timeDifference.json", "r") as f:
        Time_Difference_Data = json.load(f)


# Parse the given Date's Data from the Ramadan Time Data
def parseDateDataFromDataset(todayTimeData: str):
    key = f"{todayTimeData.get('day')}:{todayTimeData.get('month')}:{todayTimeData.get('year')}"

    data = Ramadan_Time_Data.get("timeData").get(key)

    return data


# Calculate District Time from Dhaka Time
# data = Time Data, period = sehri or iftar :: 0 or 1
def calculateDistrict(data: dict, period: str, district: str) -> dict:
    districtData = Time_Difference_Data.get(district)
    difference = districtData.get(period)

    hour = data.get("hour")
    minute = data.get("minute")

    # The Time difference Database contains minutes with + or - symbols: -4, +5. Eval'ng will return the difference.
    newMinute = eval(f"{minute}{difference}")
    newHour = hour

    if newMinute > 60:
        newMinute -= 60
        newHour += 1
    elif newMinute < 0:
        newMinute = 60 - int(newMinute * newMinute / 2)
        newHour -= 1
    elif newMinute == 60:
        newMinute = 0
        newHour += 1

    data = {"hour": newHour, "minute": newMinute}

    return data


# Calculate the Time left for the Period via finding difference between Period time and current time
def calculateTimeDiff(period, current):
    pHour = period.get("hour", 0)
    pMinute = period.get("minute", 0)

    cHour = current.get("hour", 0)
    cMinute = current.get("minute", 0)

    period_total_minutes = pHour * 60 + pMinute
    current_total_minutes = cHour * 60 + cMinute

    diff = period_total_minutes - current_total_minutes

    if diff < 0:  # Period has passed
        return {"hour": 0, "minute": 0, "diff": abs(diff)}

    return {"hour": diff // 60, "minute": diff % 60}


def is_leap_year(year):
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def get_days_in_month(month, year):
    if month in [4, 6, 9, 11]:  # April, June, September, November -> 30 days
        return 30
    elif month == 2:  # February
        return 29 if is_leap_year(year) else 28
    return 31  # All other months -> 31 days


# Parse Today's Time of Sehri and Iftar
# If the iftar time passed 20 minutes ago, show the next ramadan Sehri time, date and Sl No
def parseTodayData(todayTimeData: dict, district: str):
    # key = DD:MM:YYYY
    key = f"{todayTimeData.get('day')}:{todayTimeData.get('month')}:{todayTimeData.get('year')}"
    try:
        dateDataset = Ramadan_Time_Data.get("timeData").get(key)
    except Exception as e:
        return None

    sehriUser = calculateDistrict(dateDataset.get("sehri"), "sehri", district)
    iftarUser = calculateDistrict(dateDataset.get("iftar"), "iftar", district)

    currentTime = {
        "hour": todayTimeData.get("hour"),
        "minute": todayTimeData.get("minute"),
    }

    sehriLeft = calculateTimeDiff(sehriUser, currentTime)
    iftarLeft = calculateTimeDiff(iftarUser, currentTime)

    if sehriLeft.get("diff", 0) > 20:
        sehriUser = {"hour": "--", "minute": "--"}
        sehriLeft = {"hour": 0, "minute": 0}

    if iftarLeft.get("diff", 0) > 20:
        todayTimeData["day"] += 1
        days_in_month = get_days_in_month(todayTimeData["month"], todayTimeData["year"])

        # If day exceeds the max days of the month, reset day and move to next month
        if todayTimeData["day"] > days_in_month:
            todayTimeData["day"] = 1
            todayTimeData["month"] += 1

            # If month exceeds December, reset month and move to next year
            if todayTimeData["month"] > 12:
                todayTimeData["month"] = 1
                todayTimeData["year"] += 1

        key = f"{todayTimeData.get('day')}:{todayTimeData.get('month')}:{todayTimeData.get('year')}"
        dateDataset2 = Ramadan_Time_Data.get("timeData").get(key)

        sehriUser = calculateDistrict(dateDataset2.get("sehri"), "sehri")

        total_current_minutes = todayTimeData.get("hour") * 60 + todayTimeData.get(
            "minute"
        )
        total_sehri_minutes = (
            24 * 60 + sehriUser.get("hour") * 60 + sehriUser.get("minute")
        )

        diff_minutes = total_sehri_minutes - total_current_minutes

        hourLeft = diff_minutes // 60
        minuteLeft = diff_minutes % 60

        if minuteLeft >= 60:
            minuteLeft -= 60
            hourLeft += 1

        sehriLeft = {"hour": hourLeft, "minute": minuteLeft}
        iftarUser = {"hour": "--", "minute": "--"}
        iftarLeft = {"hour": 0, "minute": 0}

    return_data = {
        "serial": dateDataset.get("serial"),
        "quote": dateDataset.get("quote"),
        "time": {"sehri": sehriUser, "iftar": iftarUser},
        "left": {"sehri": sehriLeft, "iftar": iftarLeft},
    }

    return return_data


#### Telegram Bot Functions ####


# Timeout Wrapper
async def timeoutWrapper(
    function: Callable, update: Update, context: ContextTypes.DEFAULT_TYPE
):
    try:
        await function(update, context)
    except telegram.error.TimedOut:
        print("Timeout")
        time.sleep(3)
        await function(update, context)


# Escape Safe Characters
def escapeMarkdownV2(text: str) -> str:
    specialCharacters = r"\[\]()~>#+-=|{}.!"
    escapedText = re.sub(f"([{re.escape(specialCharacters)}])", r"\\\1", text)
    # Escape `_` only if it’s outside Markdown italics
    escapedText = re.sub(r"(?<!_)_(?!_)", r"\_", escapedText)

    return escapedText


# Load existing data
def load_data():
    if os.path.exists("userDistrict.json"):
        with open("userDistrict.json", "r") as file:
            return json.load(file)
    return {}


# Set user's city
def set_user_district(user_id, district):
    data = load_data()
    data[str(user_id)] = district
    with open("userDistrict.json", "w") as file:
        json.dump(data, file, indent=4)


def format_to_12h(hour: Union[int, str], minute: Union[int, str]) -> str:
    if hour == "--" and minute == "--":
        return "--:--"

    time = datetime.strptime(f"{hour}:{minute}", "%H:%M")
    return time.strftime("%I:%M %p")


# Get user's city
def get_user_district(user_id):
    data = load_data()
    return data.get(str(user_id))


# Show Help
async def show_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        escapeMarkdownV2(
            """📚 **Help Menu**

Here are the commands you can use with this bot:

1. **/start** - Start the Bot
   - Get Today's Sehri and Iftar Time for your District

2. **/help** - Get Help
   - Display this help message with a list of available commands.

3. **/district** - Custom District
    - Get Time of Custom District

4. **/reset** - Reset District
    - Reset saved User District

Feel free to use these commands to get Iftar and Sehri Time! 🎉
"""
        ),
        parse_mode="MarkdownV2",
        reply_markup=ReplyKeyboardRemove(),
    )


# Get Today's Time Data
async def today_time_data_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, custom_district=None
):
    if not custom_district:
        userDistrict: Union[str, None] = get_user_district(update.effective_user.id)
    else:
        userDistrict = custom_district

    if not userDistrict:
        reply_markup = ReplyKeyboardMarkup(
            [[district] for district in District_List], one_time_keyboard=True
        )

        await update.message.reply_text("Assalamu Alaikum!")
        await update.message.reply_text(
            escapeMarkdownV2("Please Select your District Name:"),
            parse_mode="MarkdownV2",
            reply_markup=reply_markup,
        )
        context.user_data["waiting_for_location"] = True

        return

    today = date.today()
    event_date = date(
        Ramadan_Time_Data.get("startDate", {}).get("year"),
        Ramadan_Time_Data.get("startDate", {}).get("month"),
        Ramadan_Time_Data.get("startDate", {}).get("day"),
    )

    if today < event_date:
        await update.message.reply_text(
            escapeMarkdownV2(
                f"""Ramadan is Coming!

📅 *Possibility:* {Ramadan_Time_Data.get("startDate", {}).get("day"):02d} - {Ramadan_Time_Data.get("startDate", {}).get("month"):02d} - {Ramadan_Time_Data.get("startDate", {}).get("year")}"""
            ),
            parse_mode="MarkdownV2",
        )
        return

    tz = pytz.timezone("Asia/Dhaka")
    time_now = datetime.now(tz)
    todayTimeData = {
        "day": time_now.day,
        "month": time_now.month,
        "year": time_now.year,
        "hour": time_now.hour,
        "minute": time_now.minute,
    }

    todayRamadanData = parseTodayData(todayTimeData, userDistrict)
    if not todayRamadanData:
        await update.message.reply_text("It's not Ramadan!")
        return

    replyText = f"""
🔢 <b>Ramadan No:</b> {todayRamadanData["serial"]:02d}

🌍 <b>Location:</b> {userDistrict.title()}
📅 <b>Date:</b> {todayTimeData["day"]:02d} - {todayTimeData["month"]:02d} - {todayTimeData["year"]}  
  

🌙 <b>Sehri Time:</b> {format_to_12h(todayRamadanData["time"]["sehri"]["hour"],todayRamadanData["time"]["sehri"]["minute"])}  
🕌 <b>Iftar Time:</b> {format_to_12h(todayRamadanData["time"]["iftar"]["hour"], todayRamadanData["time"]["iftar"]["minute"])}  

⏳ <u><b>Time Left:</b></u>
- <b>Sehri:</b> {todayRamadanData["left"]["sehri"]["hour"]:02d}h {todayRamadanData["left"]["sehri"]["minute"]:02d}m  
- <b>Iftar:</b> {todayRamadanData["left"]["iftar"]["hour"]:02d}h {todayRamadanData["left"]["iftar"]["minute"]:02d}m  

<i><b>{todayRamadanData["quote"]["quote"]}</b></i>  
📖 <b>{todayRamadanData["quote"]["source"]}</b>
"""

    await update.message.reply_text(replyText, parse_mode="html")


# Get Today's Time Data of Custom District
async def custom_district_data_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            escapeMarkdownV2(
                "You Must provide a District Name\n\nExample: **`/district Dhaka`**"
            ),
            parse_mode="MarkdownV2",
        )
        return

    userDistrict = args[0].strip().lower()
    if userDistrict not in userDistrict not in [x.lower() for x in District_List]:
        await update.message.reply_text("Invalid District Name")
        await update.message.reply_text(
            escapeMarkdownV2("\n".join([f"`{x}`" for x in District_List])),
            parse_mode="MarkdownV2",
        )
        await update.message.reply_text(
            escapeMarkdownV2("Select District From Above List"),
            parse_mode="MarkdownV2",
        )

    await today_time_data_command(update, context, userDistrict)


# Reset User Data
async def reset_user_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_user_district(update.effective_user.id, None)
    await update.message.reply_text("User Data Reset Successfully!")


# Save User location
async def save_user_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_location"):
        return

    userDistrict = update.message.text.strip().lower()
    if (not userDistrict) or (userDistrict not in [x.lower() for x in District_List]):
        await update.message.reply_text("Invalid District Name. Please Try Again.")
        return

    set_user_district(update.effective_user.id, userDistrict)
    context.user_data["waiting_for_location"] = False
    await update.message.reply_text(
        "Location Saved Successfully!\nYou can Restart (/start) the bot to get Today's Time Data.",
        reply_markup=ReplyKeyboardRemove(),
    )


# Error Handler
async def handle_error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error: {context.error}")

    await update.message.reply_text("Server Error, Please try again!")


# START APP
def setup_app(app: Application):

    app.add_handler(
        CommandHandler(
            "start",
            lambda update, context: timeoutWrapper(
                today_time_data_command, update, context
            ),
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            lambda update, context: timeoutWrapper(show_help_command, update, context),
        )
    )

    app.add_handler(
        CommandHandler(
            "district",
            lambda update, context: timeoutWrapper(
                custom_district_data_command, update, context
            ),
        )
    )

    app.add_handler(
        CommandHandler(
            "reset",
            lambda update, context: timeoutWrapper(
                reset_user_data_command, update, context
            ),
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            lambda update, context: timeoutWrapper(save_user_location, update, context),
        )
    )

    # Error Handler
    app.add_error_handler(handle_error)

    print("Pooling...")
    app.run_polling()


if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()

    print("Starting...")
    checkAndSetTimeData()
    setup_app(app)
