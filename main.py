from fastapi import FastAPI, HTTPException, Depends
from beanie import Document, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Optional
import os
import secrets
from fastapi.security import APIKeyHeader

app = FastAPI()

# Database model
class EncryptedData(Document):
    project_id: str
    encrypted_content: str
    access_key: str


class StoreData(BaseModel):
    project_id: str
    encrypted_content: str


# Initialize database
@app.on_event("startup")
async def startup_event():
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017", uuidRepresentation="standard")
    db = client["dotenvpull"]
    await init_beanie(database=db, document_models=[EncryptedData])

# Security
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    data = await EncryptedData.find_one(EncryptedData.access_key == api_key)
    if not data:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return data.project_id

# API routes
@app.post("/store")
async def store_data(data: StoreData):
    existing_data = await EncryptedData.find_one(EncryptedData.project_id == data.project_id)
    if existing_data:
        raise HTTPException(status_code=400, detail="Data already exists, use update if you want to modify it")
    
    data = EncryptedData(
        **data.model_dump(),
        access_key = secrets.token_urlsafe(32)
    )
    await data.insert()
    return {"message": "Data stored successfully", "access_key": data.access_key}

@app.get("/retrieve")
async def retrieve_data(project_id: str = Depends(verify_api_key)):
    data = await EncryptedData.find_one(EncryptedData.project_id == project_id)
    if not data:
        raise HTTPException(status_code=404, detail="Data not found")
    return {"encrypted_content": data.encrypted_content}

@app.put("/update")
async def update_data(new_data: StoreData, project_id: str = Depends(verify_api_key)):
    existing_data = await EncryptedData.find_one(EncryptedData.project_id == project_id)
    if not existing_data:
        raise HTTPException(status_code=404, detail="Data not found")
    existing_data.encrypted_content = new_data.encrypted_content
    await existing_data.save()
    return {"message": "Data updated successfully"}

@app.delete("/delete")
async def delete_data(project_id: str = Depends(verify_api_key)):
    data = await EncryptedData.find_one(EncryptedData.project_id == project_id)
    if not data:
        raise HTTPException(status_code=404, detail="Data not found")
    await data.delete()
    return {"message": "Data deleted successfully"}