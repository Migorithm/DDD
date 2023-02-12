from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(frozen=True)
class TransactionRequested:
    aggregate_id: UUID
    aggregate_version: int
    timestamp : datetime
    user_id : UUID


from uuid import uuid4

aggregate_id = uuid4()
user_id = uuid4()
event1 = TransactionRequested(
    aggregate_id=aggregate_id,
    aggregate_version=1,
    timestamp=datetime.now(),
    user_id=user_id,
)

assert isinstance(event1.aggregate_id,UUID)
assert event1.aggregate_id == aggregate_id
assert event1.aggregate_version == 1
assert isinstance(event1.timestamp,datetime)
assert event1.user_id == user_id


# Test attribute not changeable.
from dataclasses import FrozenInstanceError
try :
    event1.aggregate_id = uuid4()
except FrozenInstanceError:
    print("gotcha")


#Certainly, there must be commonality between events. Let's create baseclass

class EventMetaclass(type):
    def __new__(cls,*args,**kwargs):
        new_cls = super().__new__(cls,*args,**kwargs)
        return dataclass(frozen=True,kw_only=True)(new_cls)
    
class DomainEvent(metaclass=EventMetaclass):
    aggregate_id: UUID
    aggregate_version: int
    timestamp : datetime

class TransactionCreated(DomainEvent):
    pass


transaction_event = TransactionCreated(
    aggregate_id=aggregate_id,
    aggregate_version =2,
    timestamp=datetime.now()
)