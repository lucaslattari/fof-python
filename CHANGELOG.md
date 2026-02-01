# 📜 Histórico consolidado do port Frets on Fire → Python 3 (atualizado)

**Ambiente atual validado:**

* **Python 3.11.9**
* Windows
* **pygame 2.6.1**
* PyOpenGL + Pillow + numpy

---

## 🧠 Núcleo da aplicação (boot, config, paths, log)

### 1️⃣ `src/FretsOnFire.py`

**Status:** Portado para Python 3 ✅
**Testado:** execução direta

Correções:

* `print` → função
* reinício do processo via `sys.executable`
* bloco legado de `py2exe / eggs` preservado e isolado
* imports absolutos mantidos propositalmente
* compatível com `python FretsOnFire.py`

---

### 2️⃣ `src/Log.py`

**Status:** Portado para Python 3 ✅
**Testado:** `test_minimal.py`

Correções:

* removido `print >> file`
* removido `unicode`
* corrigido import circular com `Resource`
* abertura lazy do arquivo de log
* encoding `iso-8859-1` preservado com `errors="ignore"`

---

### 3️⃣ `src/Config.py`

**Status:** Portado para Python 3 ✅
**Testado:** `test_minimal.py` + inicialização real via `GameEngineSanityTest.py`

Correções:

* `ConfigParser` → `configparser`
* encoding explícito ao ler/escrever `.ini`
* remoção de `unicode`
* preservada lógica original de defaults, casting e tipos
* **ajuste importante de fluxo**: garantir config global default antes de acessos antecipados (destravou crash no `SvgContext`)

---

### 4️⃣ `src/Resource.py`

**Status:** Portado para Python 3 ✅
**Testado:** `test_minimal.py` (indireto)

Correções:

* `Queue` → `queue`
* `raise exc_type, exc, tb` → `raise exc.with_traceback(tb)`
* threading preservado
* lógica de diretório gravável intacta
* compatível multi-plataforma

---

## 🌍 Idioma e internacionalização

### 5️⃣ `src/Language.py`

**Status:** Portado para Python 3 ✅
**Testado:** `test_language_import.py`

Correções:

* `except Exception, x` → `except Exception as x`
* removido `.decode("utf-8")`
* leitura de `.mo` em modo binário
* fallback `_()` preservado

---

## 🧱 Modelo de objetos e sincronização

### 6️⃣ `src/Object.py`

**Status:** Portado para Python 3 ✅
**Testado:** `test_object.py`

Correções:

* `StringIO` → `io.BytesIO`
* pickle mantido em `protocol=2`
* compatibilidade bytes/str
* correção de efeitos colaterais em list comprehensions
* sistema de `Manager` preservado

---

## 🌐 Sessões, mensagens e rede lógica

### 7️⃣ `src/Session.py`

**Status:** Portado para Python 3 ✅
**Testado:** `test_session_import.py`

Correções críticas:

* `StringIO` → `io.BytesIO`
* correção de `Phrasebook.encode` (pickle-safe)
* ajuste de handlers de mensagens
* resolução de imports circulares
* comunicação binária estável

---

## 🎮 Engine principal

### 8️⃣ `src/Engine.py`

**Status:** Importa corretamente em Python 3 ✅
**Testado:** após correções em `Session.py`

Observação:

* ainda não refatorado integralmente
* **não quebra no import**, marco estrutural atingido

---

### 9️⃣ `src/GameEngine.py`

**Status:** Funcional em Python 3 ✅
**Testado:** import + execução real + sanity test gráfico

Marco importante:

* inicialização completa de áudio, vídeo, SVG, input, tasks
* engine entra em loop real (`loading` → `main`)
* janela OpenGL funcional
* **loop estável sem exits espúrios após correções gráficas**
* **melhoria de encerramento no Windows (ALT+F4 / X da janela):**

  * root-cause: pygame 2 pode emitir `WINDOWCLOSE` / `WINDOWEVENT_CLOSE` em vez de `QUIT`
  * fechamento passou a funcionar após tratamento desses eventos no `Input` (ver seção de Input)

---

## 🎛️ Mods

### 🆕 `src/Mod.py`

**Status:** Portado para Python 3.11 ✅
**Testado:** inicialização real via `GameEngine`

Correções:

* sintaxe de exceções Py3
* lógica original preservada
* fallback seguro quando pasta `mods/` não existe

---

## 🎥 Vídeo / OpenGL

### 🔟 `src/Video.py`

**Status:** Portado para Python 3 ✅
**Testado:** via `GameEngine`

Correções:

* sintaxe Py3
* fullscreen / multisample preservados

---

## 🖼️ Texturas, FBO, Atlas

### 1️⃣1️⃣ `src/Texture.py`

**Status:** Portado para Python 3 ✅
**Testado:** `test_texture_smoke.py` + execução real no menu

Correções extensas:

* Pillow moderno
* dados `bytes` explícitos para OpenGL
* fila de cleanup segura (`cleanupQueue`)
* FBO funcional (real ou emulado)
* validação defensiva de tamanhos de textura / framebuffer
* prevenção de overflows silenciosos (int cast + limites conservadores)
* `TextureAtlas` funcional e integrado ao sistema de fontes

📌 **Resultado prático:**
Texturas, SVGs, fontes e render targets funcionando corretamente no menu real.

⚠️ **Observação nova (durante crash/abort manual):**

* Log registrou: `Texture atlas (2048, 2048) full after 60 surfaces.`
* Isso confirma que o atlas encheu durante fluxo de erro/MessageScreen (não necessariamente bug ainda, mas é dado útil para futuro ajuste de estratégia de atlas/evicção).

---

## 🔤 Fontes

### 1️⃣2️⃣ `src/Font.py`

**Status:** **Totalmente funcional** ✅
**Testado:** execução real no menu principal + sanity tests

Correções críticas (fase final do port):

* inicialização correta de `self.atlases`
* limitação sensata do tamanho de `TextureAtlas` (evita `GL_MAX_TEXTURE_SIZE`)
* correção do fluxo de fallback ao estourar atlas
* correção do bug de `AttributeError: atlases`
* **isolamento completo de estado OpenGL no `Font.render`**:

  * uso de `glPushAttrib / glPopAttrib`
  * restauração de blending, cor, textura e arrays
* eliminação de vazamento de estado gráfico para o resto da cena

📌 **Marco visual:**
Menu renderiza **idêntico ao Frets on Fire original**, sem artefatos ou “lavagem” de cores.

---

## 🧩 SVG

### 🆕 `src/Svg.py`

**Status:** Portado para Python 3.11 ✅
**Testado:** carregamento real de SVG via `Data`

Correções relevantes:

* remoção de `file` (Py2)
* substituição de `__cmp__`
* correção de caches de stroke/style
* leitura robusta de SVG (`utf-8`, fallback)
* **SVGs reais renderizando corretamente no menu**

---

## 🧩 COLLADA (.dae) + Mesh

### 🆕 Parser COLLADA

**Status:** Portado para Python 3 ✅
**Testado:** sanity tests próprios (todos passando)

Correções:

* compatibilidade str/bytes
* exceções Py3
* testes confirmam integridade

---

### 🆕 `src/Mesh.py`

**Status:** Portado para Python 3 ✅
**Testado:** **MeshSanityTest.py** ✅ + execução real no jogo (SongChooser/ItemChooser)

Correções:

* correção do bug clássico do Py3: `range(len(array) / stride)` → divisão inteira (`//`) / conversão para `int`
* `_unflatten` compatível com Python 3 (sem floats em `range`)
* preservada a lógica de display lists e traversal de nodes/visualScenes
* pipeline COLLADA usado pelo SongChooser/itens do menu agora renderiza sem crash

📌 **Marco:**
O jogo passou de “crash ao apertar Play Game” para **chegar até carregar a GuitarScene**.

---

## 🎭 Stage (cenário/efeitos da GuitarScene)

### 🆕 `src/Stage.py`

**Status:** Portado para Python 3 ✅
**Testado:** execução real ao iniciar cena de guitarra (carregando múltiplos `Stage.None`)

Correções:

* `ConfigParser` (Py2) → `configparser` (Py3)
* leitura de `.ini` com `encoding="iso-8859-1"` (compatibilidade com configs antigas)
* correção de divisão inteira:

  * `beat = quarterBeat / 4` (Py2) → `beat = quarterBeat // 4` (Py3)
* parsing defensivo de parâmetros (blending e defaults), preservando comportamento original

📌 **Marco:**
A cena de jogo **inicia o carregamento** e passa por toda a fase de assets da guitarra (neck, strings, notes, meshes, etc.).

---

## 🎮 Input / Eventos / Pause & Quit

### 🆕 `src/Input.py`

**Status:** Portado e estabilizado para pygame 2 ✅
**Testado:** `EscapeSanityProbe.py` + fluxo real até GuitarScene

Correções e mudanças:

* migração segura de APIs do pygame 2 (sem depender de `event.unicode` existir sempre)
* **joystick input preservado** (buttons/axes/hats continuam “mascarando” eventos de teclado via IDs codificados)
* correção de compatibilidade Py3:

  * `reversed()` legado removível (Py3 já possui), mantido fallback seguro
  * correção de divisão inteira em `decodeJoystickHat` (`v // 3`)
* **encerramento correto no Windows via ALT+F4 / X da janela**:

  * tratamento adicional de `WINDOWCLOSE` e `WINDOWEVENT_CLOSE` para disparar `SystemEventListener.quit`
  * mantém compatibilidade com `pygame.QUIT` clássico
* mantém o design original: `Input` como “broker” broadcast para listeners (mouse/key/system)

📌 **Resultado prático:**
ALT+F4 fecha corretamente (não cai mais no fluxo “Connection lost → MessageScreen” por falta de quit).

---

## 🎸 Gameplay / Pause Menu / ESC (GuitarScene)

### 🆕 `src/GuitarScene.py`

**Status:** Gameplay entrou em loop e ESC estabilizado ✅
**Testado:** `EscapeSanityProbe.py` (pressionando ESC 1x) + cenas de jogo reais

Correções e mudanças:

* **ESC/CANCEL não causa mais múltiplos triggers** (pygame moderno pode emitir repetições/efeitos colaterais):

  * implementado **debounce** de cancel (`_lastCancelMs`, `_cancelDebounceMs`)
  * evita empilhar o pause menu múltiplas vezes
* **pause/resume tornados seguros**:

  * `pauseGame()` só pausa se a música estiver realmente tocando (`song.isPlaying()`)
  * `resumeGame()` re-aplica settings e faz `song.unpause()` quando aplicável
* **correção de fluxo “ESC → ir pro Results” indevido**:

  * ajuste no `run()` para não interpretar “pausa/stop temporário” como “fim de música”
  * `goToResults()` só quando apropriado (com base em `songStarted`/estado correto)

📌 **Resultado prático:**
Pressionar ESC durante música abre pause menu sem derrubar a cena nem forçar resultados.

⚠️ **Observação atual (ainda em ajuste fino):**

* durante countdown (5…4…3…2…1), ESC inicialmente não pausava — comportamento sendo refinado para pausar também nessa fase.

---

## ✏️ Editor de músicas

### 🆕 `src/Editor.py`

**Status:** Portado para Python 3.11 ✅
**Testado:** `EditorSanityTest.py` (passando)

Correções e ajustes:

* `print` → função
* remoção de `unicode`
* correção de imports circulares com `MainMenu`
* restauração de métodos perdidos:

  * `setCassetteColor`
  * `setCassetteLabel`
* integração correta com `Song`, `Dialogs`, `Theme`
* editor instancia, entra em loop e processa eventos

📌 **Marco:** Editor funcional em Python 3.

---

## 📋 Menus e configurações

### 🆕 `src/MainMenu.py`

**Status:** Portado para Python 3 ✅
**Testado:** `MainMenuSanityTest.py` (execução real)

Correções:

* sintaxe de exceções Py3
* tratamento de erros via decorator `catchErrors`
* integração com `SettingsMenu`, `Editor`, `Lobby`
* **renderização final idêntica ao original após correções de fonte/OpenGL**

---

### 🆕 `src/Settings.py`

**Status:** Portado para Python 3 ✅
**Testado:** via `MainMenuSanityTest.py`

Correções:

* `dict.values()` → `list(...)` / `sorted(...)`
* remoção de `.sort()` em `dict_values`
* menus de vídeo, áudio, jogo e mods funcionando
* aplicação de settings preservada

---

## 🧪 Testes / validações

Executados com sucesso:

* `test_minimal.py`
* `test_language_import.py`
* `test_object.py`
* `test_session_import.py`
* `test_texture_smoke.py`
* **Collada sanity tests** ✅
* **MeshSanityTest.py** ✅
* **GameEngineSanityTest.py** ✅
* **EditorSanityTest.py** ✅
* **MainMenuSanityTest.py** ✅
* **FretsOnFireSanityTest.py** ✅ (loop estável, sem exits prematuros)
* **EscapeSanityProbe.py** ✅ (valida ESC/cancel e quit/ALT+F4 no pygame 2)

---

## 🟡 Estado atual do projeto (ponto exato)

Neste ponto, o Frets on Fire em Python 3 possui:

* engine funcional com loop gráfico estável
* menus navegáveis e visualmente corretos
* settings aplicáveis
* editor operacional
* SVGs renderizando
* fontes corretas (atlas + blending + estado isolado)
* COLLADA/Mesh funcional (cassette/library/etc.)
* áudio e input ativos
* fluxo Play Game avançou até a GuitarScene
* **ESC/pause estável durante gameplay**
* **ALT+F4 fecha corretamente no Windows (pygame 2)**

🚧 **Bloqueio atual do gameplay:**

* `RuntimeError: midi module missing; cannot load notes.mid` ao carregar a música (módulo MIDI ausente)
* após abort manual (`Ctrl+C`), apareceu `ctypes.ArgumentError ... KeyboardInterrupt` dentro de `glTexCoordPointer` — isso é efeito colateral do interromper o processo no meio de uma chamada OpenGL (não é “bug novo” de lógica do jogo).