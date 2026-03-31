from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
import httpx
import secrets
import uuid
from bson import ObjectId

# Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://admin:mongo_dev_password@localhost:27017/users-db?authSource=admin")
JWT_SECRET = os.getenv("JWT_SECRET", "user_api_jwt_secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Medusa Integration Configuration
MEDUSA_BACKEND_URL = os.getenv("MEDUSA_BACKEND_URL", "http://localhost:9000")
MEDUSA_PUBLISHABLE_KEY = os.getenv("MEDUSA_PUBLISHABLE_KEY", "")
MEDUSA_ADMIN_EMAIL = os.getenv("MEDUSA_ADMIN_EMAIL", "admin@abtattoo.com")
MEDUSA_ADMIN_PASSWORD = os.getenv("MEDUSA_ADMIN_PASSWORD", "ABTattooAdmin2024")

# Initialize FastAPI
app = FastAPI(
    title="AB-Tattoo User Management API",
    description="Professional user management for AB-Tattoo Supplies E-commerce",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()

# MongoDB client
mongodb_client: Optional[AsyncIOMotorClient] = None

# Pydantic Models
class UserBase(BaseModel):
    email: EmailStr
    studio_name: str = Field(..., min_length=2, max_length=200, description="Tattoo studio name")
    tattoo_license: Optional[str] = Field(None, max_length=50, description="Professional tattoo license number")
    tax_id: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    specialties: Optional[List[str]] = Field(None, description="Tattoo specialties (e.g., traditional, realism, blackwork)")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    studio_name: Optional[str] = None
    tattoo_license: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    specialties: Optional[List[str]] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleAuthRequest(BaseModel):
    token: str  # Google ID token from frontend

# ============================================
# ADDRESS MODELS
# ============================================

class AddressBase(BaseModel):
    label: Optional[str] = Field(None, max_length=100, description="Label (e.g., 'Estudio principal')")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    company: Optional[str] = Field(None, max_length=200)
    address_1: str = Field(..., min_length=1, max_length=300)
    address_2: Optional[str] = Field(None, max_length=300)
    city: str = Field(..., min_length=1, max_length=100)
    province: Optional[str] = Field(None, max_length=100)
    postal_code: str = Field(..., min_length=1, max_length=20)
    country_code: str = Field("es", max_length=2)
    phone: Optional[str] = Field(None, max_length=20)

class BillingAddressInput(AddressBase):
    tax_id: Optional[str] = Field(None, max_length=50, description="NIF/CIF for invoicing")

class ShippingAddressInput(AddressBase):
    is_default: bool = False

class BillingAddressResponse(AddressBase):
    tax_id: Optional[str] = None

class ShippingAddressResponse(AddressBase):
    id: str
    is_default: bool = False

class UserResponse(BaseModel):
    id: str
    email: str
    studio_name: str
    tattoo_license: Optional[str] = None
    tax_id: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    specialties: List[str] = []
    status: str
    auth_provider: str = "email"
    medusa_customer_id: Optional[str] = None
    billing_address: Optional[dict] = None
    shipping_addresses: list = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Helper functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    db = mongodb_client.get_database()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user is None:
        raise credentials_exception
    return user

def user_document_to_response(user_doc: dict) -> UserResponse:
    return UserResponse(
        id=str(user_doc["_id"]),
        email=user_doc["email"],
        studio_name=user_doc.get("studio_name", "My Studio"),
        tattoo_license=user_doc.get("tattoo_license"),
        tax_id=user_doc.get("tax_id"),
        phone=user_doc.get("phone"),
        address=user_doc.get("address"),
        city=user_doc.get("city"),
        country=user_doc.get("country"),
        postal_code=user_doc.get("postal_code"),
        specialties=user_doc.get("specialties", []),
        status=user_doc.get("status", "pending"),
        auth_provider=user_doc.get("auth_provider", "email"),
        medusa_customer_id=user_doc.get("medusa_customer_id"),
        billing_address=user_doc.get("billing_address"),
        shipping_addresses=user_doc.get("shipping_addresses", []),
        created_at=user_doc["created_at"],
        updated_at=user_doc["updated_at"]
    )

async def verify_google_token(token: str) -> dict:
    """Verify Google ID token and return user info"""
    async with httpx.AsyncClient() as client:
        # Verify the token with Google
        response = await client.get(
            f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token"
            )
        
        token_info = response.json()
        
        # Verify the token is for our app
        if token_info.get("aud") != GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token not valid for this application"
            )
        
        return {
            "email": token_info.get("email"),
            "name": token_info.get("name"),
            "picture": token_info.get("picture"),
            "google_id": token_info.get("sub")
        }

# ============================================
# MEDUSA INTEGRATION HELPERS
# ============================================

_medusa_admin_token: Optional[str] = None
_medusa_token_time: float = 0

async def get_medusa_admin_token() -> Optional[str]:
    """Get cached admin token or authenticate with Medusa Admin API"""
    global _medusa_admin_token, _medusa_token_time
    import time
    # Reuse cached token for up to 50 minutes
    if _medusa_admin_token and (time.time() - _medusa_token_time) < 3000:
        return _medusa_admin_token
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{MEDUSA_BACKEND_URL}/auth/user/emailpass",
                json={"email": MEDUSA_ADMIN_EMAIL, "password": MEDUSA_ADMIN_PASSWORD}
            )
            if response.status_code == 200:
                import time
                _medusa_admin_token = response.json().get("token")
                _medusa_token_time = time.time()
                return _medusa_admin_token
            else:
                print(f"Medusa admin auth failed: {response.status_code} {response.text}")
                print(f"  → Using email: {MEDUSA_ADMIN_EMAIL}")
                print(f"  → Verify credentials match the admin user created in Medusa")
    except Exception as e:
        print(f"Error getting Medusa admin token: {e}")
    return None


async def create_medusa_customer(email: str, first_name: str, last_name: str = "") -> Optional[str]:
    """Create a customer in Medusa via Admin API. Returns customer ID or None."""
    token = await get_medusa_admin_token()
    if not token:
        print("Could not get Medusa admin token, skipping customer creation")
        return None
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{MEDUSA_BACKEND_URL}/admin/customers",
                json={
                    "email": email,
                    "first_name": first_name or "Studio",
                    "last_name": last_name or "",
                },
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code in (200, 201):
                customer = response.json().get("customer", {})
                customer_id = customer.get("id")
                print(f"Created Medusa customer {customer_id} for {email}")
                return customer_id
            else:
                print(f"Failed to create Medusa customer: {response.status_code} {response.text}")
                return None
    except Exception as e:
        print(f"Error creating Medusa customer: {e}")
        return None


async def ensure_medusa_customer(user_doc: dict, db) -> Optional[str]:
    """Ensure user has a Medusa customer ID. Creates one if missing (on-demand sync)."""
    if user_doc.get("medusa_customer_id"):
        return user_doc["medusa_customer_id"]
    
    customer_id = await create_medusa_customer(
        email=user_doc["email"],
        first_name=user_doc.get("studio_name", "Studio"),
    )
    
    if customer_id:
        await db.users.update_one(
            {"_id": user_doc["_id"]},
            {"$set": {"medusa_customer_id": customer_id, "updated_at": datetime.utcnow()}}
        )
    
    return customer_id

# Startup and shutdown events
@app.on_event("startup")
async def startup_db_client():
    global mongodb_client
    mongodb_client = AsyncIOMotorClient(MONGODB_URL)
    # Create indexes
    db = mongodb_client.get_database()
    await db.users.create_index("email", unique=True)
    await db.users.create_index("google_id", sparse=True)
    print("Connected to MongoDB")

@app.on_event("shutdown")
async def shutdown_db_client():
    if mongodb_client:
        mongodb_client.close()
    print("Disconnected from MongoDB")

# Routes
@app.get("/")
async def root():
    return {"message": "AB-Tattoo User Management API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "database": "connected"}

@app.post("/api/users/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    db = mongodb_client.get_database()
    
    # Check if email exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user document
    user_doc = {
        "email": user.email,
        "password_hash": get_password_hash(user.password),
        "studio_name": user.studio_name,
        "tattoo_license": user.tattoo_license,
        "tax_id": user.tax_id,
        "phone": user.phone,
        "address": user.address,
        "city": user.city,
        "country": user.country,
        "postal_code": user.postal_code,
        "specialties": user.specialties or [],
        "status": "pending",
        "auth_provider": "email",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    
    # Create Medusa customer (best effort, don't block registration)
    medusa_customer_id = await create_medusa_customer(
        email=user.email,
        first_name=user.studio_name,
    )
    if medusa_customer_id:
        user_doc["medusa_customer_id"] = medusa_customer_id
        await db.users.update_one(
            {"_id": result.inserted_id},
            {"$set": {"medusa_customer_id": medusa_customer_id}}
        )
    
    access_token = create_access_token({"sub": str(result.inserted_id)})
    
    return Token(
        access_token=access_token,
        user=user_document_to_response(user_doc)
    )

@app.post("/api/users/login", response_model=Token)
async def login_user(credentials: UserLogin):
    db = mongodb_client.get_database()
    
    user = await db.users.find_one({"email": credentials.email})
    
    # Check if user exists and has a password (not Google-only account)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if user.get("auth_provider") == "google" and not user.get("password_hash"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account uses Google Sign-In. Please use 'Continue with Google'."
        )
    
    if not verify_password(credentials.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Ensure Medusa customer exists (on-demand sync for existing users)
    db = mongodb_client.get_database()
    medusa_customer_id = await ensure_medusa_customer(user, db)
    if medusa_customer_id:
        user["medusa_customer_id"] = medusa_customer_id
    
    access_token = create_access_token({"sub": str(user["_id"])})
    
    return Token(
        access_token=access_token,
        user=user_document_to_response(user)
    )

# Google OAuth Routes
@app.post("/api/auth/google", response_model=Token)
async def google_auth(auth_request: GoogleAuthRequest):
    """
    Authenticate with Google using ID token from frontend.
    Creates a new user if they don't exist, or logs in existing user.
    """
    db = mongodb_client.get_database()
    
    # Verify the Google token
    google_user = await verify_google_token(auth_request.token)
    
    # Check if user exists
    existing_user = await db.users.find_one({"email": google_user["email"]})
    
    if existing_user:
        # Update Google ID if not set
        if not existing_user.get("google_id"):
            await db.users.update_one(
                {"_id": existing_user["_id"]},
                {"$set": {
                    "google_id": google_user["google_id"],
                    "auth_provider": "google",
                    "updated_at": datetime.utcnow()
                }}
            )
            existing_user = await db.users.find_one({"_id": existing_user["_id"]})
        
        # Ensure Medusa customer exists (on-demand sync)
        medusa_customer_id = await ensure_medusa_customer(existing_user, db)
        if medusa_customer_id:
            existing_user["medusa_customer_id"] = medusa_customer_id
        
        access_token = create_access_token({"sub": str(existing_user["_id"])})
        return Token(
            access_token=access_token,
            user=user_document_to_response(existing_user)
        )
    
    # Create new user from Google data
    user_doc = {
        "email": google_user["email"],
        "google_id": google_user["google_id"],
        "studio_name": google_user.get("name", "My Studio"),
        "tattoo_license": None,
        "tax_id": None,
        "phone": None,
        "address": None,
        "city": None,
        "country": None,
        "postal_code": None,
        "specialties": [],
        "status": "pending",
        "auth_provider": "google",
        "profile_picture": google_user.get("picture"),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    result = await db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    
    # Create Medusa customer for new Google user (best effort)
    medusa_customer_id = await create_medusa_customer(
        email=google_user["email"],
        first_name=google_user.get("name", "My Studio"),
    )
    if medusa_customer_id:
        user_doc["medusa_customer_id"] = medusa_customer_id
        await db.users.update_one(
            {"_id": result.inserted_id},
            {"$set": {"medusa_customer_id": medusa_customer_id}}
        )
    
    access_token = create_access_token({"sub": str(result.inserted_id)})
    
    return Token(
        access_token=access_token,
        user=user_document_to_response(user_doc)
    )

@app.get("/api/users/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    db = mongodb_client.get_database()
    # Ensure Medusa customer exists (on-demand sync)
    await ensure_medusa_customer(current_user, db)
    # Re-fetch to get updated data
    updated_user = await db.users.find_one({"_id": current_user["_id"]})
    return user_document_to_response(updated_user or current_user)

@app.get("/api/users/me/orders")
async def get_user_orders(current_user: dict = Depends(get_current_user)):
    """Get orders from Medusa for the current user"""
    db = mongodb_client.get_database()
    
    # Ensure user has a Medusa customer
    customer_id = await ensure_medusa_customer(current_user, db)
    if not customer_id:
        return {"orders": [], "count": 0}
    
    token = await get_medusa_admin_token()
    if not token:
        return {"orders": [], "count": 0}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{MEDUSA_BACKEND_URL}/admin/orders",
                params={"customer_id": customer_id, "limit": 50, "order": "-created_at"},
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 200:
                data = response.json()
                return {"orders": data.get("orders", []), "count": data.get("count", 0)}
            else:
                print(f"Failed to fetch orders from Medusa: {response.status_code}")
                return {"orders": [], "count": 0}
    except Exception as e:
        print(f"Error fetching orders: {e}")
        return {"orders": [], "count": 0}

@app.put("/api/users/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = mongodb_client.get_database()
    
    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    if not update_data:
        return user_document_to_response(current_user)
    
    update_data["updated_at"] = datetime.utcnow()
    
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": update_data}
    )
    
    updated_user = await db.users.find_one({"_id": current_user["_id"]})
    return user_document_to_response(updated_user)

@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(user_id: str, current_user: dict = Depends(get_current_user)):
    if str(current_user["_id"]) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this user"
        )
    
    db = mongodb_client.get_database()
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user_document_to_response(user)

# ============================================
# ADDRESS MANAGEMENT ENDPOINTS
# ============================================

@app.get("/api/users/me/addresses")
async def get_addresses(current_user: dict = Depends(get_current_user)):
    """Get user's billing address and all shipping addresses"""
    return {
        "billing_address": current_user.get("billing_address"),
        "shipping_addresses": current_user.get("shipping_addresses", []),
    }

@app.put("/api/users/me/billing-address")
async def set_billing_address(
    address: BillingAddressInput,
    current_user: dict = Depends(get_current_user)
):
    """Set or update the billing/fiscal address"""
    db = mongodb_client.get_database()
    address_data = address.dict()
    
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"billing_address": address_data, "updated_at": datetime.utcnow()}}
    )
    
    return {"billing_address": address_data}

@app.delete("/api/users/me/billing-address")
async def delete_billing_address(current_user: dict = Depends(get_current_user)):
    """Remove the billing address"""
    db = mongodb_client.get_database()
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"billing_address": None, "updated_at": datetime.utcnow()}}
    )
    return {"billing_address": None}

@app.post("/api/users/me/shipping-addresses", status_code=status.HTTP_201_CREATED)
async def add_shipping_address(
    address: ShippingAddressInput,
    current_user: dict = Depends(get_current_user)
):
    """Add a new shipping address"""
    db = mongodb_client.get_database()
    
    address_data = address.dict()
    address_data["id"] = str(uuid.uuid4())
    
    existing = current_user.get("shipping_addresses", [])
    
    # If this is the first address or marked as default, set it as default
    if address_data.get("is_default") or len(existing) == 0:
        # Unset default on all existing addresses
        for addr in existing:
            addr["is_default"] = False
        address_data["is_default"] = True
    
    existing.append(address_data)
    
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"shipping_addresses": existing, "updated_at": datetime.utcnow()}}
    )
    
    return {"shipping_address": address_data, "shipping_addresses": existing}

@app.put("/api/users/me/shipping-addresses/{address_id}")
async def update_shipping_address(
    address_id: str,
    address: ShippingAddressInput,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing shipping address"""
    db = mongodb_client.get_database()
    
    existing = current_user.get("shipping_addresses", [])
    found = False
    
    for i, addr in enumerate(existing):
        if addr.get("id") == address_id:
            updated = address.dict()
            updated["id"] = address_id
            
            # If setting as default, unset others
            if updated.get("is_default"):
                for other in existing:
                    other["is_default"] = False
            
            existing[i] = updated
            found = True
            break
    
    if not found:
        raise HTTPException(status_code=404, detail="Shipping address not found")
    
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"shipping_addresses": existing, "updated_at": datetime.utcnow()}}
    )
    
    return {"shipping_address": existing[i], "shipping_addresses": existing}

@app.delete("/api/users/me/shipping-addresses/{address_id}")
async def delete_shipping_address(
    address_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a shipping address"""
    db = mongodb_client.get_database()
    
    existing = current_user.get("shipping_addresses", [])
    updated = [a for a in existing if a.get("id") != address_id]
    
    if len(updated) == len(existing):
        raise HTTPException(status_code=404, detail="Shipping address not found")
    
    # If the deleted one was default, set first remaining as default
    if updated and not any(a.get("is_default") for a in updated):
        updated[0]["is_default"] = True
    
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"shipping_addresses": updated, "updated_at": datetime.utcnow()}}
    )
    
    return {"shipping_addresses": updated}

@app.put("/api/users/me/shipping-addresses/{address_id}/default")
async def set_default_shipping_address(
    address_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Set a shipping address as default"""
    db = mongodb_client.get_database()
    
    existing = current_user.get("shipping_addresses", [])
    found = False
    
    for addr in existing:
        if addr.get("id") == address_id:
            addr["is_default"] = True
            found = True
        else:
            addr["is_default"] = False
    
    if not found:
        raise HTTPException(status_code=404, detail="Shipping address not found")
    
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"shipping_addresses": existing, "updated_at": datetime.utcnow()}}
    )
    
    return {"shipping_addresses": existing}

# ============================================
# CONTACT FORM
# ============================================

class ContactMessage(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    subject: str = Field(..., min_length=1, max_length=300)
    message: str = Field(..., min_length=1, max_length=5000)

@app.post("/api/contact")
async def submit_contact_message(data: ContactMessage):
    """
    Receive a contact form submission.
    Stores the message in MongoDB and optionally sends an email notification.
    """
    db = mongodb_client.get_database()

    contact_doc = {
        "name": data.name,
        "email": data.email,
        "subject": data.subject,
        "message": data.message,
        "status": "unread",
        "created_at": datetime.utcnow(),
    }

    result = await db.contact_messages.insert_one(contact_doc)

    # TODO: SMTP — Send email notification
    # When SMTP credentials are available, uncomment and configure:
    #
    # import aiosmtplib
    # from email.message import EmailMessage
    #
    # SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    # SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    # SMTP_USER = os.getenv("SMTP_USER", "")
    # SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    # CONTACT_RECIPIENT = os.getenv("CONTACT_EMAIL", "info@abtattoo.com")
    #
    # if SMTP_USER and SMTP_PASSWORD:
    #     try:
    #         msg = EmailMessage()
    #         msg["From"] = SMTP_USER
    #         msg["To"] = CONTACT_RECIPIENT
    #         msg["Subject"] = f"[AB Tattoo - Contacto] {data.subject}"
    #         msg.set_content(
    #             f"Nombre: {data.name}\n"
    #             f"Email: {data.email}\n"
    #             f"Asunto: {data.subject}\n\n"
    #             f"Mensaje:\n{data.message}"
    #         )
    #         await aiosmtplib.send(
    #             msg,
    #             hostname=SMTP_HOST,
    #             port=SMTP_PORT,
    #             username=SMTP_USER,
    #             password=SMTP_PASSWORD,
    #             start_tls=True,
    #         )
    #     except Exception as e:
    #         print(f"Error sending contact email: {e}")
    #         # Don't fail the request if email fails — message is already saved

    return {
        "success": True,
        "message": "Mensaje recibido correctamente. Te responderemos lo antes posible.",
        "id": str(result.inserted_id),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
