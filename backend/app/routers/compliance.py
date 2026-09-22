"""RUO / age acknowledgment audit log.

This exists so that if anyone ever asks whether visitors were shown and
accepted the research-use terms, there is a dated record rather than an
assertion. It deliberately stores no personally identifying data.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import RuoAcknowledgment
from ..schemas import Ok, RuoAckIn
from ..security import client_ip, hash_ip, limiter

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/ruo-ack", response_model=Ok)
@limiter.limit("30/minute")
def acknowledge(payload: RuoAckIn, request: Request, db: Session = Depends(get_db)):
    db.add(RuoAcknowledgment(
        ip_hash=hash_ip(client_ip(request)),
        user_agent=request.headers.get("user-agent", "")[:500],
        path=payload.path[:255],
    ))
    db.commit()
    return Ok(detail="Acknowledgment recorded.")
