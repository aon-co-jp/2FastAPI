# 2FastAPI (to FastAPI)

**日本語**: DjangoやFlaskを使ったPythonプログラムを **FastAPI** へ変換するツール(`2` = `to`、`toFastAPI`)。出力は FastAPI と互換のコードで、[MFastAPI](https://github.com/aon-co-jp/MFastAPI)(FastAPI互換を保証)でもそのまま動く想定。コメントと書式は保ったまま書き換える(libcst)。

**VS Code 拡張 / extension**: [2FastAPI-VSC](https://github.com/aon-co-jp/2FastAPI-VSC)

**English**: Converts Python programs written with **Django or Flask** to **FastAPI** (`2` = `to`). The output is plain FastAPI code that also targets [MFastAPI](https://github.com/aon-co-jp/MFastAPI). Comments and formatting are preserved (libcst). 変換できない部分は黙って壊さず、**警告として報告**する。 / What cannot be converted is reported as a warning, never silently mis-converted.

```
pip install tofastapi           # (またはGitHub Releaseのwheel / or the wheel from the GitHub Release)
2fastapi flask app.py -o app_fastapi.py
2fastapi django path/to/project -o out_dir      # urls.py + views.py -> routers + main.py + CONVERSION_REPORT.md
2fastapi scan <dir>                 # フォルダ配下の Flask / Django を自動検出 / detect projects
2fastapi auto <dir>                 # 検出 → 変換先を英語・日本語で質問(無ければ作成) / ask where to put the result (EN/JA)
2fastapi auto <dir> -o out --yes    # 質問なし・フォルダ自動作成 / no questions, create folders
uvicorn main:app --reload
```

## 変換するもの / What is converted

| Flask | FastAPI |
|---|---|
| `Flask(__name__)`, `app.run(...)` | `FastAPI()`, `uvicorn.run(app, ...)` |
| `@app.route(rule, methods=[...])`, `@app.get/post/...` | `@app.get/post/...` / `api_route` |
| `<int:id>` `<float:x>` `<path:p>` `<uuid:u>` `<name>` | `{id}` + 型注釈 / `{p:path}` / `uuid.UUID` |
| `request.args.get("q", d, type=int)` / `args["q"]` / `getlist` | クエリパラメータ / query parameters |
| `request.form`, `request.headers`, `request.cookies` | `Form` / `Header` / `Cookie` |
| `request.get_json()` / `request.json` | `payload: Any = Body(None)` |
| `request.method` / `.path` / `.remote_addr` / `url_for` | `Request` 引数 |
| `jsonify(...)`, `return (body, status[, headers])` | dict / `JSONResponse` / `HTMLResponse` |
| `abort(404)`, `redirect(url)` | `HTTPException` / `RedirectResponse(status_code=302)` |
| `Blueprint(url_prefix=)`, `register_blueprint` | `APIRouter(prefix=)`, `include_router` |
| `flask_cors.CORS(app)` | `CORSMiddleware` |
| `@app.before_request` / `after_request` | `@app.middleware("http")` |
| `@app.errorhandler(404)` | `@app.exception_handler(404)` |
| `render_template("x.html", ...)` | `Jinja2Templates.TemplateResponse` |
| `request.files["f"]` (`.read()` `.save()` `.filename`) | `UploadFile` + 同梱の `_Upload` ラッパー / wrapper |
| `flask_restful` `Resource` + `api.add_resource`、`MethodView` + `add_url_rule` | メソッドごとのルート関数 / one route function per method |

| Django | FastAPI |
|---|---|
| `urls.py`: `path()`, `re_path()`, `include()` (入れ子 / nested) | `APIRouter` のパス + `main.py` |
| `<int:pk>` `<slug:s>` `<uuid:u>` `<path:p>`、正規表現の名前付きグループ | `{pk}` + 型注釈(正規表現の制約は外し警告) |
| `request.GET/POST/COOKIES/META/headers`, `getlist` | `Query` / `Form` / `Cookie` / `Header` |
| `JsonResponse`, `HttpResponse`, `HttpResponseRedirect`, `HttpResponseNotFound` 他 | dict / `JSONResponse` / `HTMLResponse` / `RedirectResponse` |
| `raise Http404 / PermissionDenied` | `HTTPException` |
| `@require_GET/POST/http_methods`, `request.method == "POST"` | ルートの HTTP メソッド / route methods |
| `@csrf_exempt` 等 | 削除 / dropped |
| `@app.teardown_request` / `teardown_appcontext` | ミドルウェアの `finally` / middleware `finally` block |
| `@app.before_first_request` | `@app.on_event("startup")` |
| Flask-SQLAlchemy (`db.Model`, `db.session`, `Model.query`, `create_all`, `get_or_404`) | 小さなSQLAlchemy互換層(リクエスト単位のセッション) / a small SQLAlchemy shim (per-request session) |
| Flask-Login (`LoginManager`, `UserMixin`, `login_user`, `logout_user`, `current_user`, `login_required`) | `request.session` ベースの互換層 / a session based shim |
| `app.config[...]` / `with app.app_context():` | `app.config = {}` / 本体を展開 / body inlined |
| Flask `session` / `g` | `request.session` (SessionMiddleware, secret from env `SECRET_KEY`, needs `itsdangerous`) / `request.state` |
| `View` サブクラス + `as_view()` (`get`/`post`/`put`/`patch`/`delete`) | メソッドごとのルート関数 `Class_get` ... / one route function per method |

## 変換しないもの(警告で報告) / Not converted (reported)
ORM(複雑な Django models)、Djangoのテンプレート(`render`)、Django の `View` 以外のクラスベースビュー(`TemplateView` 等)(DRF の `@action`・`generics` など)、各種 Flask 拡張(`flask_restful` など、手順を警告に表示)。

## バージョン / Versions (2026-11-17)
- **変換前(Flask/Django)のバージョンは自動判定**: `requirements*.txt` / `pyproject.toml` / `setup.py` / `Pipfile` のピン、無ければコード内の特徴(`before_first_request`、`django.conf.urls.url` など)、最後に実行環境の版。結果は `CONVERSION_REPORT.md` と `convert --json` の `detected` に出ます。
- **変換後のFastAPIのバージョンは指定可能**: `--fastapi-version 0.100.0`(VS Code拡張は設定 `tofastapi.fastapiVersion`)。指定なしは最新。古い版を指定すると `TemplateResponse(name, {"request": request, ...})` の旧形式になり、`requirements.txt` に `fastapi==指定版` を書き出します。
- **Source (Flask/Django) versions are detected automatically** from pins in requirements/pyproject/setup/Pipfile, then code patterns, then the installed version; shown in `CONVERSION_REPORT.md` and in `convert --json` (`detected`).
- **Target FastAPI version is selectable**: `--fastapi-version 0.100.0` (VS Code setting `tofastapi.fastapiVersion`); default = latest. Older targets get the old `TemplateResponse(name, {"request": request, ...})` form and a pinned `requirements.txt`.

## 互換性の注意 / Behaviour differences (documented, tested)
- 検証エラー: FastAPI は **422**(Flask/Django の手書き検証や型変換失敗は 400/404)。`<int:id>` に数字以外が来たとき Flask は 404、FastAPI は 422。
- リクエスト値は文字列のまま(`request.args.get("n", 10)` は `str`)。`type=int` のときだけ型付き。Django の `re_path` グループは `str`。
- `jsonify` と dict 返却は JSON。文字列返却は `HTMLResponse`(Flask と同じ text/html)。
- 末尾スラッシュ: 宣言どおり。FastAPI は不一致を 307 でリダイレクト(Flask は 308、Django は 301)。

テストは **Flask / Django の元アプリと変換後の FastAPI アプリへ同じリクエストを投げて、ステータスと本文を比較**する差分テスト(`tests/`)。 / Tests send identical requests to the original Flask/Django app and the converted FastAPI app and compare status and body.

## 開発 / Development
```
bash setup-wsl.sh        # WSL: uv で検証用 venv を作成 / creates a test venv
bash run-tests.sh        # pytest
```
CI は Ubuntu / Windows / macOS × Python 3.10・3.12・3.13。 / ライセンス: MIT

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

## 2FastAPI - 多言語の説明 / Multilingual description (13 languages)

公開ページ / Pages: https://easy-web.tokyo/2FastAPI ・ https://easy-web.tokyo/2FastAPI/demo (ダウンロード専用 / download-only)

- **日本語**: FlaskとDjangoのプロジェクトをFastAPI(MFastAPI互換)へ変換するツール。VS Code拡張版は 2FastAPI-VSC。
- **English**: A tool that converts Flask and Django projects to FastAPI (MFastAPI-compatible). The VS Code extension is 2FastAPI-VSC.
- **中文(简体)**: 将 Flask 和 Django 项目转换为 FastAPI(兼容 MFastAPI)的工具。VS Code 扩展版为 2FastAPI-VSC。
- **中文(台灣・繁體)**: 將 Flask 與 Django 專案轉換為 FastAPI(相容 MFastAPI)的工具。VS Code 擴充功能版為 2FastAPI-VSC。
- **한국어**: Flask와 Django 프로젝트를 FastAPI(MFastAPI 호환)로 변환하는 도구입니다. VS Code 확장 버전은 2FastAPI-VSC입니다.
- **Italiano**: Uno strumento che converte progetti Flask e Django in FastAPI (compatibile con MFastAPI). L'estensione per VS Code è 2FastAPI-VSC.
- **Français**: Un outil qui convertit des projets Flask et Django en FastAPI (compatible MFastAPI). L'extension VS Code s'appelle 2FastAPI-VSC.
- **Deutsch**: Ein Werkzeug, das Flask- und Django-Projekte in FastAPI (MFastAPI-kompatibel) umwandelt. Die VS-Code-Erweiterung heißt 2FastAPI-VSC.
- **Русский**: Инструмент, преобразующий проекты Flask и Django в FastAPI (совместимо с MFastAPI). Расширение для VS Code называется 2FastAPI-VSC.
- **Українська**: Інструмент, що перетворює проєкти Flask і Django на FastAPI (сумісно з MFastAPI). Розширення для VS Code називається 2FastAPI-VSC.
- **فارسی (ایران)**: ابزاری که پروژه‌های Flask و Django را به FastAPI (سازگار با MFastAPI) تبدیل می‌کند. افزونهٔ VS Code با نام 2FastAPI-VSC موجود است.
- **العربية**: أداة تحوّل مشاريع Flask وDjango إلى FastAPI (متوافق مع MFastAPI). إضافة VS Code اسمها 2FastAPI-VSC.
- **עברית (ישראל)**: כלי שממיר פרויקטים של Flask ו-Django ל-FastAPI (תואם MFastAPI). תוסף VS Code נקרא 2FastAPI-VSC.

Download: https://github.com/aon-co-jp/2FastAPI/releases/latest

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
