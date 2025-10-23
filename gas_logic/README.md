# Google Apps Script (GAS) Form & Sheet Logic
This folder is for storing script written to communicate between the server/database and Google Workspace tools.
* Contains logic for selecting and transfer data to Google Forms for the following endpoints
  * Create Applications (/api/applications)
  * Alternate Email Entry (/api/students/alternate-emails)
  * Attendance Log Entry (/api/students/create-attendance-entry)
* Contains Menu logic for accessing endpoints from target Google Sheet

## Set-Up
### Environment Vars
The following values are required as Script Properties (to be fetch by PropertyService)
* BASE_SERVER_URL: URL where the server is located. Do not include the target endpoint 
* AUTH_KEY: Authentication key needed for accessing the server
In the Apps Script editor, you can find them under Settings

### How to use (Forms)
1. Select your desired form
2. Copy the questionID.gs and use it to find the question ID for each response question
3. Add the question ids to the qids object, these should be named after the endpoints arguments when possible
4. Add the remaing supporting .gs files (response.gs, sanitize.gs)

### How to use (Menu)
1. Go to the target Google Sheet --> Extensions --> Apps Script
2. Copy & Paste the menu.gs content into the code.gs file
3. Copy other supporting files as needed (currently none)

Make sure to run at least 1 function directly from the editor when copying over. This ensure the script has the correct permissions to run other script functions properly.

# Testing
Testing is limited; these scripts should be verified manually.
* Mocking event objects is difficult without a dedicated library
* A new test env would need to be added to the repository
* The Google Apps Script runtime may differ from regular node environment
TODO: It's possible to test, if anyone is interested in fixing this, please introduce the issue.