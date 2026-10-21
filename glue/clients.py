from urllib.parse import quote

import httpx

from common.models import Order


def segment(value: str) -> str:
    return quote(value, safe="")


class ShopClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str):
        self.http = http
        self.base_url = base_url

    async def set_stock(self, sku: str, qty: int) -> httpx.Response:
        url = f"{self.base_url}/V1/products/{segment(sku)}/stockItems"
        return await self.http.put(url, json={"qty": qty})

    async def mark_shipped(self, order_id: str) -> httpx.Response:
        return await self.http.post(f"{self.base_url}/V1/order/{segment(order_id)}/ship")

    async def cancel(self, order_id: str) -> httpx.Response:
        return await self.http.post(f"{self.base_url}/V1/orders/{segment(order_id)}/cancel")

    async def health(self) -> httpx.Response:
        return await self.http.get(f"{self.base_url}/health")


class EmagClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str):
        self.http = http
        self.base_url = base_url

    async def read_order(self, order_id: int) -> httpx.Response:
        return await self.http.post(f"{self.base_url}/api-3/order/read", json={"id": order_id})

    async def acknowledge(self, order_id: int) -> httpx.Response:
        return await self.http.post(
            f"{self.base_url}/api-3/order/acknowledge", json={"id": order_id}
        )

    async def set_status(self, order_id: int, status: int) -> httpx.Response:
        return await self.http.post(
            f"{self.base_url}/api-3/order/save", json={"id": order_id, "status": status}
        )

    async def save_offers(self, offers: list[tuple[str, int]]) -> httpx.Response:
        body = [{"part_number": sku, "stock": stock} for sku, stock in offers]
        return await self.http.post(f"{self.base_url}/api-3/product_offer/save", json=body)

    async def health(self) -> httpx.Response:
        return await self.http.get(f"{self.base_url}/health")


class WarehouseClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str):
        self.http = http
        self.base_url = base_url

    async def create_order(self, order: Order) -> httpx.Response:
        return await self.http.post(
            f"{self.base_url}/orders",
            json=order.model_dump(),
            headers={"Idempotency-Key": order.id},
        )

    async def cancel_order(self, order_id: str) -> httpx.Response:
        return await self.http.post(f"{self.base_url}/orders/{segment(order_id)}/cancel")

    async def stock(self) -> httpx.Response:
        return await self.http.get(f"{self.base_url}/stock")

    async def health(self) -> httpx.Response:
        return await self.http.get(f"{self.base_url}/health")
