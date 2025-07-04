# 🌍 Air Quality Monitoring Web App

This project consists of three main components:

1. **Database**
2. **Webserver**
3. **Dashboard**

---

## ⚙️ Database Configuration

A local PostgreSQL database with the PostGIS extension is required. You can set it up in one of two ways:

### Option A: Restore from SQL Dump

1. Restore the database using the file:

   ```
   DB_2019.sql
   ```

### Option B: Create from Scratch Using Python

1. Manually create a PostgreSQL database named `DB_2019`.
2. Enable the `PostGIS` extension in the new database.
3. Ensure the following two files are in the same folder:
   - `SEfG_DB_Creation.ipynb`
   - `Dati_sensori_aria_dal_2019.csv`
4. Open and run `SEfG_DB_Creation.ipynb`, after updating the database connection settings in the notebook.

---

## 🚀 Running the Web Application

Once the database is ready, follow these steps to launch the web app:

1. Run the webserver:

   ```bash
   python webserver.py
   ```

   > Make sure to update the database connection settings inside `webserver.py`.

2. In a **new terminal**, run the dashboard:

   ```bash
   python dashboard.py
   ```

3. Open your browser and visit:

   [http://127.0.0.1:4070/](http://127.0.0.1:4070/)

---