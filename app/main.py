from fastapi import Depends, FastAPI

from app.api import router
from app.security import require_api_key

app = FastAPI(title="Payments")
app.include_router(router, prefix="/api/v1", dependencies=[Depends(require_api_key)])
