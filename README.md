# Automated-revenue-monitoring-for-Doubleclick-Bid-Manager
A program used to query DBM hourly for reports regarding revenues of existing advertisers. Calculates revenues spent in the past hour/day and compares them to projected values entered in a Google Sheets spreadsheet. Sends notifications regarding exceeded budgets by E-mail.

## Requirements
* Python
* Google Sheets Spreadsheet for entering data in the [format](https://docs.google.com/spreadsheets/d/1psmDekU5p1TR_vSPF3Wp2bxuuAtsY_UImz4MR-SgliY/edit?usp=sharing)
* Bash
* Google service account .json file with API access enabled for Sheets and DBM (renamed to client_secret.json)
* Sendgrid account .json file (sendgrid.json)

## Install:
* pip install -r requirements.txt
* update SheetName and SheetLink variables in main.py with correct values for your spreadsheet.
* update Request_Body to fit your request. The FILTER_PARTNER variable is especially important.

## Running the program
Run start.sh. The program will automatically run every hour.

## Top-level description of execution
* start.sh activates script.sh every hour.
* script.sh:
  * Creates seperate directories each day for log files of each execution of main.py. Deletes any logs more than one week old.
  * Runs main.py.
  * If main.py exits with an error runs Email_Error.py
* main.py:
  * Sends query and downloads report using DBM API.
  * Calculates hourly revenue for each advertiser by subtracting values from previous report.
  * Formats data from report into a dictionary of Advertiser objects. 
  * Updates spreadsheet with any new Advertisers.
  * Gets projected values and Emails from spreadsheet.
  * Makes a list of Advertiser objects which have exceeded hourly or daily budget projections.
  * Formats and sends Emails with Warnings about exceeded budgets.
* Email_Error.py:
  * Reads latest log file and sends it by Email to addresses in Service_Emails variable in main.py.




