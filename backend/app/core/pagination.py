from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)

    model_config = ConfigDict(frozen=True)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: Annotated[int, Query(ge=1)] = get_settings().default_page,
    page_size: Annotated[int, Query(ge=1, le=get_settings().max_page_size)] = get_settings().default_page_size,
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)
