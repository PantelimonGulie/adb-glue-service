from pydantic import BaseModel


class OrderLine(BaseModel):
    sku: str
    qty: int


class Order(BaseModel):
    id: str
    channel: str
    channel_order_id: str
    lines: list[OrderLine]
    customer: str


class StockLevel(BaseModel):
    sku: str
    on_hand: int
    reserved: int
    available: int


class Event(BaseModel):
    type: str
    data: dict
