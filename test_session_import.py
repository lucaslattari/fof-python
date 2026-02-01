# test_session_import.py
import sys

sys.path.insert(0, "src")

import Session


class Ping(Session.Message):
    def __init__(self, txt="hi", n=1):
        super().__init__(txt=txt, n=n)


class Handler(Session.MessageHandler):
    def __init__(self):
        self.seen = []

    def handlePing(self, sender, txt=None, n=None, **kwargs):
        self.seen.append((sender, txt, n))
        return "ok"


def main():
    # 1) Import ok (se chegou aqui, já passou)
    print("Session import ok")

    # 2) Phrasebook roundtrip (ensina classe + decodifica mensagem)
    pb = Session.Phrasebook()
    packets = pb.encode(Ping("hello", 42))
    assert len(packets) == 2, "Deveria enviar 2 pacotes (definição + mensagem)"
    assert pb.decode(packets[0]) is None, "Pacote de definição não retorna Message"
    msg = pb.decode(packets[1])
    assert isinstance(msg, Ping), "Decodificado deveria ser Ping"
    assert msg.txt == "hello" and msg.n == 42
    print("Phrasebook OK")

    # 3) Broker + handler roteando por __name__
    broker = Session.MessageBroker()
    h = Handler()
    broker.addMessageHandler(h)
    broker.signalMessage(7, msg)
    assert h.seen == [(7, "hello", 42)]
    print("Broker/Handler OK")

    print("OK: minimal Session test finished.")


if __name__ == "__main__":
    main()
