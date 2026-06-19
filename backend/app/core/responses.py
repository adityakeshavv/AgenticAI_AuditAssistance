from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


DataT = TypeVar("DataT")


class DetailResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: DataT

    model_config = ConfigDict(from_attributes=True)


class ListResponse(BaseModel, Generic[DataT]):
    success: bool = True
    count: int
    page: int
    page_size: int
    data: list[DataT]

    model_config = ConfigDict(from_attributes=True)
