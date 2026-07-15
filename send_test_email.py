import sys

from notifier import EmailConfigError, send_notification

if __name__ == "__main__":
    subject = sys.argv[1] if len(sys.argv) > 1 else "note-ifs test email"
    body = sys.argv[2] if len(sys.argv) > 2 else "This is a test notification from note-ifs."
    try:
        send_notification(subject, body)
    except EmailConfigError as e:
        print(f"Not sent: {e}")
        sys.exit(1)
    print("Sent.")
