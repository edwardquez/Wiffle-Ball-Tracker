"""One shared MongoDB connection and a short-lived cache of the league's stats.

    get_db()       the database (one connection for the whole app, reused across pages and visitors)
    league()       stats.League built from the database, cached for CACHE_SECONDS
    clear_cache()  call after any write so every page shows the change straight away

The Scorekeeper reads the live game straight from the database (never cached), and clears
the cache after each save, so the stat pages are never more than one refresh behind.
"""
import os

import streamlit as st
from dotenv import load_dotenv
from pymongo import MongoClient

import stats

DB_NAME = "blitzballstats"
CACHE_SECONDS = 30

load_dotenv()


@st.cache_resource(show_spinner=False)
def _client():
    client = MongoClient(os.getenv("MONGO_URI"))
    try:
        # Live games rewrite their atbats by game_id on every save; the index keeps that quick
        client[DB_NAME].atbats.create_index("game_id")
    except Exception:
        pass   # the app still works without the index (e.g. a read-only user)
    return client


def get_db():
    return _client()[DB_NAME]


@st.cache_data(ttl=CACHE_SECONDS, show_spinner=False)
def league():
    return stats.League.from_db(get_db())


def clear_cache():
    league.clear()