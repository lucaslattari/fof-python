import sys


def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/sanity_collada.py caminho/arquivo.dae")
        return 2

    path = sys.argv[1]

    # 1) Importa seu loader principal (ajuste o import pro seu projeto)
    # Exemplo: from your_collada_module import DaeDocument
    from Collada import DaeDocument  # <-- TROQUE AQUI

    # 2) Carrega
    doc = DaeDocument()
    doc.Load(path)  # ou doc.LoadFromFile(path), conforme sua API
    print("[OK] Load:", path)

    # 3) Tenta salvar de volta (pra testar SaveToXml em cadeia)
    out = path.replace(".dae", "_roundtrip.dae")
    doc.Save(out)  # ou doc.SaveToFile(out)
    print("[OK] Save:", out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
