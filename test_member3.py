import os
import sys
from dotenv import load_dotenv
import pymongo
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

def mask_value(val):
    if val is None:
        return "None"
    s = str(val)
    if len(s) <= 3:
        return s[:1] + "***" if len(s) > 1 else "***"
    return s[:3] + "***"

def main():
    load_dotenv()

    # Resilient DNS resolver for Windows MongoDB Atlas SRV lookups
    try:
        import dns.resolver
        dns.resolver.default_resolver = dns.resolver.Resolver()
        dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']
    except Exception:
        pass

    uri = os.environ.get("MEMBER3_MONGO_URI", "").strip()
    db_name = os.environ.get("MEMBER3_DB", "").strip()
    coll_name = os.environ.get("MEMBER3_COLLECTION", "").strip()

    missing = []
    if not uri:
        missing.append("MEMBER3_MONGO_URI")
    if not db_name:
        missing.append("MEMBER3_DB")
    if not coll_name:
        missing.append("MEMBER3_COLLECTION")

    if missing:
        print("[CONFIG ERROR] The following required variables in .env are empty or missing:")
        for m in missing:
            print(f"  - {m}")
        print("\nPlease populate these variables in your .env file before running this test.")
        sys.exit(1)

    print("[1/4] Connecting to Member 3 MongoDB Atlas cluster (timeout = 5000ms)...")

    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
        # Force a network call to verify connection
        client.admin.command('ping')
        print("[SUCCESS] Connected to MongoDB Atlas cluster successfully.")
    except ServerSelectionTimeoutError:
        print("[TIMEOUT ERROR] Connection timed out after 5000ms.")
        print("Possible causes:")
        print("  - Your current IP address is not whitelisted in MongoDB Atlas Network Access.")
        print("  - Network firewall or proxy is blocking outbound traffic on port 27017.")
        sys.exit(2)
    except OperationFailure as e:
        if "Authentication failed" in str(e) or e.code in (18, 8000):
            print("[AUTH ERROR] Authentication failed. Please check the username and password in MEMBER3_MONGO_URI.")
        else:
            print(f"[AUTH/PERM ERROR] Operation failed: {e.details.get('errmsg', str(e)) if hasattr(e, 'details') and e.details else 'Permission denied'}")
        sys.exit(3)
    except Exception as e:
        print(f"[CONNECTION ERROR] Failed to connect: {type(e).__name__}")
        sys.exit(4)

    # List databases (optional check - may be denied for restricted user)
    print("\n[2/4] Testing cluster-level permissions...")
    try:
        db_list = client.list_database_names()
        print(f"Cluster databases visible: {db_list}")
    except OperationFailure:
        print("Cluster list_database_names: not permitted (expected for scoped/read-only user). Continuing...")

    # Access targeted database and list collections
    print(f"\n[3/4] Accessing database: {db_name}")
    try:
        db = client[db_name]
        collections = db.list_collection_names()
        print(f"Available collections in '{db_name}': {collections}")
        if coll_name not in collections:
            print(f"[WARNING] Collection '{coll_name}' not found in collections list.")
    except OperationFailure as e:
        print(f"[PERMISSION ERROR] Cannot list collections in '{db_name}': {e}")
        sys.exit(5)

    # Fetch one document (read-only)
    print(f"\n[4/4] Fetching sample document from collection: '{coll_name}'...")
    try:
        coll = db[coll_name]
        doc = coll.find_one()
        if doc is None:
            print(f"[NOTICE] Collection '{coll_name}' is empty (no documents found).")
        else:
            print("[SUCCESS] Sample document retrieved. Schema & masked preview:")
            print("-" * 60)
            print(f"{'FIELD NAME':<25} {'PYTHON TYPE':<15} {'MASKED VALUE'}")
            print("-" * 60)
            for field, val in doc.items():
                val_type = type(val).__name__
                masked = mask_value(val)
                print(f"{field:<25} {val_type:<15} {masked}")
            print("-" * 60)
    except OperationFailure as e:
        print(f"[PERMISSION ERROR] Cannot read from collection '{coll_name}': {e}")
        sys.exit(6)

if __name__ == '__main__':
    main()
