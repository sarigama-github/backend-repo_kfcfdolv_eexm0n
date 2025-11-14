import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson.objectid import ObjectId
from datetime import datetime, timedelta, timezone

from database import db, create_document, get_documents
from schemas import MenuItem, Promo, Order, RecommendationRequest

app = FastAPI(title="BOSKIING API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers

def oid_str(v):
    return str(v) if isinstance(v, ObjectId) else v


def serialize(doc):
    if not doc:
        return doc
    d = {k: v for k, v in doc.items() if k != "_id"}
    d["id"] = oid_str(doc.get("_id"))
    return d


@app.get("/")
def read_root():
    return {"message": "BOSKIING Backend Running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, "name") else "✅ Connected"
            response["connection_status"] = "Connected"
            collections = db.list_collection_names()
            response["collections"] = collections[:10]
            response["database"] = "✅ Connected & Working"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


@app.post("/api/seed")
def seed_data():
    # Seed menu items and promos if empty
    menu_count = db["menuitem"].count_documents({}) if db else 0
    promo_count = db["promo"].count_documents({}) if db else 0

    seeded = {"menu": False, "promos": False}

    if menu_count == 0:
        items: List[MenuItem] = [
            MenuItem(title="Boss Bucket", description="Bucket ayam crispy signature.", price=19.99, category="Chicken Series", image="/assets/hero-chicken.svg", spicy=True, best_seller=True),
            MenuItem(title="King Burger Deluxe", description="Burger premium juicy dengan keju.", price=7.99, category="Burger Series", image="/assets/burger.svg", spicy=False, best_seller=True, is_new=True),
            MenuItem(title="Golden Rice Box", description="Nasi hangat dengan ayam fillet.", price=5.49, category="Rice Box", image="/assets/ricebox.svg", spicy=False),
            MenuItem(title="Crinkle Fries", description="Kentang goreng renyah.", price=2.49, category="Drinks", image="/assets/fries.svg", spicy=False),
            MenuItem(title="Cola Fizz", description="Soft drink segar.", price=1.99, category="Drinks", image="/assets/softdrink.svg"),
            MenuItem(title="Royal Sundae", description="Dessert lembut manis.", price=2.99, category="Dessert", image="/assets/dessert.svg", is_new=True),
        ]
        docs = [i.model_dump() for i in items]
        for d in docs:
            db["menuitem"].insert_one({**d, "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)})
        seeded["menu"] = True

    if promo_count == 0:
        now = datetime.now(timezone.utc)
        promos = [
            Promo(title="Boss Week Deal", code="BOSS10", description="Diskon 10% semua menu.", discount_percent=10, expires_at=(now + timedelta(days=7)).isoformat(), active=True),
            Promo(title="King Combo", code="KING15", description="Paket combo hemat.", discount_percent=15, expires_at=(now + timedelta(days=2)).isoformat(), active=True),
        ]
        for p in promos:
            db["promo"].insert_one({**p.model_dump(), "created_at": now, "updated_at": now})
        seeded["promos"] = True

    return {"seeded": seeded}


@app.get("/api/menu")
def get_menu(category: Optional[str] = None, q: Optional[str] = Query(None, description="search query")):
    filter_q = {}
    if category:
        filter_q["category"] = category
    if q:
        filter_q["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    items = list(db["menuitem"].find(filter_q))
    return [serialize(x) for x in items]


@app.get("/api/promos")
def get_promos():
    now = datetime.now(timezone.utc)
    promos = list(db["promo"].find({"active": True}))
    out = []
    for p in promos:
        expires_at = p.get("expires_at")
        remaining = None
        if expires_at:
            try:
                exp_dt = datetime.fromisoformat(expires_at)
            except Exception:
                exp_dt = now
            delta = exp_dt - now
            remaining = max(0, int(delta.total_seconds()))
        d = serialize(p)
        d["seconds_left"] = remaining
        out.append(d)
    return out


class OrderCreate(BaseModel):
    customer_name: Optional[str] = None
    type: str = "pickup"
    address: Optional[str] = None
    items: list
    subtotal: float
    discount: float = 0
    total: float


@app.post("/api/order")
def create_order(payload: OrderCreate):
    order = Order(
        customer_name=payload.customer_name,
        type=payload.type if payload.type in ["pickup", "delivery"] else "pickup",
        address=payload.address,
        items=payload.items,  # validated client-side; stored as-is
        subtotal=payload.subtotal,
        discount=payload.discount,
        total=payload.total,
    )
    order_id = db["order"].insert_one({**order.model_dump(), "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc)}).inserted_id
    return {"order_id": str(order_id), "status": order.status}


@app.get("/api/order/{order_id}")
def get_order(order_id: str):
    try:
        doc = db["order"].find_one({"_id": ObjectId(order_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order id")
    if not doc:
        raise HTTPException(status_code=404, detail="Order not found")
    return serialize(doc)


@app.patch("/api/order/{order_id}/status")
def update_order_status(order_id: str, status: str):
    if status not in ["Received", "Cooking", "On the way", "Delivered"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    try:
        res = db["order"].update_one({"_id": ObjectId(order_id)}, {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid order id")
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order_id": order_id, "status": status}


@app.post("/api/recommend")
def recommend(req: RecommendationRequest):
    # Simple rule-based recommender using budget/spicy/party
    q = {}
    if req.spicy == "pedas":
        q["spicy"] = True
    # get items sorted by best_seller desc then price asc
    items = list(db["menuitem"].find(q).sort([("best_seller", -1), ("price", 1)]))
    # budget filter
    items_budget = [i for i in items if float(i.get("price", 0)) <= float(req.budget) + 0.01] or items
    # party size
    if req.party == "rame":
        # prefer larger items like bucket or combos (by keywords) or higher price
        items_budget.sort(key=lambda x: ("bucket" in x.get("title", "").lower(), x.get("price", 0)), reverse=True)
    recs = []
    for it in items_budget[:3]:
        reason = []
        if req.spicy == "pedas" and it.get("spicy"):
            reason.append("pedas mantap")
        if it.get("best_seller"):
            reason.append("best seller")
        if float(it.get("price", 0)) <= req.budget:
            reason.append("sesuai budget")
        if req.party == "rame" and ("bucket" in it.get("title", "").lower() or it.get("price", 0) > 6):
            reason.append("cocok untuk rame-rame")
        recs.append({"item": serialize(it), "reason": ", ".join(reason) or "recommended"})
    return {"recommendations": recs}


@app.get("/api/nutrition/{menu_id}")
def nutrition(menu_id: str):
    try:
        doc = db["menuitem"].find_one({"_id": ObjectId(menu_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")
    if not doc:
        raise HTTPException(status_code=404, detail="Menu not found")
    # Mock nutrition estimation based on category and price
    base = {
        "Chicken Series": 750,
        "Burger Series": 650,
        "Rice Box": 700,
        "Drinks": 180,
        "Dessert": 420,
    }
    price = float(doc.get("price", 0))
    cal = int(base.get(doc.get("category"), 500) * (0.9 + min(price, 12) / 40))
    protein = int((cal / 10) * (1.2 if doc.get("category") in ["Chicken Series", "Rice Box"] else 0.6))
    suggestion = "Pilih air mineral dan tambah salad untuk seimbang." if doc.get("category") in ["Burger Series", "Chicken Series"] else "Nikmati secukupnya."
    return {"id": str(doc.get("_id")), "calories": cal, "protein": protein, "suggestion": suggestion}


@app.get("/schema")
def schema_info():
    # Minimal schema info for inspector tools
    return {"collections": ["menuitem", "promo", "order"]}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
