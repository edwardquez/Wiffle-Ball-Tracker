import csv 
from pymongo import MongoClient
import pandas as pd
import os
import json
from dotenv import load_dotenv

# Load MongoDB URI from .env or environment variables
load_dotenv()
MONGO_URI = os.getenv('MONGO_URI')  # e.g. mongodb+srv://<user>:<password>@cluster0.mongodb.net

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client['Wiffleball_Database']  # Name your database


def import_csv_to_mongodb(csv_path, collection_name):
    client = MongoClient(MONGO_URI)
    db = client["blitzballstats"]
    collection = db[collection_name]

    # Optional: Clear old data
    collection.drop()

    df = pd.read_csv(csv_path)
    data = json.loads(df.to_json(orient="records"))
    collection.insert_many(data)
    print(f"Inserted {collection.count_documents({})} documents into {collection_name}")
    

# Run imports for all CSVs
import_csv_to_mongodb('atbats.csv', 'atbats')
import_csv_to_mongodb('games.csv', 'games')
import_csv_to_mongodb('players.csv', 'players')
