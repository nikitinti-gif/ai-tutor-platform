from datetime import datetime


def log(event, message):

    print(

        f"[{datetime.now().strftime('%H:%M:%S')}] "

        f"{event} -> {message}"

    )