# src/Object.py
# -*- coding: iso-8859-1 -*-

import pickle
import io
import Log


class Serializer(pickle.Pickler):
    def persistent_id(self, obj):
        return getattr(obj, "id", None)


class Unserializer(pickle.Unpickler):
    def __init__(self, manager, data):
        super().__init__(data)
        self.manager = manager

    def persistent_load(self, obj_id):
        return self.manager.getObject(obj_id)


def serialize(data) -> bytes:
    """Serialize Python object -> bytes (pickle protocol 2 for compatibility)."""
    bio = io.BytesIO()
    Serializer(bio, protocol=2).dump(data)
    return bio.getvalue()


def unserialize(manager, data):
    """Unserialize bytes -> Python object."""
    if isinstance(data, str):
        # Migration edge-case: preserve original byte values (Py2 style).
        data = data.encode("latin-1", "strict")
    return Unserializer(manager, io.BytesIO(data)).load()


class Manager:
    MSG_CREATE = 0
    MSG_CHANGE = 1
    MSG_DELETE = 2

    def __init__(self, id=0):
        self.id = id
        self.reset()

    def setId(self, id):
        self.id = id

    def reset(self):
        self.objects = {}
        self.__creationData = {}
        self.__created = []
        self.__changed = []
        self.__deleted = []
        self.__idCounter = 0

    def createObject(self, instance, *args, **kwargs):
        self.__idCounter += 1
        obj_id = self.globalObjectId(self.__idCounter)
        self.objects[obj_id] = instance
        self.__creationData[obj_id] = (instance.__class__, args, kwargs)
        self.__created.append(instance)
        return obj_id

    def setChanged(self, obj):
        if obj not in self.__changed:
            self.__changed.append(obj)

    def deleteObject(self, obj):
        del self.objects[obj.id]
        del self.__creationData[obj.id]
        if obj in self.__created:
            self.__created.remove(obj)
        self.__deleted.append(obj.id)

    def getObject(self, obj_id):
        return self.objects.get(obj_id, None)

    def getChanges(self, everything=False):
        data = []
        if everything:
            data.append(
                (
                    self.MSG_CREATE,
                    [(obj_id, d) for obj_id, d in self.__creationData.items()],
                )
            )
            data.append(
                (
                    self.MSG_CHANGE,
                    [
                        (o.id, o.getChanges(everything=True))
                        for o in self.objects.values()
                    ],
                )
            )
        else:
            if self.__created:
                data.append(
                    (
                        self.MSG_CREATE,
                        [(o.id, self.__creationData[o.id]) for o in self.__created],
                    )
                )
            if self.__changed:
                data.append(
                    (self.MSG_CHANGE, [(o.id, o.getChanges()) for o in self.__changed])
                )
            if self.__deleted:
                data.append((self.MSG_DELETE, self.__deleted))

            self.__created = []
            self.__changed = []
            self.__deleted = []

        return [serialize(d) for d in data]

    def globalObjectId(self, objId):
        return (self.id << 20) + objId

    def applyChanges(self, managerId, data):
        for d in data:
            try:
                msg, payload = unserialize(self, d)

                if msg == self.MSG_CREATE:
                    for obj_id, creation in payload:
                        objectClass, args, kwargs = creation
                        self.__creationData[obj_id] = creation
                        self.objects[obj_id] = objectClass(
                            id=obj_id, manager=self, *args, **kwargs
                        )

                elif msg == self.MSG_CHANGE:
                    for obj_id, changes in payload:
                        if changes:
                            self.objects[obj_id].applyChanges(changes)

                elif msg == self.MSG_DELETE:
                    obj_id = payload
                    del self.__creationData[obj_id]
                    del self.objects[obj_id]

            except Exception as e:
                Log.error(
                    "Exception %s while processing incoming changes from manager %s."
                    % (str(e), managerId)
                )
                raise


def enableGlobalManager():
    global manager
    manager = Manager()


class Message:
    classes = {}

    def __init__(self):
        if self.__class__ not in self.classes:
            self.classes[self.__class__] = len(self.classes)
        self.id = self.classes[self.__class__]


class ObjectCreated(Message):
    pass


class ObjectDeleted(Message):
    def __init__(self, obj):
        self.object = obj


class Object(object):
    def __init__(self, id=None, manager=None, *args, **kwargs):
        self.__modified = {}
        self.__messages = []
        self.__messageMap = {}
        self.__shared = []

        if manager is None:
            manager = globals().get("manager")
        if manager is None:
            raise ValueError(
                "Object requires a Manager (pass manager=... or call enableGlobalManager())."
            )

        self.manager = manager
        self.id = id or manager.createObject(self, *args, **kwargs)

    def share(self, *attr):
        for a in attr:
            a = str(a)
            self.__shared.append(a)
            self.__modified[a] = self.__dict__[a]

    def __setattr__(self, attr, value):
        if attr in getattr(self, "_Object__shared", {}):
            self.__modified[attr] = value
            self.manager.setChanged(self)
        object.__setattr__(self, attr, value)

    def delete(self):
        self.emit(ObjectDeleted(self))
        self.manager.deleteObject(self)

    def getChanges(self, everything=False):
        if self.__messages:
            self.__modified["_Object__messages"] = self.__messages

        self.__processMessages()

        if everything:
            return {k: getattr(self, k) for k in self.__shared}

        if self.__modified:
            data, self.__modified = self.__modified, {}
            return data

    def applyChanges(self, data):
        self.__dict__.update(data)
        self.__processMessages()

    def emit(self, message):
        self.__messages.append(message)

    def connect(self, messageClass, callback):
        self.__messageMap.setdefault(messageClass, []).append(callback)

    def disconnect(self, messageClass, callback):
        if messageClass in self.__messageMap:
            self.__messageMap[messageClass].remove(callback)

    def __processMessages(self):
        for m in self.__messages:
            if m.__class__ in self.__messageMap:
                for c in self.__messageMap[m.__class__]:
                    c(m)
        self.__messages = []
