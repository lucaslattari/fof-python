# src/MidiSanityTest.py
from __future__ import annotations

import os
import sys
import traceback


def find_any_notes_mid(repo_root: str) -> str | None:
    # Procura por qualquer notes.mid no repositório
    for root, _dirs, files in os.walk(repo_root):
        if "notes.mid" in files:
            return os.path.join(root, "notes.mid")
    return None


def main() -> int:
    print("=== MIDI SANITY TEST ===")
    print("Python:", sys.version)
    print("Executable:", sys.executable)
    print("CWD:", os.getcwd())
    print("sys.path[0]:", sys.path[0])
    print(
        "Repo root guess:",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    )
    print()

    # 1) mido: existe?
    try:
        import mido  # type: ignore

        print("[OK] mido importado:", getattr(mido, "__version__", "<sem __version__>"))
        print("     mido file:", getattr(mido, "__file__", "<sem __file__>"))
    except Exception as e:
        print("[FAIL] Não consegui importar mido.")
        print("       Rode: pip show mido  (no mesmo venv)")
        print("Erro:", repr(e))
        print(traceback.format_exc())
        return 2

    print()

    # 2) midi: qual módulo está vindo?
    try:
        import midi  # type: ignore

        print("[OK] midi importado.")
        print("     midi module:", midi)
        print("     midi file:", getattr(midi, "__file__", "<built-in/sem arquivo?>"))
    except Exception as e:
        print("[FAIL] Não consegui importar midi.")
        print("       Se você criou src/midi.py, ele não está no lugar certo,")
        print("       ou tem erro de import/sintaxe lá dentro.")
        print("Erro:", repr(e))
        print(traceback.format_exc())
        return 3

    print()

    # 3) API mínima existe?
    missing = []
    for attr in ("MidiInFile", "MidiOutStream", "MidiOutFile"):
        if not hasattr(midi, attr):
            missing.append(attr)

    if missing:
        print("[FAIL] O módulo 'midi' importado não tem a API esperada:", missing)
        print(
            "       Isso geralmente significa que você NÃO está importando o seu src/midi.py,"
        )
        print("       e sim algum outro pacote 'midi' (ou nada compatível).")
        return 4

    print("[OK] midi tem MidiInFile/MidiOutStream/MidiOutFile")

    print()

    # 4) Tenta ler um notes.mid real do repo
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    notes_path = find_any_notes_mid(repo_root)
    if not notes_path:
        print("[WARN] Não achei nenhum notes.mid no repositório para testar leitura.")
        print("       (sem isso, só validamos import/API)")
        return 0

    print("[INFO] Testando leitura de:", notes_path)

    # Importa os leitores do Song.py (sem inicializar engine)
    try:
        # O MidiInfoReader existe no Song.py e é ideal para teste
        from Song import MidiInfoReader  # type: ignore
    except Exception as e:
        print(
            "[FAIL] Não consegui importar Song.MidiInfoReader (import de Song.py falhou)."
        )
        print("Erro:", repr(e))
        print(traceback.format_exc())
        return 5

    try:
        info = MidiInfoReader()
        midi_in = midi.MidiInFile(info, notes_path)
        midi_in.read()
        diffs = getattr(info, "difficulties", [])
        print("[OK] Leitura do notes.mid funcionou.")
        print(
            "     difficulties detectadas:", [getattr(d, "text", str(d)) for d in diffs]
        )
        return 0
    except Exception as e:
        print("[FAIL] Leitura do notes.mid falhou.")
        print("Erro:", repr(e))
        print(traceback.format_exc())
        return 6


if __name__ == "__main__":
    raise SystemExit(main())
