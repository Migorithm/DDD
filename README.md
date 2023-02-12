# DDD - Event Sourced Model
Reference: Event Sourcing in Python - John Bywater


## What this project is for
This project is to explain and recap my own learning on DDD and especially event sourcing.<br>

## Domain Event - Stubborn facts.
At its core, domain model is what we use to make decisions. And those decisions become<br>
immutable facts. There is no object-relational impedance mismatch between a sequence<br>
of immutable facts and stored events.<br>

### Its values
- native types.
- custom value objects.
- non-root entities.
- maybe versioned
- maybe timestamped

```python
#Metaclass
class EventMetaclass(type):
    def __new__(cls,*args,**kwargs):
        new_cls = super().__new__(cls,*args,**kwargs)
        return dataclass(frozen=True,kw_only=True)(new_cls)
    
#Base Class For Common Attribute
class DomainEvent(metaclass=EventMetaclass):
    aggregate_id: UUID
    aggregate_version: int
    timestamp : datetime

#Concrete Event
class TransactionCreated(DomainEvent):
    pass


transaction_event = TransactionCreated(
    aggregate_id=aggregate_id,
    aggregate_version =2,
    timestamp=datetime.now()
)

```

## Aggregate
A model is 'projected' into the current state after rehydration. Aggregate is a cluster<br>
of domain objects that can be treated as a single unit when it comes to data changes.<br>
It has 'root entity' which is an access point to the cluster. The ID of the root is<br>
used as the ID of the aggregate. And it essentially makes usre of atomic transaction.<br><br>

The current status of event-sourced aggregate is defined by the function of its event objects.<br>
So, when an aggregates needs to be 'reconstructed', its domain event objects will be used.<br>
Bear in mind that each event object may cause many changes to the entities and value objects of<br>
the aggregate. The aggregate's projection MUST NOT trigger further domain event objects.<br>

### Helper functions
The following is helper functions to locate aggregate

```python
#Helper functions
def get_topic(cls:type) -> str:
    """
    Returns a string that locates the given class. 
    This will be used when creating aggregate for the first time.
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
```
The 'resolve_topic' method will recursively find the class. 

### Aggregate Base Class
```python
from collections import deque
from dataclasses import dataclass

@dataclass
class Aggregate:
    class NotAggregateError(Exception):
        pass
    class VersionError(Exception):
        pass
    class Event(DomainEvent):
        def mutate(self,obj:"Aggregate"|None) -> "Aggregate":
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

    class Created(Event):
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
            aggregate_id = uuid4(),
            aggregate_version = 1,
            aggregate_topic = get_topic(cls),
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
                timestamp= datetime.now()
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
    modified_on:datetime
    pending_events: deque[Event] = field(init=False)
    def __post_init__(self):
        self.pending_events = deque()



```

#### Domain Event in Aggregate
Aggregate.Event extends the vase class DomainEvent, A mutate() is defined for projection.<br>
The method is called with the 'previous state' of aggregate OR None as prior state<br>
in case of creation of aggregate. For this reason, if this method is implemented<br>
in subclasses, those methods much call super() and must always return an object.<br>
That's way mutate() method calls apply() which is NOT expected to return a value<br>
and does not necessarily need to call super().<br><br>

The nested class Aggregate.Created extends the base class Aggregate.Event.<br>
The mutate() method is overriden and resolves the aggregate_topic to an aggregate class.<br>

#### \_create\_()
Factory method which creates new aggregate object using the Created event class. 

#### \_trigger\_() 
This method will be used by command methods to create new domain event objects.<br>


#### \_collect\_()
This method drains the list of pending events and return a list of the events that are<br>
waiting to be recorded. 
