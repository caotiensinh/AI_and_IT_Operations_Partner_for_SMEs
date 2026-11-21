"""Staging-only entrypoint: runtime account may assume sme_app, never DB owner."""
import os
import psycopg
from sme_partner.session_api import create_app

dsn=os.environ["SME_RUNTIME_DATABASE_DSN"]
app=create_app(lambda:psycopg.connect(dsn,connect_timeout=5))
