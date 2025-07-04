# Software Release Document
Our project three main parts:
1. database
2. webserver 
3. dashboard

# Configuration of the database
In our project local database was used, to configure it on your PC there are two ways:
1. Restore database from the file "DB_2019.sql".
2. Create a database using python script.
In the second case follow these steps:
1. Manually create database and name it "DB_2019".
2. Create the extension "PostGIS" to this database.
3. Run file "SEfG_DB_Creation.ipynb" to create tables and relations (it's important to change connection to database settings inside the file and make sure that the file "SEfG_DB_Creation.ipynb" is in the same folder with "Dati_sensori_aria_dal_2019.csv" file).

# Steps to run the website:
1. Run "webserver.py" in Visual Studio Code by a terminal by typing: "python webserver.py" (it's important to change connection to database settings inside the file).
2. Open a new terminal and run "dashboard.py" by typing: "python dashboard.py".
3. Finally on http://127.0.0.1:4070/ you can see the website.
