# test_language_import.py
import sys

sys.path.insert(0, "src")

import Language

print("Language import ok")
print("Available languages:", Language.getAvailableLanguages()[:10])
print("Translator result:", Language._("Language"))
