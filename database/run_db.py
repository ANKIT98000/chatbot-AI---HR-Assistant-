import os
import uvicorn

os.environ["IS_PERSISTENT"] = "TRUE"
os.environ["PERSIST_DIRECTORY"] = "./vectordb"
os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"

if __name__ == "__main__":
    print("Boss, ChromaDB Server start ho raha hai Port 8005 par...")
    # Yahan port 8005 hona chahiye
    uvicorn.run("chromadb.app:app", host="127.0.0.1", port=8005)