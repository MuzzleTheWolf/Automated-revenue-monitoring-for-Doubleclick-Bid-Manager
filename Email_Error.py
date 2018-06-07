from main import Warnings, Service_Emails
from datetime import datetime
import sys


def main(argv):
    today = datetime.today()
    filename = argv[1]
    subject = 'Budget_Control at {} exited with error, relaying latest logfile'.format(today)
    with open('Logs/Logs_{}/{}'.format(today.date(), filename), 'r') as f:
        s = f.read()
    try:
        Warnings.send_email(Service_Emails, s, subject=subject, write_response_to_logfile=False)
        print('sent error email for {}'.format(filename))
    except Exception:
        Warnings.send_email(Service_Emails, 'logfile could not be read', subject=subject, write_response_to_logfile=False)
        print("sent error email but logfile couldn't be read")


if __name__ == "__main__":
	main(sys.argv)



