import sys

sys.path.insert(0, "src")

import Object

Object.enableGlobalManager()

m = Object.manager
o = Object.Object(manager=m)
o.foo = 123
o.share("foo")
o.foo = 999

changes = m.getChanges()
assert isinstance(changes, list)
print("Object smoke test OK. Changes packets:", len(changes))
