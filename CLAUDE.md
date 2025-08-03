# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current State
This directory currently contains only PDF contract notes from stock trading activities. There is no active code project or development setup at this time.



## Notes
We plan to create a Stock Portfolio App which contains all the stock transactions (both buy and sell). Some of the key features of the application should be 

- This app should be able to support storing stock portfolio for multiple users
- The primary mechanism of updating the stock transaction details would be digital contract notes. The user should be able to upload one or multiple password encrypted pdf files. Post upload there should be a way to confirm the details which are being added to the database, with an option of editing those. 
- There should also be an option of manual entries (both add and edit)
- There should be a dashboard screen which shows both realized and unrealiazed capital gains
- There should be another screen to see all trasnaction with relevant fitlers on dates and or securities. 
- At the top there should be a way os creating users and switching the view to another user wherein we now see transactions for that specific user.
- There should also be an option for switching into a view which given an option of seeing data for all users.
 - For now in the code could you remove user registration and authentication and just let user enter a username. If the username is new create the user and if the username is existing show the details of that user    

Database Structure:
The main transaction table should at a high level have the below fields (use your intelligence to make this better )
Username or any user identified tying this transaction to a user
SecurityName/ Key Identifier
Transaction Type (Buy Or Sell)
Quantity Traded
Total Amount Traded 

Technology stack:
Kindly create the backend in Python since this involves decrypting encrypted digital contract notes in a format similar to samples created in the contractnotes/ folder. 
KIndly create the front-end in React. 
Use a database of your choice to store the transactions.
Integrate with a free stock market API to get real time stock price.  

## Structure
- `contractnotes/` - This folder contains sample Contract notes which are generated while selling or buying stocks. This folder should not be checked into github but should be just used for training the model. The pdf in the files are password protected. For these samples the password of all the files are "VIK1706". We need to extract the content from the section "The scrip wise summary is enclosed below" or named something similar and need to group them at a "Security/Contract Description" level and then extract the below information for each security 
Order Date (which would be the date of the digital contract note)
Securtiy Name 
Buy Or Sell
Quantity 
Total Trade Price/ Transaction Amount.

- 'backend/' - The backend code repo.
- 'ftontend/' - The frontend code repo. 


This file should be updated once actual development begins to include relevant build commands, architecture details, and development workflows.