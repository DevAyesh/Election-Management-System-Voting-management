"""
Script to clean up MongoDB collection and fix documents with id: null
Run this script to fix the duplicate key error issue.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'election_portal.settings')
django.setup()

from candidates.models import Candidate
from pymongo import MongoClient

def cleanup_mongodb():
    """
    Clean up MongoDB collection to remove documents with id: null
    """
    # Connect to MongoDB directly
    client = MongoClient('mongodb://localhost:27017/')
    db = client['election_portal_db']
    collection = db['candidates_candidate']
    
    print("Checking for documents with id: null...")
    
    # Find documents with id: null
    null_id_docs = list(collection.find({'id': None}))
    print(f"Found {len(null_id_docs)} documents with id: null")
    
    if null_id_docs:
        print("Removing documents with id: null...")
        result = collection.delete_many({'id': None})
        print(f"Deleted {result.deleted_count} documents with id: null")
    else:
        print("No documents with id: null found.")
    
    # Also check for documents without id field
    docs_without_id = list(collection.find({'id': {'$exists': False}}))
    if docs_without_id:
        print(f"Found {len(docs_without_id)} documents without id field")
        # These should be fine as MongoDB will auto-generate _id
    
    print("\nCleanup complete!")
    print(f"Total documents in collection: {collection.count_documents({})}")
    
    client.close()

if __name__ == '__main__':
    cleanup_mongodb()

