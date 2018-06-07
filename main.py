from googleapiclient.discovery import build
import json
from io import StringIO
from google.oauth2 import service_account
from googleapiclient.errors import HttpError
import time
import pprint
import requests
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import sendgrid
from sendgrid.helpers.mail import *
import sys
import logging

Today = datetime.today()
# date and time now formatted as string
Today_Date_Formatted = str(Today.date()) + '_' + str(Today.hour).zfill(2) + ':' + str(Today.minute).zfill(2)

# create the log file for this execution
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# create a file handler
handler = logging.FileHandler('Logs/Logs_{}/logfile{}.log'.format(Today.date(), Today_Date_Formatted))
handler.setLevel(logging.INFO)

# create a logger format
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(handler)

# Email addresses to send emails to in case of errors
Service_Emails = []

# Details of the google spreadsheet used to enter data (spreadsheet read/write permissions
# have to be given to the service account used by this program)
SheetName = ''
SheetLink = ''

# Request body for making a new query in the DBM API
Request_Body = {
  "kind": "doubleclickbidmanager#query",
  "queryId": "131815728",
  "metadata": {
    "title": "DailyBudgetControlReport",
    "dataRange": "CURRENT_DAY",
    "format": "CSV"
  },
  "params": {
    "type": "TYPE_GENERAL",
    "filters": [
      {
        "type": "FILTER_PARTNER",
        "value": ""
      }
    ],
    "groupBys": ["FILTER_ADVERTISER"],
    "metrics": [
      "METRIC_REVENUE_USD"
    ]
  },
  "schedule": {
    "frequency": "ONE_TIME"
  },
  "timezoneCode": "Europe/Warsaw"
}


class Spreadsheet:
    """class for reading/writing information to the google spreadsheet"""

    def __init__(self, adv_dict):
        self.Adv_Dict = adv_dict
        self.CSVAdvNames = list(self.Adv_Dict)
        self.Sheet = None
        self.SheetAdvNames = None
        self.Emails = ""
        self.Budget_Value_Y_Index = 3
        self.Budget_Value_X_Index = 2

    def open_sheet(self):
        # Authenticate the service account credentials using client_secret.json file
        # Drive API has to be enabled for project
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name("client_secret.json", scope)

        # Authorize with spreadsheet API using service account credentials
        try:
            client = gspread.authorize(creds)
        except Exception as e:
            logger.error('Error authorizing with gspread', exc_info=True)
            raise e

        # Open the spreadsheet
        try:
            sheet = client.open(SheetName).sheet1
        except Exception as e:

            logger.error('Error opening spreadsheet')
            raise e

        self.SheetAdvNames = sheet.col_values(1)[2:]
        logger.info("Opened spreadsheet")
        self.Sheet = sheet

    def delete_old_advertiser_names_from_sheet(self):
        # delete rows of advertisers who are no longer in the reports from the spreadsheet
        for i in range(len(self.SheetAdvNames) - 1, -1, -1):
            if self.SheetAdvNames[i] not in self.CSVAdvNames:
                self.SheetAdvNames.pop(i)
                self.Sheet.delete_row(i + self.Budget_Value_Y_Index)

    def read_budget_values_from_sheet(self):
        email_addresses_x_index = 3
        email_addresses_y_index = 2
        for i in range(len(self.SheetAdvNames)):
            # read and update value of entered budget
            val = self.Sheet.cell(i + self.Budget_Value_Y_Index, self.Budget_Value_X_Index).value
            # if value of cell in spreadsheet is empty do nothing (advertiser.BudgetFromSheet = None)
            if val is not '':
                val = val[1:]
                self.Adv_Dict[self.SheetAdvNames[i]].budget = int(val)

        # get Emails to send warnings to
        self.Emails = self.Sheet.cell(email_addresses_y_index, email_addresses_x_index).value
        self.Emails = self.Emails.replace(" ", "")
        self.Emails = self.Emails.split(",")
        logger.info("Values read from spreadsheet")
        return self.Adv_Dict

    def write_new_adv_names_to_sheet(self):
        # add rows for any new advertisers
        # (inserts rows from the end)
        i = len(self.SheetAdvNames) + self.Budget_Value_Y_Index - 1
        for advertiser_name, advertiser in self.Adv_Dict.items():
            if advertiser_name not in self.SheetAdvNames and advertiser_name != '':
                self.Sheet.insert_row([advertiser_name], i)
                i += 1
        return self.Adv_Dict

    def get_budgets(self):
        self.delete_old_advertiser_names_from_sheet()
        self.write_new_adv_names_to_sheet()
        return self.read_budget_values_from_sheet()


class DoubleclickApiWrapper:
    """Class serving as a Wrapper for the Doubleclick API"""

    def __init__(self, service_account_json_path):
        # Authorize the Doubleclick API using google service account

        scope = ['https://www.googleapis.com/auth/doubleclickbidmanager']
        try:
            # create credentials object from service account file
            credentials = service_account.Credentials.from_service_account_file(service_account_json_path, scopes=scope)

            # build th API object for Doubleclick using credentials
            self.doubleclick = build('doubleclickbidmanager', 'v1', credentials=credentials)
            logger.info("Doubleclick API authorized")
        except Exception as e:
            logger.error("Couldn't authorize Doubleclick API", exc_info=True)
            raise e

    def createquery(self, body):
        try:
            query = self.doubleclick.queries().createquery(body=body).execute()
            logger.info("Succesfully created query")
            logger.info(query)
        except HttpError as e:
            logger.error("Encountered error while creating query in Doubleclick API", exc_info=True)
            raise e
        return query

    def deletequery(self, id):
        try:
            query = self.doubleclick.queries().deletequery(queryId=id).execute()
            logger.info("Succesfully deleted query")
        except HttpError as e:
            logger.error("Encountered error while deleting query in Doubleclick API", exc_info=True)
            raise e
        return query

    def listqueries(self):
        try:
                query = self.doubleclick.queries().listqueries().execute()
        except HttpError as e:
                logger.error("Encountered error while requesting list of queries in Doubleclick API", exc_info=True)
                raise e
        return query

    def get_stored_query_ids(self):
        # returns all stored query IDs
        ids = []
        for query in self.listqueries()["queries"]:
            ids.append(query["queryId"])
        return ids

    def delete_all_queries(self):
        resp = self.listqueries()
        for query in resp["queries"]:
            self.deletequery(query["queryId"])

    def run_query(self, id, timezoneCode = "Europe/Warsaw"):
        body = {
            "timezoneCode": timezoneCode
        }
        try:
            logger.info("Running query...")
            query = self.doubleclick.queries().runquery(queryId=id, body=body).execute()
            logger.info("Succesfully ran query")
        except HttpError as e:
            logger.error("Encountered error while running query in Doubleclick API", exc_info=True)
            raise e
        return query

    def get_latest_query_response(self):
        try:
            with open('latest_response.json', 'r') as f:
                return json.loads(f.read())
        except FileNotFoundError as e:
            logger.warning("Couldn't find latest_response.json", exc_info=True)
            raise e

    def write_latest_query_response(self, response):
        logger.info("Storing query response to latest_response.json...")
        open("latest_response.json", "w").write(json.dumps(response))

    @staticmethod
    def write_latest_report(csv):
        logger.info("Storing latest report to latest_report.csv...")
        open("latest_report.csv", "w").write(csv)

    def download_from_url(self, url):
        # Downloads report csv file from given google drive url
        try:
            r = requests.get(url, allow_redirects=True)
            logger.info("Downloading report...")
            csv = r.content.decode("UTF-8")
        except Exception:
            logger.error("Encountered error while Downloading report", exc_info=True)
            raise
        return csv

    def find_query(self, queryId, querylist):
        for q in querylist:
            if q["queryId"] == queryId:
                return q

    def get_link_to_latest_report(self):
        # Run the previously stored query. If no matching query is found, generate a new one and run it
        query = None
        querylist = self.listqueries()
        if "queries" in querylist.keys():
            try:
                query = self.find_query(self.get_latest_query_response()["queryId"], querylist["queries"])
            except IOError:
                query = None
        if query is None:
            logger.info("Query not found. making new query...")
            id = self.createquery(Request_Body)["queryId"]
            query = self.find_query(id, self.listqueries()["queries"])
        self.run_query(query["queryId"])

        # Wait for query to run
        time.sleep(12)
        query_response = self.find_query(query["queryId"], self.listqueries()["queries"])
        logger.debug(query)
        url = query_response["metadata"]["googleCloudStoragePathForLatestReport"]

        # Makes sure that an unusable query (not containing a report) isn't written as the latest query
        if url == "":
            logger.error("query didn't provide url to report")
            raise Exception("query didn't provide url to report")
        self.write_latest_query_response(query_response)

        return url


class Advertiser:
    """ Class serving as a data structure for Advertisers"""
    def __init__(self, name = None, revenue = None):
        self.name = name
        self.revenue_today = revenue
        self.budget = None
        self.revenue_hour = None


class CsvParser:
    """ Class for parsing data obtained from reports"""
    def __init__(self, csvstring):
        self.csvstring = csvstring
        buff = StringIO(csvstring)
        # read string obtained from report as CSV
        self.CSVReader = csv.reader(buff)
        self.advertisers = {}

    def make_advertisers(self):
        for i, row in enumerate(self.CSVReader):
            # Make Advertiser objects based on the csv from the report
            try:
                revenue = float(row[4])
                self.advertisers[row[0]] = Advertiser(name=row[0], revenue=revenue)

            # skips rows which do not have valid format
            except ValueError:
                logger.info('Invalid value for Advertiser, skipping row nr: {}\n'.format(i))
                continue
            except IndexError:
                logger.info('Invalid index for row nr: {}\n'.format(i))
                continue
        return self.advertisers

    # Function which obtains revenue values from previous report and substracts from current revenue values
    def get_hourly_revenue(self, prev_report_path="latest_report.csv"):

        # If running at the first hour of the day revenue_hour = revenue
	# For some reason DBM runs on Los Angeles time (GMT-7) so beggining of the day for UTC+1 is 9:00am
        if Today.hour != 9:
            try:
                with open(prev_report_path, 'r') as prev_report:
                    logger.info("Reading values form previous report")
                    tempreader = csv.reader(prev_report)
                    for i, row in enumerate(tempreader):
                        if len(row) > 0 and row[0] in self.advertisers.keys():
                            try:
                                # read revenue values from previous report
                                prev_revenue = float(row[4])
                                advertiser = self.advertisers[row[0]]

                                # substract previous revenue from current revenue
                                advertiser.revenue_hour = advertiser.revenue_today - prev_revenue
                            except ValueError:
                                logger.info('Invalid value for Advertiser, skipping row nr: {}\n'.format(i))
                                continue
                            except IndexError:
                                logger.info('Invalid index for row nr: {}\n'.format(i))
                                continue
            except FileNotFoundError:
                logger.error("Didn't find previous report file. hourly report may be wrong...")

        #in the case of a new advertiser made in the previous hour (wasn't in the previous report)
        for name, advertiser in self.advertisers.items():
            if advertiser.revenue_hour is None:
                advertiser.revenue_hour = advertiser.revenue_today
        return self.advertisers

    def get_revenues(self):
        self.get_hourly_revenue("latest_report.csv")

        # can overwrite previous report because all needed data has been obtained
        open("latest_report.csv", 'w').write(self.csvstring)


class Warnings:
    """Class for sending notification Emails in case of the monthly budget exceeding projected budget"""

    def __init__(self, adv_dict, emails):
        self.Adv_Dict = adv_dict
        self.WarningContent = []
        self.Emails = emails

    # Check if any Advertisers exceeded projected budget
    def check_budgets(self):
        for advertiser_name, advertiser in self.Adv_Dict.items():
            # Format the calculated budget so it only shows the first two decimal places (tmp = '{:.2f}...')
            # Later, format a second time so that there are commas seperating thousands ({:.2f}.format(eval(tmp)))

            # if no value entered in spreadsheet ignore advertiser
            if advertiser.budget is None:
                continue
            daily_revenue = advertiser.revenue_today
            hourly_revenue = advertiser.revenue_hour
            daily_budget = 1.2*(advertiser.budget/7.0)
            hourly_budget = 1.2*(daily_budget/24.0)
            daily_revenue_formatted = '{:.2f}'.format(round(daily_revenue, 2))
            hourly_revenue_formatted = '{:.2f}'.format(round(hourly_revenue, 2))
            daily_budget_formatted = '{:.2f}'.format(round(daily_budget, 2))
            hourly_budget_formatted = '{:.2f}'.format(round(hourly_budget, 2))
            s = "Advertiser name: {0}\nProjected budget for today: ${1:,}\n" \
                "Amount spent today: ${2:,}\nProjected budget for past hour: ${3:,}\n" \
                "Amount spent in past hour: ${4:,}\n\n".format(
                advertiser_name, eval(daily_budget_formatted), eval(daily_revenue_formatted),
                eval(hourly_budget_formatted), eval(hourly_revenue_formatted))

            # check if daily budget has been exceeded, if so append to WarningContent
            if daily_revenue >= daily_budget:
                daily_warning = "Advertiser exceeded daily budget:\n" + s
                logger.info(daily_warning)
                self.WarningContent.append(daily_warning)

            # check if hourly budget has been exceeded, if so append to WarningContent
            if hourly_revenue >= hourly_budget:
                hourly_warning = "Advertiser exceeded hourly budget:\n" + s
                logger.info(hourly_warning)
                self.WarningContent.append(hourly_warning)
        return len(self.WarningContent) > 0

    # Method used to send Email (also used in mail.py to send any Error logs or log files)
    @staticmethod
    def send_email(recipient, content, subject='List of DBM budget violations for: {}'.format(Today_Date_Formatted),
                   write_response_to_logfile=True):
        # Authenticate and construct Email using sendgrid api
        with open('sendgrid.json', 'r') as f:
            apikey = json.loads(f.read())
            apikey = apikey["SENDGRID_API_KEY"]
        sg = sendgrid.SendGridAPIClient(apikey=apikey)
        from_email = Email('budget@control.com')
        to_email = Email(recipient)
        content = Content('text/plain', content)

        # Send Email
        try:
            mail = Mail(from_email, subject, to_email, content)
            response = sg.client.mail.send.post(request_body=mail.get())
        except Exception as e:
            logger.error('Error Sending Email', exc_info=True)
            raise e

    def send_warning_emails(self):
        content = 'Link to Budget_Control Spreadsheet:\n{}\n\n'.format(SheetLink)
        content += "This email was generated automatically because one or more advertisers listed in Doubleclick Bid" \
                   "Manager have exceeded their projected budgets\n\n"
        for s in self.WarningContent:
            content += s
        for email in self.Emails:
            self.send_email(email, content)

    # Method to send notifications to all recipients
    def send_warnings(self):
        self.send_warning_emails()
        tmp = 'Warning email sent EST {}'.format(Today_Date_Formatted)
        logger.info(tmp)
        return Today_Date_Formatted


def main(argv):
    api = DoubleclickApiWrapper("client_secret.json")
    url = api.get_link_to_latest_report()
    s = api.download_from_url(url)
    c = CsvParser(s)
    c.make_advertisers()
    c.get_revenues()
    sheet = Spreadsheet(c.advertisers)
    sheet.open_sheet()
    advertisers = sheet.get_budgets()
    pp = pprint.PrettyPrinter(indent = 4)
    pp.pprint(s)
    for k, v in c.advertisers.items():
        logger.info("{} dayrevenue: {}, hourrevenue: {}, budget: {}".format(k, v.revenue_today, v.revenue_hour, v.budget))
    w = Warnings(advertisers, sheet.Emails)
    if w.check_budgets():
        w.send_warnings()
    if Today.hour == 11 or Today.hour == 21:
        recipients = Service_Emails + w.Emails
        content = "Budget Control program is running."
        for recipient in recipients:
            w.send_email(recipient, content, subject="Budget Control CEST Date: {}.".format(Today_Date_Formatted))

if __name__ == "__main__":
	main(sys.argv)








