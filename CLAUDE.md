# 2FastAPI 開発方針 / Development notes

**日本語**: 共通ルールは [`open-raid-z/CLAUDE.md`](https://github.com/aon-co-jp/open-raid-z) と [`runo`](https://github.com/aon-co-jp/runo) の `CLAUDE.md` を参照。チャットは日本語のみ。確認なしで開発・TEST・DEBUG・commit・push。UI・インストーラーはリリース前に実機/エミュレーターで確認。heredocでバックスラッシュを含むコードを書かない(Writeツールを使う)。
**English**: shared rules live in `open-raid-z/CLAUDE.md` and `runo/CLAUDE.md`. Chat in Japanese only. Develop, test, debug, commit and push without asking. Verify UI/installers on real devices/emulators before each release. Do not write code containing backslashes through bash heredocs (use the Write tool).

## 状態 / Status
- 日本語: v0.2.0+。Flask(フック・render_template・request.files・Flask-RESTful/MethodView)とDjango(View継承クラス)をFastAPIへ変換。scan/auto/convertで複数プロジェクトを自動検出し、変換先を英日で質問(無ければ作成確認)。差分テスト36件、CIは3OS成功。
- English: v0.2.0+. Converts Flask (hooks, render_template, request.files, Flask-RESTful/MethodView) and Django (View subclasses) to FastAPI. scan/auto/convert detect several projects and ask in English and Japanese where to put the result (creating folders). 36 differential tests, CI green on 3 OSes.

## 未了 / Open
- 日本語: PyPI公開(DRF ViewSet/ModelViewSet・Flask JWT/marshmallow は v0.5.2 で対応済み)、Python 3.14ネイティブのlibcst(WindowsのPythonにlibcst無し→テストはWSL)。
- English: PyPI publication (DRF ViewSet/ModelViewSet and Flask JWT/marshmallow done in v0.5.2), libcst on native Windows Python 3.14 (tests run in WSL).

詳細・再開用メッセージ / details and the resume message: [`PORTING.md`](PORTING.md)

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

## DRF ViewSet・ModelViewSet / Flask JWT・marshmallow (2026-11-17)
**日本語 (v0.5.2, 2026-11-17)**: DRF の `ViewSet`(`list/create/retrieve/update/destroy`)と `DefaultRouter`/`SimpleRouter` の `register`、`ModelSerializer`(`Meta.model/fields/read_only_fields`、単純なフィールドのみ)+ Django `models.Model` → SQLAlchemy テーブル+pydantic、`ModelViewSet`/`ReadOnlyModelViewSet`(`queryset = Model.objects.all()`)→ 生成した CRUD ルート(環境変数 `DATABASE_URL`、既定 `sqlite:///db.sqlite3`)を変換。Flask-JWT-Extended(`JWTManager`、`create_access_token`/`create_refresh_token`、`jwt_required(optional/fresh/refresh)`、`get_jwt`/`get_jwt_identity`、`verify_jwt_in_request`)→ PyJWT 互換層(クレームも 401/422 の応答文言も同じ。Flask 側が発行したトークンを変換後が受け付けることを確認。要 `pyjwt`)。marshmallow はそのまま動く(`Schema.load` 等は変更不要)ため Flask-SQLAlchemy+marshmallow+JWT の組み合わせを差分試験(`tests/test_flask_jwt_marshmallow.py`、`tests/test_drf_viewset.py`、`tests/test_drf_model.py`)。**未対応**: `@action`・`generics`・Router の `format` 接尾辞、ModelSerializer の入れ子/日時/Decimal/外部キー、JWT の Cookie/CSRF・ブロックリスト・`*_loader`、`flask_marshmallow`(`ma.SQLAlchemyAutoSchema`)。
**English (v0.5.2, 2026-11-17)**: DRF `ViewSet` (`list/create/retrieve/update/destroy`) with `DefaultRouter`/`SimpleRouter` `register`; `ModelSerializer` (`Meta.model/fields/read_only_fields`, simple fields only) + Django `models.Model` -> SQLAlchemy table + pydantic; `ModelViewSet`/`ReadOnlyModelViewSet` (`queryset = Model.objects.all()`) -> generated CRUD routes (env `DATABASE_URL`, default `sqlite:///db.sqlite3`). Flask-JWT-Extended (`JWTManager`, `create_access_token`/`create_refresh_token`, `jwt_required(optional/fresh/refresh)`, `get_jwt`/`get_jwt_identity`, `verify_jwt_in_request`) -> a PyJWT shim with the same claims and the same 401/422 answers (a token issued by the Flask app is accepted by the converted app; needs `pyjwt`). Plain marshmallow keeps working unchanged (`Schema.load` etc.), so the Flask-SQLAlchemy + marshmallow + JWT combination is covered by differential tests (`tests/test_flask_jwt_marshmallow.py`, `tests/test_drf_viewset.py`, `tests/test_drf_model.py`). **Not converted**: `@action`, `generics`, router `format` suffixes, nested/datetime/Decimal/ForeignKey ModelSerializer fields, JWT cookies/CSRF/blocklist/`*_loader` callbacks, `flask_marshmallow` (`ma.SQLAlchemyAutoSchema`).

## 利用者の環境を上流の新版へ上げる: `2fastapi upgrade` / Upgrading your pinned dependencies (2026-11-18)
**日本語 (v0.5.3)**: 明示コマンドのみ。**自動では絶対に上げません**(起動時の自動更新は 2FastAPI 自身だけで、利用者のプロジェクトには触れません)。`2fastapi upgrade <プロジェクト> --check` は `requirements*.txt` / `pyproject.toml` の固定版(`==`)と上流の最新安定版(PEP 503 索引、既定は PyPI。先行版・yank 済みは除外)の差を一覧にするだけで何も変更しません。`--apply` は、プロジェクトを一時フォルダへコピーして固定版を書き換え、**別の一時 venv** に導入し、プロジェクトのテスト(`pytest`、または `--test-cmd`。`{python}` は一時 venv の python)を実行します。**全成功のときだけ**元のファイルの固定版を書き換え、失敗したら元のファイルは一切変更せず、段階(resolve=依存解決 / tests=試験)と出力の末尾を報告します(終了コード 1)。ネットワーク無し・索引に到達できない・固定版が無い・**テストが無い**(`--test-cmd` も無い)ときは何も変えずに停止します(終了コード 2)。対象は既定で Flask / Django / FastAPI / Starlette と関連(DRF・Flask-SQLAlchemy・SQLAlchemy・marshmallow・Flask-JWT-Extended・pydantic・uvicorn・mfastapi)、`--package NAME`(複数可)・`--all`・`--index-url` で変更できます。差分試験: `tests/test_upgrade.py`(実 venv で 成功→書き換え / 失敗→元のまま / 依存解決の失敗 / テスト無し / 索引不達 / 実 PyPI)。**未対応**: Poetry/Pipenv/ハッシュ付き固定、範囲指定(`>=`)の書き換え、変換後アプリの差分試験の自動実行(必要なら `--test-cmd` で指定)。
**English (v0.5.3)**: An explicit command only; **nothing is ever upgraded automatically** (the startup self-update touches 2FastAPI itself, never your project). `2fastapi upgrade PROJECT --check` lists the pinned (`==`) versions in `requirements*.txt` / `pyproject.toml` against the latest stable upstream release (PEP 503 index, PyPI by default; pre-releases and yanked files ignored) and changes nothing. `--apply` copies the project to a temporary folder, rewrites the pins there, installs them into a **separate temporary venv** and runs the project's tests (`pytest`, or `--test-cmd`, where `{python}` is the temp venv's python). **Only if everything passes** are the pins in your files rewritten; on failure your files are left untouched and the stage (resolve = dependency resolution / tests) and the output tail are reported (exit code 1). With no network / unreachable index / no pins / **no tests** (and no `--test-cmd`) it stops without changing anything (exit code 2). Default scope: Flask, Django, FastAPI, Starlette and related (DRF, Flask-SQLAlchemy, SQLAlchemy, marshmallow, Flask-JWT-Extended, pydantic, uvicorn, mfastapi); change with `--package NAME` (repeatable), `--all`, `--index-url`. Differential tests: `tests/test_upgrade.py` (real venvs: success -> rewrite / failure -> untouched / resolution failure / no tests / unreachable index / real PyPI). **Not covered**: Poetry/Pipenv/hash-pinned files, rewriting range specifiers (`>=`), and running a converted-app differential test automatically (pass it via `--test-cmd`).

## OS別インストーラー: macOS .pkg・Linux .deb / Per-OS installers (2026-11-18)
**日本語 (v0.5.4)**: Windows は従来どおり `2FastAPI-Setup-x64.exe` / `-arm64.exe`(Inno Setup)。**macOS** は `2FastAPI-<版>-macos-x64.pkg` / `-arm64.pkg`(`pkgbuild`+`productbuild`)で、**管理者権限なしで利用者のホームに入ります**(`installer -pkg ... -target CurrentUserHomeDirectory`、またはダブルクリックで「自分専用」に導入): `~/Library/2FastAPI/2fastapi`(本体)、`~/Library/2FastAPI/uninstall.sh`(`.pkg` には削除機能が無いため同梱。`sh ~/Library/2FastAPI/uninstall.sh`)、PATH 用のリンク `~/.local/bin/2fastapi`。**Linux** は `2fastapi_<版>_amd64.deb` / `_arm64.deb`(`dpkg-deb`)で、`/usr/bin/2fastapi` と `/usr/share/doc/2fastapi/` のみを置き、`dpkg -r 2fastapi` で残骸なく消えます。どちらも PyInstaller で Python ごと同梱した CLI 版(GUI は Windows 版のみ。`2fastapi web` はどの OS でも可)。**自動更新との整合**: Windows の Setup 版だけが自分で更新します。`.pkg`/`.deb` 版は OS の管理下に置かれるため**自分では書き換えず**、24時間に1回(切り離したスレッド)最新リリースを調べて、新しい版があれば stderr に一度だけ知らせます(入れ直すのは利用者)。`TOFASTAPI_NO_UPDATE=1`(CI・pytest 実行中も)で通知も止まります。状態は `~/.2fastapi/`(`.pkg`/`.deb` の削除では消えません)。試験: `.deb` は WSL Ubuntu で `dpkg -i` → 起動 → Flask 変換 → `dpkg -r` → 残骸なしを確認(`installer/test-deb.sh`)、`.pkg` は CI(macOS)で `pkgutil --expand` と `installer -pkg` → 起動 → `uninstall.sh` → 残骸なし(`installer/test-pkg.sh`)。CI の `deb` / `pkg` ジョブがタグで資産と `.sha256` をリリースに添付します。**未対応**: macOS の署名・公証(未署名のため、ダブルクリックでは「開発元を確認できない」と出る場合は右クリック→開く、または `installer` コマンド)、Linux の rpm / apt リポジトリ。
**English (v0.5.4)**: Windows is unchanged (`2FastAPI-Setup-x64.exe` / `-arm64.exe`, Inno Setup). **macOS**: `2FastAPI-<ver>-macos-x64.pkg` / `-arm64.pkg` (`pkgbuild` + `productbuild`) that install **for the current user without admin rights** (`installer -pkg ... -target CurrentUserHomeDirectory`, or double-click and choose "install for me only"): `~/Library/2FastAPI/2fastapi` (the program), `~/Library/2FastAPI/uninstall.sh` (a `.pkg` has no uninstaller of its own, so one is shipped: `sh ~/Library/2FastAPI/uninstall.sh`) and a PATH symlink `~/.local/bin/2fastapi`. **Linux**: `2fastapi_<ver>_amd64.deb` / `_arm64.deb` (`dpkg-deb`) that put only `/usr/bin/2fastapi` and `/usr/share/doc/2fastapi/` on the system and vanish cleanly with `dpkg -r 2fastapi`. Both are PyInstaller CLI builds bundling Python (the GUI is Windows-only; `2fastapi web` works everywhere). **Self-update**: only the Windows Setup build updates itself. The `.pkg` / `.deb` builds are managed by the OS, so they **never rewrite themselves**: once every 24 hours (detached thread) they check the latest release and print one notice on stderr if a newer one exists (re-installing is up to you). `TOFASTAPI_NO_UPDATE=1` (also set under CI / pytest) silences the notice too. State lives in `~/.2fastapi/` (not removed by uninstalling). Tests: the `.deb` is checked in WSL Ubuntu with `dpkg -i` -> run -> Flask conversion -> `dpkg -r` -> nothing left (`installer/test-deb.sh`); the `.pkg` in CI (macOS) with `pkgutil --expand` and `installer -pkg` -> run -> `uninstall.sh` -> nothing left (`installer/test-pkg.sh`). The CI `deb` / `pkg` jobs attach the assets and `.sha256` files to the release on tags. **Not covered**: macOS code signing / notarisation (unsigned: if double-clicking warns about an unidentified developer, right-click -> Open, or use the `installer` command), Linux rpm / apt repository.

**CI の構成メモ / CI layout (2026-11-18)**: 日本語: `deb` ジョブは macOS の試験を待たず、Ubuntu のみの `test-linux` に依存(macOS の runner 待ちで止まらないため)。そのためタグでは、macOS の試験が失敗していても `.deb` だけ先にリリースへ添付され得る。`pkg`・`release`・`windows-exe` は従来どおり全 OS の `test` を待つ。`.pkg` の `installer -pkg ... -target CurrentUserHomeDirectory` は CI 実機(macOS)での初回確認が未了。 / English: the `deb` job no longer waits for the macOS tests; it depends on the Ubuntu-only `test-linux` job (so a congested macOS runner pool cannot block it). On tags a `.deb` can therefore be attached even if a macOS test failed. `pkg`, `release` and `windows-exe` still wait for the full `test` matrix. The `.pkg` `installer -pkg ... -target CurrentUserHomeDirectory` path has not yet been confirmed on a real CI macOS runner.

## 引っ越しメッセージ(別アカウント・別PCで再開する人へ) / Handover message (2026-11-18)
**日本語**: 1) `F:\2FastAPI\PORTING.md` の先頭「状態・未了・再開用メッセージ」を読む。2) `gh run list` で CI を確認する(v0.5.3 はタグ済みだが macOS の runner 待ちでリリース未作成、v0.5.4 は未タグ)。3) v0.5.4 は `deb`(Ubuntu のみで先に走る)と `pkg`(macOS 実機で初回)の結果を見て、通ってからタグ `v0.5.4` を打つ。`.pkg` が失敗したら CI ログから `installer/build-pkg.sh` / `test-pkg.sh` を直す。4) テストは WSL で `bash run-tests.sh`(`setup-wsl.sh` で環境作成)。`.deb` は `installer/wsl-run.sh`(root)。5) チャットは日本語のみ、確認なしで開発・TEST・DEBUG・commit・push。PyPI 公開は所有者の認証が要るので対象外。
**English**: 1) Read the top of `F:\2FastAPI\PORTING.md` (status, open items, resume message). 2) Check CI with `gh run list` (v0.5.3 is tagged but its release does not exist because the macOS runner pool is congested; v0.5.4 is untagged). 3) For v0.5.4 look at the `deb` job (runs on Ubuntu only, so it finishes first) and the `pkg` job (first run on a real macOS runner), then tag `v0.5.4` once they pass. If the `.pkg` fails, fix `installer/build-pkg.sh` / `test-pkg.sh` from the CI log. 4) Tests: `bash run-tests.sh` in WSL (`setup-wsl.sh` creates the env); the `.deb` check is `installer/wsl-run.sh` (as root). 5) Chat in Japanese only; develop, test, debug, commit and push without asking. PyPI publication needs the owner's credentials and is out of scope.

## Versionless API の方針 / Versionless API policy (2026-11-25)
**日本語**: このリポジトリのAPIは **Versionless**(URL・パッケージ名に `v1` 等を付けず、互換性を壊さず足すだけで進化させる)。欄は足すだけ・足す欄は省略可能・知らない欄は無視・名前変更は新名を足して旧を非推奨に(期限は既定で6か月以上、使用0を確認してから削除)・enumは未知の値を許容・安全上の緊急修正は例外。既存の `.v1` は呼び出し側を壊さないよう当面残し、版なしの別名を追加して段階的に畳む。詳細・出典は [`runo/API-POLICY.md`](https://github.com/aon-co-jp/runo/blob/main/API-POLICY.md) 末尾。適用はこれから順に行う。
**English**: This repository's APIs are **Versionless**: no `v1` in URLs or package names; evolve by adding only, without breaking compatibility. Only add fields, new fields are optional, ignore unknown fields, rename by adding the new name and deprecating the old (default deadline 6 months or more, remove only after confirming zero use), tolerate unknown enum values, emergency security fixes are the exception. Existing `.v1` names stay for now so callers do not break; a versionless alias is added and `.v1` is retired in stages. Details and sources: the end of [`runo/API-POLICY.md`](https://github.com/aon-co-jp/runo/blob/main/API-POLICY.md). Rollout is step by step.

## 完成まで作り切る方針 / Finish everything policy (2026-11-27)
**日本語**: 全リポジトリで、**未確認は自動で確認し、未実施は実施し、未了は完成させる**(確認を求めず進める)。使用頻度が低いと判断される機能や、**1から作り直す大規模開発になる内容でも、やめずに最後まで開発・TEST・DEBUGする**(別の方式で済ませない、後回しにしない)。進め方: 調査(英語・日本語の検索とGitHub) → 設計 → 実装 → 実機/実データで確認 → 失敗は原因を直して再試験 → README・CLAUDE・PORTING・POLICY を日英で更新 → push。「できた」と書くのは実測した範囲だけ、確認できなかった所は「未確認」と正直に書く。例外(確認を取る): 元に戻せない削除、秘密の公開、所有者の認証・決済・実機操作が要るもの、利用者のシステム設定の変更。
**English**: In every repository, **verify what is unverified, do what is not yet done, and finish what is unfinished** automatically, without asking. Even features that look rarely used, or work that means **a large rewrite from scratch, are developed, tested and debugged to the end** (no substituting another approach, no postponing). Method: research (English and Japanese search plus GitHub) -> design -> implement -> verify on real devices or data -> fix causes and retest on failure -> update README, CLAUDE, PORTING and POLICY in Japanese and English -> push. Write "done" only for what was measured, and say "unverified" honestly for the rest. Exceptions that still need confirmation: irreversible deletions, publishing secrets, anything needing the owner's authentication, payment or real-device actions, and changes to the user's system settings.