from __future__ import annotations
from dataclasses import dataclass,field
from decimal import Decimal
from typing import Type
from uuid import UUID, uuid4
from datetime import datetime
from collections import deque
import importlib


class EventMetaclass(type):
    def __new__(cls,*args,**kwargs):
        new_cls = super().__new__(cls,*args,**kwargs)
        return dataclass(frozen=True,kw_only=True)(new_cls)
    
class DomainEvent(metaclass=EventMetaclass):
    aggregate_id: UUID
    aggregate_version: int
    timestamp : datetime



#Helper functions
def get_topic(cls:type) -> str:
    """
    Returns a string that locates the given class
    """
    return f"{cls.__module__}#{cls.__qualname__}"

def resolve_topic(topic:str):
    """
    Returns a class located by the given string
    """
    module_name, _,class_name =topic.partition("#")
    module = importlib.import_module(module_name)
    return resolve_attr(module,class_name)

def resolve_attr(obj,path:str) -> type:
    #Base Case
    if not path:
        return obj
    
    #Recursive Case
    else:
        head,_,tail = path.partition(".")
        obj = getattr(obj,head)
        return resolve_attr(obj,tail)


@dataclass
class Aggregate:
    class NotAggregateError(Exception):
        pass
    class VersionError(Exception):
        pass
    

    class Event(DomainEvent):
        def mutate(self,obj:"Aggregate"|None) -> "Aggregate":
            """
            Changes the state of the aggregate
            according to domain event attriutes. 
            """
            #Check sequence
            if not isinstance(obj,Aggregate):
                raise Aggregate.NotAggregateError
            next_version = obj.version +1 
            if self.aggregate_version != next_version:
                raise obj.VersionError(
                    self.aggregate_version, next_version
                )
            #Update aggregate version #? Guess it should be encapsulated in apply method?
            obj.version = next_version

            obj.timestamp = self.timestamp

            #Project obj 
            self.apply(obj)
            return obj 

        def apply(self,obj) -> None:
            pass

    class Created(Event):
        """
        Domain event for creation of aggregate
        """

        aggregate_topic : str
        def mutate(self, obj: "Aggregate"|None) -> "Aggregate":
            #Copy the event attributes
            kwargs = self.__dict__.copy()
            id = kwargs.pop("aggregate_id")
            version = kwargs.pop("aggregate_version")

            #Get the root class from topicm, using helper function
            aggregate_class = resolve_topic(kwargs.pop("aggregate_topic"))

            return aggregate_class(id=id,version=version,**kwargs)

    @classmethod
    def _create_(
        cls,
        event_class: Type["Aggregate.Event"],
        **kwargs,
    ):
        event = event_class(
            aggregate_id = uuid4(), # Should it be managed on application?
            aggregate_version = 1,
            aggregate_topic = get_topic(cls),
            timestamp=datetime.now(),
            **kwargs
        )

        #Call Aggregate.Created.mutate
        aggregate = event.mutate(None)
        aggregate.pending_events.append(event)
        return aggregate

    def _trigger_(
        self,
        event_class: Type["Aggregate.Event"],
        **kwargs,
    )->None:
        """
        Triggers domain event of given type,
        extending the sequence of domain events for this aggregate object
        """
        next_version = self.version +1
        try:
            event = event_class(
                aggregate_id = self.id,
                aggregate_version = next_version,
                timestamp= datetime.now(),
                **kwargs,
            )
        except AttributeError:
            raise
        #Mutate aggregate with domain event
        event.mutate(self)

        #Append the domain event to pending events
        self.pending_events.append(event)

    def _collect_(self) -> list[Event]:
        """
        Collect pending events
        """
        collected = []
        while self.pending_events:
            collected.append(self.pending_events.popleft())
        return collected

    id:UUID
    version:int
    timestamp:datetime
    pending_events: deque[Event] = field(init=False)
    def __post_init__(self):
        self.pending_events = deque()



# Concrete class
@dataclass
class Account(Aggregate):
    full_name:str
    email_address: str
    balance: Decimal = Decimal("0.00")
    overdraft_limit: Decimal = Decimal("0.00")
    is_closed= False

    class Opened(Aggregate.Created):
        full_name:str
        email_address:str

    class TransactionAppended(Aggregate.Event):
        amount:Decimal
        def apply(self, account:"Account") -> None:
            account.balance += self.amount

    class OverdraftLimitSet(Aggregate.Event):
        overdraft_limit:Decimal
        def apply(self, account:"Account") -> None:
            account.overdraft_limit= self.overdraft_limit

    class Closed(Aggregate.Event):
        def apply(self,account:"Account")->None:
            account.is_closed = True
    
    #Exceptions
    class AccountClosedError(Exception):
        pass

    class InsufficientFundsError(Exception):
        pass

    @classmethod
    def open(
        cls,full_name:str,email_address:str
    ) -> "Account":
        """
        Create new bank account object
        """
        return super()._create_(
            cls.Opened,
            full_name=full_name,
            email_address=email_address
        )
    
    def check_account_is_not_closed(self)->None:
        if self.is_closed:
            raise self.AccountClosedError
    def check_has_sufficient_funds(
        self,amount:Decimal
    ) -> None:
        if self.balance + amount < -self.overdraft_limit:
            raise self.InsufficientFundsError({"account_id":self.id})
    
    def append_transaction(self,amount:Decimal) -> None:
        """
        Appends given amount as transaction on account
        """
        self.check_account_is_not_closed()
        self.check_has_sufficient_funds(amount)
        self._trigger_(
            self.TransactionAppended,
            amount=amount
        )
    def set_overdraft_limit(
        self,overdraft_limit:Decimal
    ) -> None:
        assert overdraft_limit >= Decimal("0.00")
        self.check_account_is_not_closed()
        self._trigger_(
            self.OverdraftLimitSet,
            overdraft_limit=overdraft_limit,
        )
    def close(self)->None:
        self._trigger_(self.Closed)
    

#Test
account = Account.open(full_name="Migo",email_address="test@mail.com")
assert account.full_name =="Migo"
assert account.email_address == "test@mail.com"
assert account.balance == 0 
account.append_transaction(Decimal("10"))
assert account.balance == Decimal("10")
account.append_transaction(Decimal("10"))
assert account.balance == Decimal("20")
account.append_transaction(Decimal("-15.00"))
assert account.balance == Decimal("5.00")

#fail to debit
try :
    account.append_transaction(Decimal("-15.00"))
except Account.InsufficientFundsError:
    print("Insufficient funds error raised")
    pass
else:
    raise Exception("Insufficient funds error not raised")

#Increase the overdraft limit
account.set_overdraft_limit(Decimal("100.00"))
account.append_transaction(Decimal("-15.00"))
assert account.balance == Decimal("-10.00")

#close the account
account.close()

try:
    account.append_transaction(Decimal("-15.00"))
except Account.AccountClosedError:
    print("Account has been closed.")

else:
    raise Exception("Account closed error not raised")

pending = account._collect_()
assert len(pending) ==7