"""Farmer profile read/update (only the fields the app actually needs)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import User, get_db
from ..schemas import ProfileUpdateIn, UserOut
from ..security import get_current_user, hash_password

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/profile", response_model=UserOut)
def get_profile(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.put("/profile", response_model=UserOut)
def update_profile(
    payload: ProfileUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    for field in ("name", "language", "village", "state"):
        if field in data and data[field] is not None:
            setattr(user, field, data[field])
    if password:
        user.password_hash = hash_password(password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
