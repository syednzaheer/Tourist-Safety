"""
Twilio SMS wrapper, optional like everything else that needs an external
account. Text messages are the one channel that still works on basic
cellular coverage with no data connection, which is the whole reason the
problem statement asks for SMS specifically instead of a push
notification - a push notification needs the app open and a data
connection, neither of which is a safe assumption in the terrain this
is meant for.

Without TWILIO_* env vars set, this logs "simulated" instead of
pretending to send a text it didn't send.
"""
import os

TWILIO_SID = os.environ.get("TWILIO_SID")
TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN")
TWILIO_FROM = os.environ.get("TWILIO_FROM")


def send_sms(to: str, body: str) -> str:
    if not (TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM and to):
        return "simulated"
    try:
        from twilio.rest import Client  # imported lazily; twilio is optional

        client = Client(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(body=body, from_=TWILIO_FROM, to=to)
        return "sent"
    except Exception as e:
        return f"failed: {e}"
