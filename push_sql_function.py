from sqlalchemy import create_engine, MetaData, Table, update
from sqlalchemy.orm import sessionmaker
import pandas as pd
import logging

def get_engine(username, password, host, port, database):
    engine = create_engine(f'mysql+mysqlconnector://{username}:{password}@{host}:{port}/{database}', echo=False)
    return engine

def get_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    return session

def get_metadata(engine):
    metadata = MetaData()
    metadata.reflect(bind=engine)
    return metadata

def update_records(engine, metadata, table_name, data, column_mapping, indices=None):
    # Reflect the table from the database
    table = Table(table_name, metadata, autoload_with=engine)
    
    # Define the primary key column(s)
    primary_key_cols = [col.name for col in table.primary_key.columns]

    # Update each record in the database
    with engine.connect() as connection:
        # Filter the data based on provided indices if any
        if indices is not None:
            data = data.loc[indices]
        
        for index, row in data.iterrows():
            # Convert DateTime to string format (YYYY-MM-DD HH:MM:SS)
            datetime_str = row[column_mapping['DateTime']].strftime('%Y-%m-%d %H:%M:%S')
            
            # Construct update data, excluding primary key columns
            update_data = {table_col: row[df_col] for df_col, table_col in column_mapping.items() if table_col not in primary_key_cols}
            
            # Construct the update query using SQLAlchemy's update function
            update_query = (
                update(table)
                .where(table.c.DateTime == datetime_str)  # Assuming 'DateTime' is the primary key
                .values(update_data)  # Pass the update_data dictionary to values()
            )
            
            # Execute the update query
            connection.execute(update_query)
        
        # Commit the transaction
        connection.commit() # The connection is automatically committed on execute, no need for connection.commit() ??
