import json
import os
import re
import time
from typing import Callable
import requests
from datetime import datetime
import dotenv

dotenv.load_dotenv()


import telegram
from telegram import Update
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
User_District_Data = {}
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


# Get User District
def get_user_district(userId: str) -> str:
    return User_District_Data.get(userId)


# Check and Set Ramadan Time Data
def checkAndSetTimeData() -> None:
    global Ramadan_Time_Data, Time_Difference_Data

    if Ramadan_Time_Data.get("status") == "running":
        return

    """
    fileUrl = "https://raw.githubusercontent.com/Toxic-Noob/PersonalRepository/main/ramadan/timeData.json"
    response = requests.get(fileUrl)
    if not response.status_code == 200:
        return
    
    data: dict = response.json()
    if data.get("status") == "running":
        Ramadan_Time_Data = data
        with open("timeDifference.json", "r") as f:
            Time_Difference_Data = json.load(f)
    """
    with open("timeData.json", "r") as f:
        Ramadan_Time_Data = json.load(f).get("timeData")

    with open("timeDifference.json", "r") as f:
        Time_Difference_Data = json.load(f)


# Parse the given Date's Data from the Ramadan Time Data
def parseDateDataFromDataset(todayTimeData: str):
    key = f"{todayTimeData.get('day')}:{todayTimeData.get('month')}:{todayTimeData.get('year')}"

    data = Ramadan_Time_Data.get(key)

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
    dateDataset = Ramadan_Time_Data.get(key)

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
        dateDataset2 = Ramadan_Time_Data.get(key)

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


# Get Today's Time Data
async def get_today_time_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    userDistrict = get_user_district(update.effective_user.id)
    if not userDistrict:
        await update.message.reply_text(
            escapeMarkdownV2("\n".join([f"`{x}`" for x in District_List])),
            parse_mode="MarkdownV2",
        )
        await update.message.reply_text(
            escapeMarkdownV2("Please Send your District Name:"), parse_mode="MarkdownV2"
        )
        context.user_data["waiting_for_location"] = True

        return

    time_now = datetime.now()
    todayTimeData = {
        "day": time_now.day,
        "month": 3,
        "year": time_now.year,
        "hour": time_now.hour,
        "minute": time_now.minute,
    }

    todayData = parseTodayData(todayTimeData, userDistrict)
    await update.message.reply_text(
        escapeMarkdownV2(json.dumps(todayData, indent=4)), parse_mode="MarkdownV2"
    )


async def save_user_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_for_location"):
        return

    userDistrict = update.message.text.strip().lower().title()
    if (not userDistrict) or (userDistrict not in District_List):
        await update.message.reply_text("Invalid District Name. Please Try Again.")
        return

    User_District_Data[update.effective_user.id] = userDistrict
    context.user_data["waiting_for_location"] = False
    await update.message.reply_text("Location Saved Successfully!")


# START APP
def setup_app(app):

    app.add_handler(
        CommandHandler(
            "start",
            lambda update, context: timeoutWrapper(
                get_today_time_data, update, context
            ),
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            lambda update, context: timeoutWrapper(save_user_location, update, context),
        )
    )

    print("Pooling...")
    app.run_polling()


if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()

    print("Starting...")
    checkAndSetTimeData()
    setup_app(app)
