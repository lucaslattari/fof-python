# Frets on Fire – Python 3 Port

**Languages:**  
[English](#english) | [Português](#português)

---

## English

### Overview

This repository is a **fork of the original Frets on Fire legacy codebase**, originally written in Python 2, with the goal of **porting and keeping the game functional on modern Python versions (Python 3.11+)**.

The main goals of this fork are:
- Python 3 compatibility
- bug fixes for legacy code
- easier modern builds (e.g. PyInstaller on Windows)

This is **not a rewrite**, but an **incremental and conservative port**.

---

### Status

✅ Fully playable on Python 3  
✅ Menus, song selection and gameplay working  
⚠️ Legacy code preserved as much as possible  

---

### Requirements (running from source)

- Python 3.11+
- pip
- pygame 2.x

Install basic dependencies with:

```bash
pip install pygame typing_extensions
````

> Note: some legacy dependencies are optional and handled with fallbacks.

---

### Running from source

```bash
python src/FretsOnFire.py
```

---

### Project structure

```
src/        → game source code
data/       → game assets (themes, translations, songs, etc.)
doc/        → legacy documentation
```

---

### Songs / Music

This repository **does not include licensed or commercial songs**.

To play the game, you must add your own songs to:

```
data/songs/
```

Each song must be in its own folder containing at least:

* `song.ogg`
* `guitar.ogg`
* `song.ini`
* `notes.mid`

---

### Windows build (PyInstaller)

This fork has been tested with **PyInstaller (onedir mode)**.

High-level steps:

1. Create a virtual environment
2. Install dependencies
3. Build the executable with PyInstaller
4. Distribute the generated `dist/FretsOnFire/` folder

> Build artifacts (`build/`, `dist/`, `.spec`) are not tracked in the repository.

---

### Legal notice

Frets on Fire is free software released under the GPL license.
This fork **does not redistribute licensed or commercial music**.

Users are responsible for adding only content they have the right to use.

---

### Credits

* Original code: Frets on Fire (Sami Kyöstilä and contributors)
* Python 3 port and maintenance: this fork

---

### Contributing

Contributions are welcome, especially:

* Python 3 compatibility fixes
* legacy code cleanup
* build and portability improvements

---

## Português

### Visão geral

Este repositório é um **fork do código legado original do Frets on Fire**, originalmente escrito em Python 2, com o objetivo de **portar e manter o jogo funcional em versões modernas do Python (Python 3.11+)**.

Os principais objetivos deste fork são:

* compatibilidade com Python 3
* correções de bugs do código legado
* facilitar builds modernos (ex.: PyInstaller no Windows)

Este **não é um rewrite**, mas sim um **port incremental e conservador**.

---

### Status

✅ Jogo totalmente funcional em Python 3
✅ Menus, seleção de músicas e gameplay funcionando
⚠️ Código legado preservado ao máximo

---

### Requisitos (executando pelo código-fonte)

* Python 3.11+
* pip
* pygame 2.x

Instale as dependências básicas com:

```bash
pip install pygame typing_extensions
```

> Observação: algumas dependências legadas são opcionais e tratadas com fallback no código.

---

### Executando pelo código-fonte

```bash
python src/FretsOnFire.py
```

---

### Estrutura do projeto

```
src/        → código-fonte do jogo
data/       → assets do jogo (temas, traduções, músicas, etc.)
doc/        → documentação legado
```

---

### Músicas

Este repositório **não inclui músicas licenciadas ou comerciais**.

Para jogar, você deve adicionar suas próprias músicas em:

```
data/songs/
```

Cada música deve estar em uma pasta contendo, no mínimo:

* `song.ogg`
* `guitar.ogg`
* `song.ini`
* `notes.mid`

---

### Build para Windows (PyInstaller)

Este fork foi testado com **PyInstaller em modo onedir**.

Resumo do processo:

1. Criar um ambiente virtual
2. Instalar as dependências
3. Gerar o executável com PyInstaller
4. Distribuir a pasta `dist/FretsOnFire/`

> Artefatos de build (`build/`, `dist/`, `.spec`) não são versionados.

---

### Aviso legal

Frets on Fire é software livre, distribuído sob a licença GPL.
Este fork **não redistribui músicas comerciais ou licenciadas**.

Os usuários são responsáveis por adicionar apenas conteúdo que tenham direito de uso.

---

### Créditos

* Código original: Frets on Fire (Sami Kyöstilä e colaboradores)
* Port e manutenção em Python 3: este fork

---

### Contribuições

Contribuições são bem-vindas, especialmente:

* correções de compatibilidade com Python 3
* limpeza de código legado
* melhorias de build e portabilidade

---