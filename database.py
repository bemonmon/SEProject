<<<<<<< HEAD
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import numpy as np
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CSVToPostgreSQL:
    def __init__(self, host, database, user, password, port=5432):
        """Initialize database connection parameters"""
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.connection = None
        self.cursor = None
    
    def connect(self):
        """Establish connection to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port
            )
            self.cursor = self.connection.cursor()
            logger.info("Successfully connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL database: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Database connection closed")
    
    def create_tables(self):
        """Create tables matching the ERD schema"""
        
        # Create sensors table
        create_sensors_table = """
        CREATE TABLE IF NOT EXISTS sensors (
            id_sensore INTEGER PRIMARY KEY,
            nome_tipo_sensore CHARACTER VARYING(100),
            unita_misura CHARACTER VARYING(20),
            id_stazione INTEGER,
            nome_stazione CHARACTER VARYING(100),
            quota INTEGER,
            provincia CHARACTER(2),
            comune CHARACTER VARYING(100),
            storico CHARACTER(1),
            data_start DATE,
            data_stop DATE,
            utm_nord BIGINT,
            utm_est BIGINT,
            latitude NUMERIC(10,8),
            longitude NUMERIC(11,8),
            location GEOMETRY
        );
        """
        
        # Create air_quality table
        create_air_quality_table = """
        CREATE TABLE IF NOT EXISTS air_quality (
            id SERIAL PRIMARY KEY,
            idsensore INTEGER,
            data TIMESTAMP WITHOUT TIME ZONE,
            valore DOUBLE PRECISION,
            stato CHARACTER VARYING(10),
            idoperatore INTEGER,
            FOREIGN KEY (idsensore) REFERENCES sensors(id_sensore)
        );
        """
        
        try:
            self.cursor.execute(create_sensors_table)
            self.cursor.execute(create_air_quality_table)
            self.connection.commit()
            logger.info("Tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            self.connection.rollback()
            raise
    
    def clean_data(self, df, table_type):
        """Clean and prepare data for insertion"""
        
        if table_type == 'sensors':
            # Handle date columns
            date_columns = ['data_start', 'data_stop']
            for col in date_columns:
                if col in df.columns:
                    # Replace ### or other placeholders with None
                    df[col] = df[col].replace(['###', '########', '', 'NULL'], None)
                    # Convert to datetime, handling errors
                    df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
            
            # Handle numeric columns
            numeric_columns = ['id_sensore', 'id_stazione', 'quota', 'utm_nord', 'utm_est']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Handle float columns
            float_columns = ['latitude', 'longitude']
            for col in float_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        
        elif table_type == 'readings':
            # Handle date column - convert to timestamp
            if 'Data' in df.columns:
                df['Data'] = df['Data'].replace(['###', '########', ''], None)
                df['Data'] = pd.to_datetime(df['Data'], errors='coerce', dayfirst=True)
            
            # Handle numeric columns
            if 'idSensore' in df.columns:
                df['idSensore'] = pd.to_numeric(df['idSensore'], errors='coerce')
            if 'Valore' in df.columns:
                df['Valore'] = pd.to_numeric(df['Valore'], errors='coerce')
            if 'idOperatore' in df.columns:
                df['idOperatore'] = pd.to_numeric(df['idOperatore'], errors='coerce')
        
        return df
    
    def import_sensors_data(self, csv_file_path):
        """Import sensors data from CSV"""
        try:
            # Read CSV file
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            logger.info(f"Read {len(df)} rows from sensors CSV file")
            
            # Clean data
            df = self.clean_data(df, 'sensors')
            
            # Prepare data for insertion
            columns = [
                'id_sensore', 'nome_tipo_sensore', 'unita_misura', 'id_stazione',
                'nome_stazione', 'quota', 'provincia', 'comune', 'storico',
                'data_start', 'data_stop', 'utm_nord', 'utm_est',
                'latitude', 'longitude', 'location'
            ]
            
            # Convert DataFrame to list of tuples
            data_tuples = []
            for _, row in df.iterrows():
                tuple_data = []
                for col in columns:
                    if col in df.columns:
                        value = row[col]
                        if pd.isna(value):
                            tuple_data.append(None)
                        else:
                            # Handle geometry column for location
                            if col == 'location' and value:
                                # Convert PostGIS geometry string to proper format
                                tuple_data.append(value)
                            else:
                                tuple_data.append(value)
                    else:
                        tuple_data.append(None)
                data_tuples.append(tuple(tuple_data))
            
            # Insert data using execute_values for better performance
            insert_query = f"""
            INSERT INTO sensors ({', '.join(columns)})
            VALUES %s
            ON CONFLICT (id_sensore) DO UPDATE SET
                nome_tipo_sensore = EXCLUDED.nome_tipo_sensore,
                unita_misura = EXCLUDED.unita_misura,
                id_stazione = EXCLUDED.id_stazione,
                nome_stazione = EXCLUDED.nome_stazione,
                quota = EXCLUDED.quota,
                provincia = EXCLUDED.provincia,
                comune = EXCLUDED.comune,
                storico = EXCLUDED.storico,
                data_start = EXCLUDED.data_start,
                data_stop = EXCLUDED.data_stop,
                utm_nord = EXCLUDED.utm_nord,
                utm_est = EXCLUDED.utm_est,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                location = EXCLUDED.location
            """
            
            execute_values(self.cursor, insert_query, data_tuples)
            self.connection.commit()
            logger.info(f"Successfully imported {len(data_tuples)} sensor records")
            
        except Exception as e:
            logger.error(f"Error importing sensors data: {e}")
            self.connection.rollback()
            raise
    
    def import_readings_data(self, csv_file_path):
        """Import air quality readings data from CSV"""
        try:
            # Read CSV file
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            logger.info(f"Read {len(df)} rows from air quality CSV file")
            
            # Clean data
            df = self.clean_data(df, 'readings')
            
            # Rename columns to match database schema
            column_mapping = {
                'idSensore': 'idsensore',
                'Data': 'data',
                'Valore': 'valore',
                'Stato': 'stato',
                'idOperatore': 'idoperatore'
            }
            df = df.rename(columns=column_mapping)
            
            # Prepare data for insertion
            columns = ['idsensore', 'data', 'valore', 'stato', 'idoperatore']
            
            # Convert DataFrame to list of tuples
            data_tuples = []
            for _, row in df.iterrows():
                tuple_data = []
                for col in columns:
                    if col in df.columns:
                        value = row[col]
                        if pd.isna(value):
                            tuple_data.append(None)
                        else:
                            tuple_data.append(value)
                    else:
                        tuple_data.append(None)
                data_tuples.append(tuple(tuple_data))
            
            # Insert data
            insert_query = f"""
            INSERT INTO air_quality ({', '.join(columns)})
            VALUES %s
            """
            
            execute_values(self.cursor, insert_query, data_tuples)
            self.connection.commit()
            logger.info(f"Successfully imported {len(data_tuples)} air quality records")
            
        except Exception as e:
            logger.error(f"Error importing air quality data: {e}")
            self.connection.rollback()
            raise

def main():
    """Main function to run the import process"""
    
    # Database connection parameters
    DB_CONFIG = {
        'host': 'localhost',        # Change to your PostgreSQL host
        'database': 'ali3',  # Change to your database name
        'user': 'postgres',    # Change to your PostgreSQL username
        'password': '123456', # Change to your PostgreSQL password
        'port': 5432               # Change if using different port
    }
    
    # CSV file paths
    SENSORS_CSV = 'C:/Users/Majid/Desktop/sensors.csv'      # Path to your sensors CSV file
    READINGS_CSV = "C:/Users/Majid/Desktop/air_quality.csv" # Path to your air quality CSV file
    
    # Create importer instance
    importer = CSVToPostgreSQL(**DB_CONFIG)
    
    try:
        # Connect to database
        importer.connect()
        
        # Create tables
        importer.create_tables()
        
        # Import sensors data
        logger.info("Starting import of sensors data...")
        importer.import_sensors_data(SENSORS_CSV)
        
        # Import air quality data
        logger.info("Starting import of air quality data...")
        importer.import_readings_data(READINGS_CSV)
        
        logger.info("All data imported successfully!")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
    finally:
        # Close database connection
        importer.close()

if __name__ == "__main__":
=======
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import numpy as np
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CSVToPostgreSQL:
    def __init__(self, host, database, user, password, port=5432):
        """Initialize database connection parameters"""
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.connection = None
        self.cursor = None
    
    def connect(self):
        """Establish connection to PostgreSQL database"""
        try:
            self.connection = psycopg2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password,
                port=self.port
            )
            self.cursor = self.connection.cursor()
            logger.info("Successfully connected to PostgreSQL database")
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL database: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("Database connection closed")
    
    def create_tables(self):
        """Create tables matching the ERD schema"""
        
        # Create sensors table
        create_sensors_table = """
        CREATE TABLE IF NOT EXISTS sensors (
            id_sensore INTEGER PRIMARY KEY,
            nome_tipo_sensore CHARACTER VARYING(100),
            unita_misura CHARACTER VARYING(20),
            id_stazione INTEGER,
            nome_stazione CHARACTER VARYING(100),
            quota INTEGER,
            provincia CHARACTER(2),
            comune CHARACTER VARYING(100),
            storico CHARACTER(1),
            data_start DATE,
            data_stop DATE,
            utm_nord BIGINT,
            utm_est BIGINT,
            latitude NUMERIC(10,8),
            longitude NUMERIC(11,8),
            location GEOMETRY
        );
        """
        
        # Create air_quality table
        create_air_quality_table = """
        CREATE TABLE IF NOT EXISTS air_quality (
            id SERIAL PRIMARY KEY,
            idsensore INTEGER,
            data TIMESTAMP WITHOUT TIME ZONE,
            valore DOUBLE PRECISION,
            stato CHARACTER VARYING(10),
            idoperatore INTEGER,
            FOREIGN KEY (idsensore) REFERENCES sensors(id_sensore)
        );
        """
        
        try:
            self.cursor.execute(create_sensors_table)
            self.cursor.execute(create_air_quality_table)
            self.connection.commit()
            logger.info("Tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            self.connection.rollback()
            raise
    
    def clean_data(self, df, table_type):
        """Clean and prepare data for insertion"""
        
        if table_type == 'sensors':
            # Handle date columns
            date_columns = ['data_start', 'data_stop']
            for col in date_columns:
                if col in df.columns:
                    # Replace ### or other placeholders with None
                    df[col] = df[col].replace(['###', '########', '', 'NULL'], None)
                    # Convert to datetime, handling errors
                    df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
            
            # Handle numeric columns
            numeric_columns = ['id_sensore', 'id_stazione', 'quota', 'utm_nord', 'utm_est']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Handle float columns
            float_columns = ['latitude', 'longitude']
            for col in float_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        
        elif table_type == 'readings':
            # Handle date column - convert to timestamp
            if 'Data' in df.columns:
                df['Data'] = df['Data'].replace(['###', '########', ''], None)
                df['Data'] = pd.to_datetime(df['Data'], errors='coerce', dayfirst=True)
            
            # Handle numeric columns
            if 'idSensore' in df.columns:
                df['idSensore'] = pd.to_numeric(df['idSensore'], errors='coerce')
            if 'Valore' in df.columns:
                df['Valore'] = pd.to_numeric(df['Valore'], errors='coerce')
            if 'idOperatore' in df.columns:
                df['idOperatore'] = pd.to_numeric(df['idOperatore'], errors='coerce')
        
        return df
    
    def import_sensors_data(self, csv_file_path):
        """Import sensors data from CSV"""
        try:
            # Read CSV file
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            logger.info(f"Read {len(df)} rows from sensors CSV file")
            
            # Clean data
            df = self.clean_data(df, 'sensors')
            
            # Prepare data for insertion
            columns = [
                'id_sensore', 'nome_tipo_sensore', 'unita_misura', 'id_stazione',
                'nome_stazione', 'quota', 'provincia', 'comune', 'storico',
                'data_start', 'data_stop', 'utm_nord', 'utm_est',
                'latitude', 'longitude', 'location'
            ]
            
            # Convert DataFrame to list of tuples
            data_tuples = []
            for _, row in df.iterrows():
                tuple_data = []
                for col in columns:
                    if col in df.columns:
                        value = row[col]
                        if pd.isna(value):
                            tuple_data.append(None)
                        else:
                            # Handle geometry column for location
                            if col == 'location' and value:
                                # Convert PostGIS geometry string to proper format
                                tuple_data.append(value)
                            else:
                                tuple_data.append(value)
                    else:
                        tuple_data.append(None)
                data_tuples.append(tuple(tuple_data))
            
            # Insert data using execute_values for better performance
            insert_query = f"""
            INSERT INTO sensors ({', '.join(columns)})
            VALUES %s
            ON CONFLICT (id_sensore) DO UPDATE SET
                nome_tipo_sensore = EXCLUDED.nome_tipo_sensore,
                unita_misura = EXCLUDED.unita_misura,
                id_stazione = EXCLUDED.id_stazione,
                nome_stazione = EXCLUDED.nome_stazione,
                quota = EXCLUDED.quota,
                provincia = EXCLUDED.provincia,
                comune = EXCLUDED.comune,
                storico = EXCLUDED.storico,
                data_start = EXCLUDED.data_start,
                data_stop = EXCLUDED.data_stop,
                utm_nord = EXCLUDED.utm_nord,
                utm_est = EXCLUDED.utm_est,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                location = EXCLUDED.location
            """
            
            execute_values(self.cursor, insert_query, data_tuples)
            self.connection.commit()
            logger.info(f"Successfully imported {len(data_tuples)} sensor records")
            
        except Exception as e:
            logger.error(f"Error importing sensors data: {e}")
            self.connection.rollback()
            raise
    
    def import_readings_data(self, csv_file_path):
        """Import air quality readings data from CSV"""
        try:
            # Read CSV file
            df = pd.read_csv(csv_file_path, encoding='utf-8')
            logger.info(f"Read {len(df)} rows from air quality CSV file")
            
            # Clean data
            df = self.clean_data(df, 'readings')
            
            # Rename columns to match database schema
            column_mapping = {
                'idSensore': 'idsensore',
                'Data': 'data',
                'Valore': 'valore',
                'Stato': 'stato',
                'idOperatore': 'idoperatore'
            }
            df = df.rename(columns=column_mapping)
            
            # Prepare data for insertion
            columns = ['idsensore', 'data', 'valore', 'stato', 'idoperatore']
            
            # Convert DataFrame to list of tuples
            data_tuples = []
            for _, row in df.iterrows():
                tuple_data = []
                for col in columns:
                    if col in df.columns:
                        value = row[col]
                        if pd.isna(value):
                            tuple_data.append(None)
                        else:
                            tuple_data.append(value)
                    else:
                        tuple_data.append(None)
                data_tuples.append(tuple(tuple_data))
            
            # Insert data
            insert_query = f"""
            INSERT INTO air_quality ({', '.join(columns)})
            VALUES %s
            """
            
            execute_values(self.cursor, insert_query, data_tuples)
            self.connection.commit()
            logger.info(f"Successfully imported {len(data_tuples)} air quality records")
            
        except Exception as e:
            logger.error(f"Error importing air quality data: {e}")
            self.connection.rollback()
            raise

def main():
    """Main function to run the import process"""
    
    # Database connection parameters
    DB_CONFIG = {
        'host': 'localhost',        # Change to your PostgreSQL host
        'database': 'ali3',  # Change to your database name
        'user': 'postgres',    # Change to your PostgreSQL username
        'password': '123456', # Change to your PostgreSQL password
        'port': 5432               # Change if using different port
    }
    
    # CSV file paths
    SENSORS_CSV = 'C:/Users/Majid/Desktop/sensors.csv'      # Path to your sensors CSV file
    READINGS_CSV = "C:/Users/Majid/Desktop/air_quality.csv" # Path to your air quality CSV file
    
    # Create importer instance
    importer = CSVToPostgreSQL(**DB_CONFIG)
    
    try:
        # Connect to database
        importer.connect()
        
        # Create tables
        importer.create_tables()
        
        # Import sensors data
        logger.info("Starting import of sensors data...")
        importer.import_sensors_data(SENSORS_CSV)
        
        # Import air quality data
        logger.info("Starting import of air quality data...")
        importer.import_readings_data(READINGS_CSV)
        
        logger.info("All data imported successfully!")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
    finally:
        # Close database connection
        importer.close()

if __name__ == "__main__":
>>>>>>> f4bc93ba63b592ef5eea876844f7161635763107
    main()