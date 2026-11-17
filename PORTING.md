# 2FastAPI PORTING / 再開メモ

## 日本語
**状態**: v0.2.0+。Flask(フック・render_template・request.files・Flask-RESTful/MethodView)とDjango(View継承クラス)をFastAPIへ変換。scan/auto/convertで複数プロジェクトを自動検出し、変換先を英日で質問(無ければ作成確認)。差分テスト36件、CIは3OS成功。
**未了**: PyPI公開(DRF ViewSet/ModelViewSet・Flask JWT/marshmallow は v0.5.2、`upgrade` は v0.5.3 で対応済み)、Python 3.14ネイティブのlibcst(WindowsのPythonにlibcst無し→テストはWSL)。
**再開用メッセージ**: 「`F:\runo\PORTING.md` 末尾の「2026-11-15 別アカウントでの再開用メモ」と、`F:$1\PORTING.md` を読んで、未了の続きを確認なしで開発・TEST・DEBUG・commit・pushして。チャットは日本語のみ。」
**テスト**: WSL: powershell -c "wsl -d Ubuntu -- bash /mnt/f/2FastAPI/run-tests.sh" (setup-wsl.sh で環境作成 / creates the env; TAILN=100 で出力を増やす / more output)

## English
**Status**: v0.2.0+. Converts Flask (hooks, render_template, request.files, Flask-RESTful/MethodView) and Django (View subclasses) to FastAPI. scan/auto/convert detect several projects and ask in English and Japanese where to put the result (creating folders). 36 differential tests, CI green on 3 OSes.
**Open**: PyPI publication (DRF ViewSet/ModelViewSet and Flask JWT/marshmallow done in v0.5.2, `upgrade` in v0.5.3), libcst on native Windows Python 3.14 (tests run in WSL).
**Resume message**: "Read the 2026-11-15 section at the end of `F:\runo\PORTING.md` and `F:$1\PORTING.md`, then continue the open items without asking (develop, test, debug, commit, push). Chat in Japanese only."
**Tests**: WSL: powershell -c "wsl -d Ubuntu -- bash /mnt/f/2FastAPI/run-tests.sh" (setup-wsl.sh で環境作成 / creates the env; TAILN=100 で出力を増やす / more output)

## API 方針: REST 全廃・gRPC / Connect へ (2026-11-04)

### 日本語
- **REST は全廃する。新しい API は REST で作らない。** ブラウザや `curl` から呼ぶ API は **Connect の単純呼び出し**(`POST /<パッケージ>.<Service>/<Method>`、`content-type: application/json`、本文は JSON)、サービス間は **gRPC / gRPC-web**(RPoem の管理API `open_runo.admin.v1.Admin` と同じ流儀)。ストリーミングは、必要になってから。
- **既存の REST は、触るときに順に移す。** 移したら旧 REST の経路は消す。移行が終わるまで残るが、**新規には追加しない**。
- **JSON は RS-JSON に統一**する(読み込みは `from_str_secure` / `parse_secure` でサイズ・深さ・重複キーの上限つき、書き出しは `rust_json::fast`)。ブラウザの WASM に `prost` は入れない(サイズが増えるため)。
- **例外(自分たちの API ではなく、相手の規格が決めているもの)**: ACME、OAuth/OIDC のコールバック、第三者(GitHub など)からの Webhook、ヘルスチェック、静的ファイル配信、OTLP など。これらは規格どおりの HTTP を受ける。
- 参考実装: `RPoem`(`open_runo.admin.v1.Admin`)、`open-easy-web`(`server/src/connect.rs`、`proto/open_easy_web/admin/v1/admin.proto`)。
- ※ このリポジトリのコードが既に方針どおりかどうかは、各リポジトリの現状による。この節は方針の記録であり、コードの変更を意味しない。

### English
- **REST is being abolished. New APIs are not built as REST.** APIs called from browsers or `curl` use **Connect unary calls** (`POST /<package>.<Service>/<Method>`, `content-type: application/json`, JSON body); service-to-service calls use **gRPC / gRPC-web** (the same style as RPoem's admin API `open_runo.admin.v1.Admin`). Streaming only when it is actually needed.
- **Existing REST endpoints are migrated one by one, when they are touched.** The old REST route is removed once migrated. Until migration is finished they remain, but **no new ones are added**.
- **JSON is unified on RS-JSON**: reading with `from_str_secure` / `parse_secure` (size, depth and duplicate-key limits), writing with `rust_json::fast`. `prost` is not put into browser WASM (it would grow the binary).
- **Exceptions (shapes dictated by someone else's standard, not our own API)**: ACME, OAuth/OIDC callbacks, webhooks from third parties (e.g. GitHub), health checks, static file serving, OTLP, and so on. These accept plain HTTP as the standard requires.
- Reference implementations: `RPoem` (`open_runo.admin.v1.Admin`) and `open-easy-web` (`server/src/connect.rs`, `proto/open_easy_web/admin/v1/admin.proto`).
- Note: whether the code in a given repository already follows this policy depends on that repository. This section records the policy; it does not mean the code has been changed.

### Deutsch (KI-Übersetzung, redaktionell überarbeitet; noch nicht von Muttersprachlern geprüft)
- **REST wird vollständig abgeschafft; neue APIs entstehen nicht mehr als REST.** APIs, die aus dem Browser oder per `curl` aufgerufen werden, verwenden **unäre Connect-Aufrufe** (`POST /<Paket>.<Service>/<Methode>`, `content-type: application/json`, JSON-Body). Zwischen Diensten kommen **gRPC bzw. gRPC-web** zum Einsatz, im selben Stil wie die Admin-API von RPoem (`open_runo.admin.v1.Admin`). Streaming wird erst ergänzt, wenn es tatsächlich gebraucht wird.
- **Bestehende REST-Endpunkte werden schrittweise umgestellt, und zwar immer dann, wenn man ohnehin an ihnen arbeitet.** Sobald ein Endpunkt umgestellt ist, wird die alte REST-Route entfernt. Bis zum Abschluss der Migration bleiben die übrigen bestehen, es werden aber **keine neuen mehr hinzugefügt**.
- **JSON wird einheitlich über RS-JSON verarbeitet**: Gelesen wird mit `from_str_secure` bzw. `parse_secure` (mit Obergrenzen für Größe, Verschachtelungstiefe und doppelte Schlüssel), geschrieben mit `rust_json::fast`. `prost` wird nicht in das Browser-WASM aufgenommen, da es die Datei vergrößern würde.
- **Ausnahmen (Schnittstellen, deren Form ein fremder Standard vorgibt und die nicht zu unserer eigenen API gehören)**: ACME, OAuth/OIDC-Callbacks, Webhooks von Drittanbietern (z. B. GitHub), Health-Checks, die Auslieferung statischer Dateien, OTLP und Ähnliches. Diese nehmen, wie vom jeweiligen Standard verlangt, gewöhnliches HTTP entgegen.
- Referenzimplementierungen: `RPoem` (`open_runo.admin.v1.Admin`) und `open-easy-web` (`server/src/connect.rs`, `proto/open_easy_web/admin/v1/admin.proto`).
- Hinweis: Ob der Code eines einzelnen Repositorys diese Richtlinie bereits erfüllt, hängt vom jeweiligen Repository ab. Dieser Abschnitt dokumentiert lediglich die Richtlinie; er besagt nicht, dass der Code schon angepasst wurde.

### Русский (перевод выполнен с помощью ИИ и отредактирован; носителями языка пока не проверен)
- **От REST мы полностью отказываемся; новые API больше не создаются в стиле REST.** API, к которым обращаются из браузера или через `curl`, используют **унарные вызовы Connect** (`POST /<пакет>.<Service>/<Method>`, `content-type: application/json`, тело запроса — JSON). Для взаимодействия между сервисами применяются **gRPC и gRPC-web** — в том же стиле, что и административный API RPoem (`open_runo.admin.v1.Admin`). Потоковая передача данных добавляется лишь тогда, когда в ней действительно возникает необходимость.
- **Существующие REST-эндпоинты переводятся поэтапно — по мере того, как с ними приходится работать.** После перевода старый REST-маршрут удаляется. Пока миграция не завершена, оставшиеся эндпоинты сохраняются, но **новые не добавляются**.
- **Работа с JSON унифицирована на основе RS-JSON**: чтение — через `from_str_secure` или `parse_secure` (с ограничениями на размер, глубину вложенности и повторяющиеся ключи), запись — через `rust_json::fast`. `prost` в браузерный WASM не включается, поскольку это увеличило бы размер файла.
- **Исключения (интерфейсы, форму которых определяет чужой стандарт, а не наш собственный API)**: ACME, обратные вызовы OAuth/OIDC, вебхуки сторонних сервисов (например, GitHub), проверки работоспособности, раздача статических файлов, OTLP и тому подобное. Такие интерфейсы принимают обычный HTTP, как того требует соответствующий стандарт.
- Эталонные реализации: `RPoem` (`open_runo.admin.v1.Admin`) и `open-easy-web` (`server/src/connect.rs`, `proto/open_easy_web/admin/v1/admin.proto`).
- Примечание: соответствует ли код конкретного репозитория этой политике, зависит от самого репозитория. Данный раздел лишь фиксирует политику и не означает, что код уже изменён.

## API 方針の補足: 用語の整理と使い分け (2026-11-04)

### 日本語
**1つに統一するものではなく、別の層の話です。** 「REST の代わり」になるのは Connect・gRPC・GraphQL だけで、WASM は画面を作る技術です。

| 用語 | 何か | REST の代わりか |
|---|---|---|
| REST | URL と HTTP メソッドで操作を表す API の作り方 | 全廃する側 |
| **Connect** | `POST /サービス名/メソッド名` に JSON を送る形式。`curl` でもブラウザの `fetch` でも呼べる | はい(**採用**) |
| **gRPC** | 同じ「サービス/メソッド」の考え方を、バイナリ(protobuf)と HTTP/2 で行う形式。速く、ストリーミングも得意 | はい(**サービス同士に採用**) |
| gRPC-web | gRPC のブラウザ向けの変形版 | はい(必要なら) |
| GraphQL | 欲しい項目を問い合わせる形式 | 一部だけ(**問い合わせ(読み取り)専用**) |
| WASM | Rust をブラウザの中で動かす仕組み | いいえ(画面を作る技術) |

- **ブラウザの画面や `curl` から呼ぶ API は Connect**(POST、JSON を RS-JSON で読み書き)。ブラウザの WASM は素の gRPC を話せず、Connect なら `fetch` のままで、`prost` を足さずに済む(画面のサイズも増えない)。
- **サービス同士の通信(サーバー間、重い処理、ストリーミング)は gRPC。** 多くは Connect で足りるので、ストリーミングが必要になった所だけ gRPC に上げる。
- **GraphQL は、まとめて問い合わせたいときの読み取り専用。** 書き込み(操作)には使わない。
- **WASM は画面を作る技術として、そのまま使う。** 画面から呼ぶ API が Connect になっただけ。
- 外部の規格が形を決めるもの(ACME、OAuth のコールバック、第三者の Webhook、ヘルスチェック、静的ファイル、OTLP)は、規格どおりの HTTP のまま。
- **迷ったら Connect。**

### English
**These are not alternatives to unify; they sit at different layers.** Only Connect, gRPC and GraphQL can replace REST; WASM is a way to build the UI.

| Term | What it is | Replaces REST? |
|---|---|---|
| REST | API style that expresses operations through URLs and HTTP methods | The thing being abolished |
| **Connect** | `POST /Service/Method` with a JSON body; callable from `curl` and from a browser `fetch` | Yes (**adopted**) |
| **gRPC** | The same service/method idea over binary (protobuf) and HTTP/2; fast, good at streaming | Yes (**for service-to-service**) |
| gRPC-web | A browser-friendly variant of gRPC | Yes (if needed) |
| GraphQL | A query language: ask for exactly the fields you want | Partly (**read-only queries**) |
| WASM | Runs Rust inside the browser | No (a UI technology) |

- **APIs called from browser screens or `curl` use Connect** (POST, JSON read and written with RS-JSON). Browser WASM cannot speak plain gRPC; with Connect it stays a `fetch`, and `prost` is not needed (the binary does not grow).
- **Service-to-service calls (server to server, heavy work, streaming) use gRPC.** Connect is enough in most places; move a call to gRPC only where streaming is actually needed.
- **GraphQL is read-only**, for queries that gather several pieces of data. It is not used for writes (operations).
- **WASM stays as the way to build the UI.** The API it calls simply became Connect.
- Interfaces whose shape an outside standard dictates (ACME, OAuth callbacks, third-party webhooks, health checks, static files, OTLP) stay plain HTTP.
- **When in doubt, use Connect.**

### Deutsch (KI-Übersetzung, sprachlich überarbeitet; noch nicht von Muttersprachlern geprüft)
**Es geht nicht darum, eine einzige Technik auszuwählen – die Begriffe liegen auf unterschiedlichen Ebenen.** Als Ersatz für REST kommen nur Connect, gRPC und GraphQL in Frage; WASM dagegen ist eine Technik, mit der die Benutzeroberfläche gebaut wird.

| Begriff | Was ist das? | Ersatz für REST? |
|---|---|---|
| REST | Ein API-Stil, bei dem Operationen über URLs und HTTP-Methoden ausgedrückt werden | wird abgeschafft |
| **Connect** | `POST /Dienst/Methode` mit JSON im Body; aufrufbar mit `curl` ebenso wie mit `fetch` im Browser | ja (**gewählt**) |
| **gRPC** | Dasselbe Prinzip aus Dienst und Methode, aber über binäres protobuf und HTTP/2; schnell und gut für Streaming geeignet | ja (**zwischen Diensten**) |
| gRPC-web | Eine für den Browser angepasste Variante von gRPC | ja (bei Bedarf) |
| GraphQL | Abfragesprache, mit der man genau die benötigten Felder anfordert | teilweise (**nur für lesende Abfragen**) |
| WASM | Führt Rust-Code direkt im Browser aus | nein (Technik für die Oberfläche) |

- **APIs, die von Browseroberflächen oder per `curl` aufgerufen werden, verwenden Connect** (POST; JSON wird mit RS-JSON gelesen und geschrieben). WASM im Browser kann kein reines gRPC sprechen. Mit Connect bleibt es bei einem gewöhnlichen `fetch`, und `prost` ist nicht nötig – die WASM-Datei wird dadurch nicht größer.
- **Für die Kommunikation zwischen Diensten (Server zu Server, rechenintensive Aufgaben, Streaming) wird gRPC eingesetzt.** In den meisten Fällen reicht Connect aus; auf gRPC wird nur dort umgestellt, wo Streaming tatsächlich gebraucht wird.
- **GraphQL dient ausschließlich lesenden Abfragen**, wenn mehrere Informationen gebündelt abgefragt werden sollen. Für Schreibzugriffe (Operationen) wird es nicht verwendet.
- **WASM bleibt die Technik für die Oberfläche.** Geändert hat sich lediglich, dass die aufgerufene API nun auf Connect beruht.
- Schnittstellen, deren Form durch einen externen Standard festgelegt ist (ACME, OAuth-Callbacks, Webhooks von Drittanbietern, Health-Checks, statische Dateien, OTLP), bleiben gewöhnliches HTTP.
- **Im Zweifel: Connect.**

### Русский (перевод выполнен с помощью ИИ и литературно отредактирован; носителями языка пока не проверен)
**Это не варианты, из которых нужно выбрать один, а технологии разных уровней.** Заменить REST могут только Connect, gRPC и GraphQL; WASM же — это способ создания пользовательского интерфейса.

| Термин | Что это | Заменяет REST? |
|---|---|---|
| REST | Стиль построения API, при котором операции выражаются через URL и HTTP-методы | отменяется |
| **Connect** | `POST /Сервис/Метод` с телом в формате JSON; вызывается как из `curl`, так и из браузерного `fetch` | да (**выбран**) |
| **gRPC** | Тот же принцип «сервис — метод», но поверх двоичного формата protobuf и HTTP/2; работает быстро и хорошо подходит для потоковой передачи | да (**для связи между сервисами**) |
| gRPC-web | Адаптированный для браузера вариант gRPC | да (при необходимости) |
| GraphQL | Язык запросов: клиент запрашивает ровно те поля, которые ему нужны | частично (**только запросы на чтение**) |
| WASM | Позволяет выполнять код на Rust прямо в браузере | нет (технология для интерфейса) |

- **API, которые вызываются из браузерных интерфейсов или через `curl`, строятся на Connect** (POST; JSON читается и записывается через RS-JSON). Браузерный WASM не умеет работать с «чистым» gRPC. С Connect достаточно обычного `fetch`, а `prost` не требуется — размер WASM-файла не увеличивается.
- **Для обмена между сервисами (сервер — сервер, ресурсоёмкие задачи, потоковая передача) применяется gRPC.** В большинстве случаев достаточно Connect; на gRPC переходят только там, где потоковая передача действительно необходима.
- **GraphQL используется только для чтения**, когда нужно получить сразу несколько связанных данных. Для записи (операций) он не применяется.
- **WASM по-прежнему остаётся технологией для интерфейса.** Изменилось лишь то, что вызываемый им API теперь построен на Connect.
- Интерфейсы, форма которых задана внешним стандартом (ACME, обратные вызовы OAuth, вебхуки сторонних сервисов, проверки работоспособности, статические файлы, OTLP), остаются обычным HTTP.
- **Если есть сомнения — выбирайте Connect.**

## 補足: ストリーミングの対応状況 (2026-11-07)

### 日本語
- **server-streaming は対応済み**(`RPoem` の `open-runo-connect-*`、RPoem main `1570371`・`34cb595`)。Connect は `application/connect+json` のエンベロープ、gRPC / gRPC-web でも受ける。途中エラーは終端フレームで返し、件数・時間の上限、切断時の資源解放、実 TCP での `WatchEvents` 試験を通過。**VPS には未反映**。
- **使いどころ**: 変更の監視、進捗の逐次通知、長い生成の逐次返却など、サーバーから複数回返したい所。1回で済む呼び出しは従来どおり Connect の単純呼び出し。client-streaming / 双方向は、必要になってから。
- 独語・露語は未追記(日英のみ)。

### English
- **Server-streaming is supported** (`open-runo-connect-*` in RPoem, main `1570371` / `34cb595`): `application/connect+json` envelopes, also via gRPC / gRPC-web; mid-stream errors end with a terminal frame; item/time limits, resource release on disconnect, and a real-TCP `WatchEvents` test pass. **Not yet deployed to the VPS.**
- **When to use**: watching changes, progress updates, incremental results. One-shot calls stay plain Connect unary. Client-streaming / bidirectional only when needed.
- German and Russian not yet added.

## Windows: アイコンをダブルクリックして使う(GUI・ブラウザ版) / Windows: double-click the icon (GUI and browser wizard)

**日本語**: `install\install-windows.ps1` を実行すると、2FastAPI を専用の Python 環境へ導入し、デスクトップとスタートメニューに「2FastAPI」(アプリ画面)と「2FastAPI (Web)」(ブラウザ画面、このPC内だけで動作)のアイコンを作ります。**open-easy-web が未導入なら自動で導入します(既定。不要なら `-NoOpenEasyWeb`)**。アイコンをダブルクリックするとエクスプローラーのフォルダ選択が開き、「どのフォルダ以下の Flask / Django を」「どのフォルダ以下に」「FastAPI か MFastAPI(`mfastapi.accelerate(app)` で Rust 高速化)として」変換するかを順に聞きます。言語は既定で英語+日本語、ほか日本語・英語・中国語(簡体/台湾繁体)・韓国語・イタリア語・フランス語・ドイツ語・ロシア語・ウクライナ語・ペルシャ語・アラビア語・ヘブライ語から選べます。コマンド: `2fastapi gui` / `2fastapi web` / `2fastapi convert --target mfastapi`。ブラウザ版は 127.0.0.1 のみ・実行ごとのトークン付き(公開サイトの `easy-web.tokyo/2FastAPI` はダウンロード専用で、変換機能は置いていません)。
**English**: Run `install\install-windows.ps1`: it installs 2FastAPI into its own Python environment and puts "2FastAPI" (desktop window) and "2FastAPI (Web)" (browser wizard, served on this PC only) icons on the Desktop and Start menu. **open-easy-web is installed automatically when it is missing (default; use `-NoOpenEasyWeb` to skip).** Double-clicking opens the system folder picker (File Explorer) and asks which folder's Flask/Django projects to convert, into which folder, and as FastAPI or MFastAPI (Rust acceleration via `mfastapi.accelerate(app)`). The UI shows English + Japanese by default and can switch to 13 languages. Commands: `2fastapi gui`, `2fastapi web`, `2fastapi convert --target mfastapi`. The browser wizard listens on 127.0.0.1 only with a per-run token; the public page `easy-web.tokyo/2FastAPI` stays download-only.

## Windows installer (.exe) / Windows インストーラー(.exe)

**日本語**: Windows 版は `2FastAPI-Setup-x64.exe` / `2FastAPI-Setup-arm64.exe`(Inno Setup)で配布します。リリースの Assets から取得してダブルクリックするだけで、Python は不要です(PyInstaller で同梱)。デスクトップとスタートメニューに「2FastAPI」(GUI)と「2FastAPI (Web)」(手元のブラウザ)が作られ、チェックを入れると open-easy-web が未導入の場合に一緒に導入します(既定オン)。サイレント導入は `/VERYSILENT`、削除は設定の「アプリ」またはアンインストーラーから。開発用の PowerShell 版 `install/install-windows.ps1` は残しています。ビルドは `installer/launcher.py` + `installer/2fastapi.iss`、CI の `windows-exe` ジョブが x64/ARM64 を作ります(確認済み: ビルド、サイレント導入、GUI 自己試験、Flask→MFastAPI 変換、アンインストール)。

**English**: The Windows build ships as `2FastAPI-Setup-x64.exe` / `2FastAPI-Setup-arm64.exe` (Inno Setup). Download from the release assets and double-click; no Python needed (bundled with PyInstaller). It creates "2FastAPI" (GUI) and "2FastAPI (Web)" (local browser) icons on the Desktop and Start menu, and optionally installs open-easy-web when missing (on by default). Silent install: `/VERYSILENT`; uninstall via Apps settings or the uninstaller. The PowerShell `install/install-windows.ps1` remains for development. Sources: `installer/launcher.py` + `installer/2fastapi.iss`; the CI `windows-exe` job builds x64/ARM64. Verified: build, silent install, GUI self-test, Flask→MFastAPI conversion, uninstall. Known: PyInstaller's `--icon` failed on this PC (resource write error), so the exe itself has no embedded icon; shortcuts use the shipped `.ico`.

## Django REST framework (DRF) / DRF 変換 (2026-11-16)
**日本語**: `@api_view([...])` の関数ビュー、`APIView` クラス(HTTP メソッドごとの関数に展開)、`Response(data, status=...)`(→ そのまま返す/`JSONResponse`、本文なしは `Response(status_code=…)`)、`status.HTTP_201_CREATED` → `201`、`request.data.get/[]` → JSON ボディ、`request.query_params` → クエリ、`serializers.Serializer` → pydantic `BaseModel`(`max_length`・`min_value`・`required=False`・`default`・`read_only` 対応)、`ser = XSerializer(data=request.data)` + `is_valid()` / `validated_data` → ボディ引数。`@permission_classes` などは警告つきで除去。DRF 本物との差分0を `tests/test_drf_diff.py`(サンプル `examples/drf_proj`)で確認。**未対応**: `ModelSerializer`・`ViewSet`/`ModelViewSet`・`Router`・`generics`(ORM 依存。警告を出して元のまま残す)、不正入力のエラー形式(DRF は 400、FastAPI は 422)。
**English**: Converts `@api_view([...])` function views, `APIView` classes (one route per HTTP method), `Response(data, status=...)` (returned as-is / `JSONResponse`; empty bodies → `Response(status_code=…)`), `status.HTTP_201_CREATED` → `201`, `request.data.get/[]` → JSON body, `request.query_params` → query, `serializers.Serializer` → pydantic `BaseModel` (`max_length`, `min_value`, `required=False`, `default`, `read_only`), and `ser = XSerializer(data=request.data)` + `is_valid()` / `validated_data` → a body parameter. `@permission_classes` etc. are dropped with a warning. Verified against real DRF with 0 differences (`tests/test_drf_diff.py`, sample `examples/drf_proj`). **Not converted**: `ModelSerializer`, `ViewSet`/`ModelViewSet`, routers, `generics` (ORM-bound; warned and left as-is), and the invalid-input error shape (DRF 400, FastAPI 422).

## 2026-11-17 到達点 / Status
**日本語**: v0.3.3 公開(CI緑、exe x64/arm64+wheel)。Flask `session`→`request.session`(SessionMiddleware、秘密鍵は環境変数`SECRET_KEY`、要`itsdangerous`)、`g`→`request.state`を自動変換(差分試験`tests/test_flask_session.py`、43件成功)。未了: PyPI公開(所有者の認証が必要)、`teardown_request`・Flask-SQLAlchemy・`flask_login`は警告のみ。
**English**: v0.3.3 released (CI green, x64/arm64 exe + wheel). Flask `session` -> `request.session` (SessionMiddleware, secret from env `SECRET_KEY`, needs `itsdangerous`) and `g` -> `request.state` are converted (differential test `tests/test_flask_session.py`; 43 pass). Open: PyPI (owner credentials), `teardown_request`, Flask-SQLAlchemy and `flask_login` remain warnings only.

## 2026-11-17 v0.4.0 / Status
**日本語**: `teardown_request`(ミドルウェア)、`before_first_request`(startup)、Flask-SQLAlchemy(SQLAlchemy互換層、リクエスト単位セッション、`get_or_404`)、Flask-Login(セッション互換層、`login_required`/`fresh_login_required`/`request_loader`/`unauthorized_handler`)、Flask-SQLAlchemy の `paginate`・複数bind(`__bind_key__`/`SQLALCHEMY_BINDS`)、`app.config`、`with app.app_context()` を自動変換。変換前のFlask/Djangoのバージョンは自動判定、変換後のFastAPIのバージョンは`--fastapi-version`で指定(既定は最新、旧版は`TemplateResponse`旧形式+`requirements.txt`固定)。Django: `render()`/`render_to_response()`(Django 3.0未満)をJinja2Templatesへ自動変換し、`templates/`(ルートと各アプリ)を出力へ統合(差分試験`tests/test_django_render.py`)。試験54件成功(v0.5.0)。未了: Flask-Login の remember-me クッキー(セッションのみ)、Django側の版別の差(現状は検出と報告が中心)。
**English**: `teardown_request` (middleware), `before_first_request` (startup), Flask-SQLAlchemy (SQLAlchemy shim, per-request session, `get_or_404`), Flask-Login (session shim: `login_required`, `fresh_login_required`, `request_loader`, `unauthorized_handler`), Flask-SQLAlchemy `paginate` and multiple binds (`__bind_key__`/`SQLALCHEMY_BINDS`), `app.config` and `with app.app_context()` are converted. Source Flask/Django versions are auto-detected; the target FastAPI version is selectable with `--fastapi-version` (default latest; older targets get the old `TemplateResponse` form and a pinned `requirements.txt`). Django: `render()` / `render_to_response()` (pre-3.0) convert to Jinja2Templates and `templates/` dirs (root and per app) are merged into the output (differential test `tests/test_django_render.py`). 54 tests pass (v0.5.0). Open: Flask-Login remember-me cookie (session only), version-specific Django differences (currently detection + reporting).

## open-cpu の同梱と、アクセラレーターの扱い(2026-11-17)
- **同梱済み(実行時に AVX-512BW > AVX2 > NEON > スカラーを自動選択、`OPEN_CPU_MAX_ISA`で上限指定可)**: MFastAPI(`--cpu`、長いクエリ文字列の探索)、RMojo(`rmojo cpu`、`str.find`/`str.count`)、open-web-server・open-easy-web(起動時の要約、`System/GetCpu`、FastCGIヘッダー走査)。実機はNEONをSnapdragon端末2台で、AVX-512BWはCIで確認(開発PCはAVX2まで)。
- **2FastAPI**: 変換ツール(Python)で、実行時の計算処理を持たないため open-cpu は使わない。
- **open-cuda / aruaru-llm / open-directx は同梱しない**: 共有基盤を1回だけVPSに入れ、各サイトはConnect/gRPCで呼ぶ方針(本ファイル冒頭の配備アーキテクチャ方針)に従う。
- **ブラウザ(Windows/Linux/Mac/Android/iPhone)**: 計算はサーバー側で行うため、どの端末のブラウザからでも利用できる。RMojoのWASM(`wasm32-unknown-unknown`の`cargo check`は通過)は将来の遊び場候補。WASMでは open-cpu のSIMD自動選択は使わない。
- **スマホのアクセラレーター化**: `open-cpu/remote`(`open-cpu-remote`)。実測では手元PCが速いため自動判断は「手元のみ」で、手元が非力な場合に効く。詳細は`open-cpu/remote/README.md`。

## 起動時の自動バージョンアップ(2026-11-17)/ Self-update at startup
**日本語**: 起動のたびに前回の確認から24時間以上たっていれば、切り離した子プロセスで GitHub の最新リリースを調べ、新しければ取得して入れ替える(起動は遅くならない。更新は次回の起動から有効で、その旨を一度だけ表示)。**リリースの `<ファイル名>.sha256` と一致したときだけ**入れ替え、`.sha256` が無いリリース・GitHub 以外の取得先・先行版(-alpha 等)へは更新しない。信頼の根拠は GitHub への TLS と SHA-256(電子署名ではない)。手動実行と停止は下表。失敗は黙って次回に回し、理由は状態ディレクトリの `last_error` に残る。
**English**: On each start, if 24 h have passed since the last check, a detached child process queries the latest GitHub release and, if newer, downloads and swaps it in (startup is not delayed; the update takes effect on the next start, announced once). It installs **only if the SHA-256 matches the release's `<file>.sha256`**; releases without `.sha256`, non-GitHub hosts and pre-releases are refused. Trust = TLS to GitHub + SHA-256 (not a signature). Failures are silent and recorded in `last_error` in the state directory.
- 2FastAPI: pip 版は `2fastapi`/`2fastapi-gui` 起動時に、`pip download --no-index`→SHA-256 検証→`pip install --no-deps`(別の仮想環境で 0.5.0→0.5.1 を実リリースで確認済み)。インストーラー版(Windows)は新しい `2FastAPI-Setup-<arch>.exe` を取得・検証して置き、次回起動時に静かに実行。手動: `python -m tofastapi._autoupdate --now`、停止: `TOFASTAPI_NO_UPDATE=1`。状態: `~/.2fastapi/`。

## 上流の新版への追従(2026-11-17)/ Following upstream releases
- **定期試験**: CI を毎日(UTC 03:23)実行し、最新の Python・Flask・Django・FastAPI・Starlette(RMojo は最新の CPython との差分試験)で再試験。失敗したら日付つきの issue を1件起こす。
- **easy-web.tokyo**: `runo/scripts/refresh_versions.py` を VPS のタイマー(`easy-web-intros-refresh.timer`、1時間ごと)で実行し、MFastAPI・RMojo・2FastAPI・2FastAPI-VSC の最新版と上流(Python・Flask・Django・FastAPI・Starlette・Rust・Mojo)の最新版を各紹介ページと `/demo` に表示(`<製品>/versions.json`)。ページはダウンロード専用のまま。
- **未了**: 上流の新版が出たときに、利用者の環境(Flask/Django 等)まで自動で上げる機能は無い(本製品が更新するのは本製品自身)。aruaru-llm の同梱は未着手(open-cpu は同梱済み)。iPhone・iPad には対応していない。

## DRF ViewSet・ModelViewSet / Flask JWT・marshmallow (2026-11-17)
**日本語 (v0.5.2, 2026-11-17)**: DRF の `ViewSet`(`list/create/retrieve/update/destroy`)と `DefaultRouter`/`SimpleRouter` の `register`、`ModelSerializer`(`Meta.model/fields/read_only_fields`、単純なフィールドのみ)+ Django `models.Model` → SQLAlchemy テーブル+pydantic、`ModelViewSet`/`ReadOnlyModelViewSet`(`queryset = Model.objects.all()`)→ 生成した CRUD ルート(環境変数 `DATABASE_URL`、既定 `sqlite:///db.sqlite3`)を変換。Flask-JWT-Extended(`JWTManager`、`create_access_token`/`create_refresh_token`、`jwt_required(optional/fresh/refresh)`、`get_jwt`/`get_jwt_identity`、`verify_jwt_in_request`)→ PyJWT 互換層(クレームも 401/422 の応答文言も同じ。Flask 側が発行したトークンを変換後が受け付けることを確認。要 `pyjwt`)。marshmallow はそのまま動く(`Schema.load` 等は変更不要)ため Flask-SQLAlchemy+marshmallow+JWT の組み合わせを差分試験(`tests/test_flask_jwt_marshmallow.py`、`tests/test_drf_viewset.py`、`tests/test_drf_model.py`)。**未対応**: `@action`・`generics`・Router の `format` 接尾辞、ModelSerializer の入れ子/日時/Decimal/外部キー、JWT の Cookie/CSRF・ブロックリスト・`*_loader`、`flask_marshmallow`(`ma.SQLAlchemyAutoSchema`)。
**English (v0.5.2, 2026-11-17)**: DRF `ViewSet` (`list/create/retrieve/update/destroy`) with `DefaultRouter`/`SimpleRouter` `register`; `ModelSerializer` (`Meta.model/fields/read_only_fields`, simple fields only) + Django `models.Model` -> SQLAlchemy table + pydantic; `ModelViewSet`/`ReadOnlyModelViewSet` (`queryset = Model.objects.all()`) -> generated CRUD routes (env `DATABASE_URL`, default `sqlite:///db.sqlite3`). Flask-JWT-Extended (`JWTManager`, `create_access_token`/`create_refresh_token`, `jwt_required(optional/fresh/refresh)`, `get_jwt`/`get_jwt_identity`, `verify_jwt_in_request`) -> a PyJWT shim with the same claims and the same 401/422 answers (a token issued by the Flask app is accepted by the converted app; needs `pyjwt`). Plain marshmallow keeps working unchanged (`Schema.load` etc.), so the Flask-SQLAlchemy + marshmallow + JWT combination is covered by differential tests (`tests/test_flask_jwt_marshmallow.py`, `tests/test_drf_viewset.py`, `tests/test_drf_model.py`). **Not converted**: `@action`, `generics`, router `format` suffixes, nested/datetime/Decimal/ForeignKey ModelSerializer fields, JWT cookies/CSRF/blocklist/`*_loader` callbacks, `flask_marshmallow` (`ma.SQLAlchemyAutoSchema`).

## 利用者の環境を上流の新版へ上げる: `2fastapi upgrade` / Upgrading your pinned dependencies (2026-11-18)
**日本語 (v0.5.3)**: 明示コマンドのみ。**自動では絶対に上げません**(起動時の自動更新は 2FastAPI 自身だけで、利用者のプロジェクトには触れません)。`2fastapi upgrade <プロジェクト> --check` は `requirements*.txt` / `pyproject.toml` の固定版(`==`)と上流の最新安定版(PEP 503 索引、既定は PyPI。先行版・yank 済みは除外)の差を一覧にするだけで何も変更しません。`--apply` は、プロジェクトを一時フォルダへコピーして固定版を書き換え、**別の一時 venv** に導入し、プロジェクトのテスト(`pytest`、または `--test-cmd`。`{python}` は一時 venv の python)を実行します。**全成功のときだけ**元のファイルの固定版を書き換え、失敗したら元のファイルは一切変更せず、段階(resolve=依存解決 / tests=試験)と出力の末尾を報告します(終了コード 1)。ネットワーク無し・索引に到達できない・固定版が無い・**テストが無い**(`--test-cmd` も無い)ときは何も変えずに停止します(終了コード 2)。対象は既定で Flask / Django / FastAPI / Starlette と関連(DRF・Flask-SQLAlchemy・SQLAlchemy・marshmallow・Flask-JWT-Extended・pydantic・uvicorn・mfastapi)、`--package NAME`(複数可)・`--all`・`--index-url` で変更できます。差分試験: `tests/test_upgrade.py`(実 venv で 成功→書き換え / 失敗→元のまま / 依存解決の失敗 / テスト無し / 索引不達 / 実 PyPI)。**未対応**: Poetry/Pipenv/ハッシュ付き固定、範囲指定(`>=`)の書き換え、変換後アプリの差分試験の自動実行(必要なら `--test-cmd` で指定)。
**English (v0.5.3)**: An explicit command only; **nothing is ever upgraded automatically** (the startup self-update touches 2FastAPI itself, never your project). `2fastapi upgrade PROJECT --check` lists the pinned (`==`) versions in `requirements*.txt` / `pyproject.toml` against the latest stable upstream release (PEP 503 index, PyPI by default; pre-releases and yanked files ignored) and changes nothing. `--apply` copies the project to a temporary folder, rewrites the pins there, installs them into a **separate temporary venv** and runs the project's tests (`pytest`, or `--test-cmd`, where `{python}` is the temp venv's python). **Only if everything passes** are the pins in your files rewritten; on failure your files are left untouched and the stage (resolve = dependency resolution / tests) and the output tail are reported (exit code 1). With no network / unreachable index / no pins / **no tests** (and no `--test-cmd`) it stops without changing anything (exit code 2). Default scope: Flask, Django, FastAPI, Starlette and related (DRF, Flask-SQLAlchemy, SQLAlchemy, marshmallow, Flask-JWT-Extended, pydantic, uvicorn, mfastapi); change with `--package NAME` (repeatable), `--all`, `--index-url`. Differential tests: `tests/test_upgrade.py` (real venvs: success -> rewrite / failure -> untouched / resolution failure / no tests / unreachable index / real PyPI). **Not covered**: Poetry/Pipenv/hash-pinned files, rewriting range specifiers (`>=`), and running a converted-app differential test automatically (pass it via `--test-cmd`).
