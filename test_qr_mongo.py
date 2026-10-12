import os
import sys
from dotenv import load_dotenv
import pymongo
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

def mask_value(val):
    if val is None:
        return "None"
    s = str(val)
    if "@" in s:
        # Mask user:pass in URI
        prefix, rest = s.split("://", 1)
        creds, host = rest.split("@", 1)
        return f"{prefix}://***:***@{host}"
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

    uri = os.environ.get("QR_MONGO_URI", "").strip()
    db_name = os.environ.get("QR_DB", "").strip()
    coll_name = os.environ.get("QR_COLLECTION", "").strip()

    missing = []
    if not uri:
        missing.append("QR_MONGO_URI")
    if not db_name:
        missing.append("QR_DB")
    if not coll_name:
        missing.append("QR_COLLECTION")

    if missing:
        print("[CONFIG ERROR] The following required variables in .env are empty or missing:")
        for m in missing:
            print(f"  - {m}")
        print("\nPlease populate these variables in your .env file before running this test.")
        sys.exit(1)

    print("[1/4] Connecting to QR Verification MongoDB Atlas cluster...")
    print(f"      Database: {db_name}")
    print(f"      Collection: {coll_name}")
    print(f"      Cluster URI: {mask_value(uri)}")

    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=12000)
        client.admin.command('ping')
        print("[SUCCESS] Connected to MongoDB Atlas cluster successfully.\n")
    except ServerSelectionTimeoutError:
        print("[TIMEOUT ERROR] Connection timed out after 6000ms.")
        print("Possible causes:")
        print("  - Your current IP address is not whitelisted in MongoDB Atlas Network Access.")
        print("  - Network firewall or proxy is blocking outbound traffic on port 27017.")
        sys.exit(2)
    except OperationFailure as e:
        print(f"[AUTH ERROR] Authentication failed: {e}")
        sys.exit(3)
    except Exception as e:
        print(f"[ERROR] Could not connect: {e}")
        sys.exit(4)

    print("[2/4] Verifying database and collections...")
    db = client[db_name]
    existing_colls = db.list_collection_names()
    print(f"      Collections found: {existing_colls}")

    target_coll_name = coll_name
    if target_coll_name not in existing_colls:
        if "qr_codes" in existing_colls:
            target_coll_name = "qr_codes"
        elif "qr_code" in existing_colls:
            target_coll_name = "qr_code"

    coll = db[target_coll_name]
    total_count = coll.count_documents({})
    unused_count = coll.count_documents({"used": False})
    used_count = coll.count_documents({"used": True})

    print(f"\n[3/4] Collection Summary for '{target_coll_name}':")
    print(f"      Total QR tokens:  {total_count}")
    print(f"      Unused (valid):   {unused_count}")
    print(f"      Used (consumed):  {used_count}")

    print("\n[4/4] Sample available tokens:")
    samples = list(coll.find({"used": False}).limit(5))
    for i, s in enumerate(samples, 1):
        print(f"      {i}. Token: {s.get('qr_token')} | used: {s.get('used')}")

    print("\n[COMPLETE] QR verification MongoDB is ready and operational.")

if __name__ == "__main__":
    main()
