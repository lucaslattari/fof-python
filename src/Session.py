#####################################################################
# -*- coding: iso-8859-1 -*-                                        #
#                                                                   #
# Frets on Fire                                                     #
# Copyright (C) 2006 Sami Ky�stil�                                  #
#                                                                   #
#####################################################################

import pickle
import io

import Network

# import Engine  # mantido por compatibilidade (pode ser usado indiretamente)
import Log

# import World
import Task


class Message:
    def __init__(self, **args):
        for key, value in args.items():
            setattr(self, key, value)

    def __repr__(self):
        parts = " ".join([f"{k}='{v}'" for k, v in self.__dict__.items()])
        return f"<Message {self.__class__} {parts}>"


class MessageBroker:
    def __init__(self):
        self.messageHandlers = []

    def addMessageHandler(self, handler):
        if handler not in self.messageHandlers:
            self.messageHandlers.append(handler)

    def removeMessageHandler(self, handler):
        if handler in self.messageHandlers:
            self.messageHandlers.remove(handler)

    def signalMessage(self, sender, message):
        # Em Py2 tinha um reversed() custom; em Py3 já existe e é seguro.
        for handler in reversed(self.messageHandlers):
            try:
                handler.handleMessage(sender, message)
            except Exception as e:
                import traceback

                traceback.print_exc()

    def signalSessionOpened(self, session):
        for handler in self.messageHandlers:
            handler.handleSessionOpened(session)

    def signalSessionClosed(self, session):
        for handler in self.messageHandlers:
            handler.handleSessionClosed(session)


class MessageHandler:
    def handleMessage(self, sender, message):
        # Em Py2 faziam "handle" + str(message.__class__).split(".")[-1]
        # Isso quebra no Py3 por causa do "<class '...'>".
        # O equivalente certo é __name__.
        method_name = "handle" + message.__class__.__name__
        try:
            f = getattr(self, method_name)
        except AttributeError:
            return None
        return f(sender, **message.__dict__)

    def handleSessionOpened(self, session):
        pass

    def handleSessionClosed(self, session):
        pass


class Phrasebook:
    def __init__(self):
        self.receivedClasses = {}
        self.sentClasses = {}

    @staticmethod
    def serialize(data) -> bytes:
        bio = io.BytesIO()
        pickle.Pickler(bio, protocol=2).dump(data)
        return bio.getvalue()

    @staticmethod
    def unserialize(data):
        # garantir bytes (pickle em Py3 quer bytes)
        if isinstance(data, str):
            data = data.encode("latin-1", "strict")
        return pickle.loads(data)

    def decode(self, packet):
        data = self.unserialize(packet)
        msg_id = data[0]

        if msg_id < 0:
            # mensagem “definição” (ensina classe + campos)
            self.receivedClasses[-msg_id] = data[1:]
            Log.debug(
                "Learned about %s, %d phrases now known."
                % (data[1], len(self.receivedClasses))
            )
            return None

        if msg_id in self.receivedClasses:
            cls, keys = self.receivedClasses[msg_id]
            message = cls()
            if len(data) > 1:
                message.__dict__.update(dict(zip(keys, data[1:])))
            return message

        Log.warn("Message with unknown class received: %d" % msg_id)
        return None

    def encode(self, message):
        packets = []

        if message.__class__ not in self.sentClasses:
            msg_id = len(self.sentClasses) + 1
            # IMPORTANT: no Py3, message.__dict__.keys() é dict_keys (não picklável como antes).
            keys = list(message.__dict__.keys())
            definition = [message.__class__, keys]
            self.sentClasses[message.__class__] = [msg_id] + definition
            packets.append(self.serialize([-msg_id] + definition))
            Log.debug("%d phrases taught." % len(self.sentClasses))
        else:
            msg_id = self.sentClasses[message.__class__][0]

        keys = self.sentClasses[message.__class__][2]
        data = [msg_id] + [getattr(message, key) for key in keys]
        packets.append(self.serialize(data))
        return packets


class BaseSession(Network.Connection, Task.Task, MessageHandler):
    def __init__(self, engine, broker, sock=None):
        Network.Connection.__init__(self, sock)
        self.engine = engine
        self.broker = broker
        self.phrasebook = Phrasebook()

    def __str__(self):
        # addr vem do asyncore/dispatcher (depende da Connection original)
        return "<Session #%s at %s>" % (self.id, getattr(self, "addr", None))

    def isPrimary(self):
        return self.id == 1

    def run(self, ticks):
        pass

    def stopped(self):
        self.close()

    def disconnect(self):
        return self.engine.disconnect(self)

    def sendMessage(self, message):
        for packet in self.phrasebook.encode(message):
            self.sendPacket(packet)

    def handleMessage(self, sender, message):
        self.broker.signalMessage(sender, message)

    def handleRegistration(self):
        Log.debug("Connected as session #%d." % self.id)

    def isConnected(self):
        return self.id is not None


class ServerSession(BaseSession):
    def __init__(self, engine, sock):
        super().__init__(engine=engine, broker=engine.server.broker, sock=sock)
        self.server = engine.server
        self.world = self.server.world

    def handlePacket(self, packet):
        message = self.phrasebook.decode(packet)
        if message:
            self.handleMessage(self.id, message)

    def handleRegistration(self):
        self.broker.signalSessionOpened(self)

    def handleClose(self):
        self.broker.signalSessionClosed(self)
        BaseSession.handleClose(self)


class ConnectionLost(Message):
    pass


class ClientSession(BaseSession):
    def __init__(self, engine):
        super().__init__(engine=engine, broker=MessageBroker())

        # Import lazy para evitar ciclo: Engine -> World -> Session
        import World

        self.world = World.WorldClient(engine, session=self)
        self.broker.addMessageHandler(self.world)
        self.closed = False

    def handleClose(self):
        if not self.closed:
            self.closed = True
            self.broker.signalMessage(0, ConnectionLost())

    def handlePacket(self, packet):
        message = self.phrasebook.decode(packet)
        if message:
            self.handleMessage(0, message)

    def run(self, ticks):
        Network.communicate()
