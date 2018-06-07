# Automated-revenue-monitoring-for-Doubleclick-Bid-Manager
A program used to query DBM hourly for reports regarding revenues of existing advertisers. Calculates revenues spent in the past hour/day and compares them to projected values entered in a Google Sheets spreadsheet. Sends notifications regarding exceeded budgets by E-mail.

## Requirements
* Python
* Google Sheets Spreadsheet for entering data in the format: https://docs.google.com/spreadsheets/d/1psmDekU5p1TR_vSPF3Wp2bxuuAtsY_UImz4MR-SgliY/edit?usp=sharing
* Bash
* Google service account .json file with API access enabled for Sheets and DBM (renamed to client_secret.json)
* Sendgrid account .json file (sendgrid.json)

## Install:
* pip install -r requirements.txt
* update SheetName and SheetLink variables in main.py with correct values for your spreadsheet.
* update Request_Body to fit your request. The FILTER_PARTNER variable is especially important.

## Running the program
Run start.sh. The program will automatically run every hour.

## Top-level execution description
* start.sh activates script.sh every hour
* ### script.sh:
..* creates seperate directories each day for log files of each execution of main.py. 
..* It also deletes any logs more than one week old. Runs main.py.





