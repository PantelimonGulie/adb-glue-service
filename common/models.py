from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

ORDER_ID = r"^(shop-\d+|emag-\d+)$"
SKU = r"^[A-Z0-9-]{1,32}$"


class OrderLine(BaseModel):
    sku: str = Field(pattern=SKU)
    qty: int = Field(ge=1, le=100)


class Order(BaseModel):
    id: str
    channel: Literal["shop", "emag"]
    channel_order_id: str = Field(pattern=r"^\d+$")
    lines: list[OrderLine]
    customer: str = Field(max_length=100)

    @model_validator(mode="after")
    def id_matches_channel(self) -> Self:
        if self.id != f"{self.channel}-{self.channel_order_id}":
            raise ValueError("id must be <channel>-<channel_order_id>")
        return self


class OrderRef(BaseModel):
    order_id: str = Field(pattern=ORDER_ID)


class StockAdjusted(BaseModel):
    sku: str = Field(pattern=SKU)
    on_hand: int = Field(ge=0)
    reserved: int = Field(ge=0)
    # Why the shelf was counted, when it was not a person, e.g. "demo restock".
    note: str = Field("", max_length=40)
    # Why the shelf was counted, when it was not a person, e.g. "demo restock".
    note: str = Field("", max_length=40)


class EmagNotification(BaseModel):
    order_id: int = Field(ge=1)
    type: Literal["new", "cancelled"]


class StockLevel(BaseModel):
    sku: str
    on_hand: int
    reserved: int
    available: int


class Event(BaseModel):
    type: str
    data: dict
