from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import Base, engine, get_db
from app.models import ServiceRequest
from app.schemas import CreateRequest
from app.security import require_permission

def serialize(item): return {column.name: getattr(item, column.name) for column in item.__table__.columns}

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield
app = FastAPI(title="HQS Service", version="2.0.0", lifespan=lifespan)

@app.get('/health/live')
def live(): return {'status':'alive'}
@app.get('/health/ready')
def ready(db: Session = Depends(get_db)):
    db.query(ServiceRequest).limit(1).all(); return {'status':'ready','database':'ok'}
@app.get('/internal/v1/dashboard')
def dashboard(db: Session = Depends(get_db), claims=Depends(require_permission('hqs.dashboard.view'))):
    values = dict(db.query(ServiceRequest.status, func.count(ServiceRequest.id)).group_by(ServiceRequest.status).all())
    return {'open': values.get('open',0), 'in_progress': values.get('in_progress',0), 'closed': values.get('closed',0)}
@app.get('/internal/v1/requests')
def list_requests(page:int=Query(1,ge=1), page_size:int=Query(20,ge=1,le=100), db:Session=Depends(get_db), claims=Depends(require_permission('hqs.requests.view'))):
    query=db.query(ServiceRequest); total=query.count(); rows=query.order_by(ServiceRequest.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {'items':[serialize(x) for x in rows], 'total':total, 'page':page, 'pages':max(1,(total+page_size-1)//page_size)}
@app.post('/internal/v1/requests', status_code=201)
def create_request(payload:CreateRequest, db:Session=Depends(get_db), claims=Depends(require_permission('hqs.requests.create'))):
    item=ServiceRequest(**payload.model_dump(), created_by=claims['sub']); db.add(item); db.commit(); db.refresh(item); return serialize(item)
