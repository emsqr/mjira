from fastapi import Depends, HTTPException, status

from shared.jwt_utils import CurrentUser, get_current_user


def require_tenant(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if current.tenant_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Token has no tenant context — log in with a tenant_slug",
        )
    return current
