"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Class name lowercased is the collection name (e.g., MenuItem -> "menuitem").
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

# Brand user example kept for reference
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class MenuItem(BaseModel):
    title: str = Field(..., description="Menu item name")
    description: Optional[str] = Field(None, description="Short description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: Literal[
        "Chicken Series", "Burger Series", "Rice Box", "Drinks", "Dessert"
    ] = Field(..., description="Menu category")
    image: Optional[str] = Field(None, description="Image path or URL")
    spicy: bool = Field(False, description="Is spicy")
    best_seller: bool = Field(False, description="Is best seller")
    is_new: bool = Field(False, description="Is new item")

class Promo(BaseModel):
    title: str
    code: str
    description: Optional[str] = None
    discount_percent: int = Field(ge=1, le=90)
    expires_at: Optional[str] = Field(None, description="ISO timestamp string")
    active: bool = True

class OrderItem(BaseModel):
    menu_id: str
    title: str
    price: float
    qty: int = Field(ge=1)

class Order(BaseModel):
    customer_name: Optional[str] = None
    type: Literal["pickup", "delivery"] = "pickup"
    address: Optional[str] = None
    items: List[OrderItem]
    subtotal: float
    discount: float = 0
    total: float
    status: Literal["Received", "Cooking", "On the way", "Delivered"] = "Received"

# Nutrition request model (for AI nutrition info)
class NutritionRequest(BaseModel):
    menu_id: str

# Recommendation request model
class RecommendationRequest(BaseModel):
    spicy: Literal["pedas", "non pedas"]
    budget: float
    party: Literal["sendiri", "rame"]
