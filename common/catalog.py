PRODUCTS = {
    "IPH16-128": "iPhone 16 · 128GB",
    "IPH16-256": "iPhone 16 · 256GB",
    "MBA-M4": "MacBook Air M4",
    "APP-3": "AirPods Pro 3",
    "IPAD-A16": "iPad A16",
    "WATCH-S10": "Apple Watch S10",
}


def product_name(sku: str) -> str:
    return PRODUCTS.get(sku, sku)
