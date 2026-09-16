"""Roles (plan.md §10 «Админка»): the five roles of ТЗ п. 16 with their permissions.

Contract stub: answers 501 until T-38. Only the Администратор reads roles (ADR-008). The set of
roles is fixed and the role → permission matrix comes from T-20, so there is nothing to change.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Security

from app.core.deps import PageParams, page_params, user_token
from app.core.errors import not_implemented
from app.schemas.users import RoleListItemPage

router = APIRouter(prefix="/roles", tags=["admin"], dependencies=[Security(user_token)])


@router.get(
    "",
    summary="Роли и их права",
    description="Пять ролей ТЗ п. 16 в порядке school, district, oblast, provider, admin.",
)
async def list_roles(params: Annotated[PageParams, Depends(page_params)]) -> RoleListItemPage:
    raise not_implemented("T-38")
