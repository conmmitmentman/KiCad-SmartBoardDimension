# スマート基板寸法（KiCad-SmartBoardDimension）

**KiCad 10.0.7 の PCB エディタで、寸法の数字をクリックして基板外形を数値・計算式で変更する非公式ネイティブ版**です。KiCad 本体のソースに機能を追加し、ビルドして使用します。

> [!IMPORTANT]
> **2026年11月10日現在、一般向け Windows インストーラー（`Install.exe`）とコンパイル済みアプリは未公開です。** 公開中の **Source v1.0.2** はソース配布です。ZIP を展開するだけでは動作せず、KiCad 本体のソースへのパッチ適用とビルドが必要です。
>
> 現在使うには **KiCad 10.0.7 のソースにパッチを適用し、Windows でビルド**してください。通常版 KiCad にそのまま機能を追加するインストーラーは提供していません。

## 1. できること

| 対象 | 操作 |
| --- | --- |
| `Edge.Cuts` の水平・垂直な長方形 | 寸法値から幅・高さを変更 |
| `Edge.Cuts` の円 | 中心を固定したまま半径・直径を変更 |
| 数式入力 | `56`、`2*(30+5)`、`1in+5mm` など |
| 数字の直接操作 | 寸法の数字をクリック → 入力 → `Enter` で確定、`Esc` で取消 |
| Undo / Redo | `Ctrl+Z` / `Ctrl+Y` |
| 点への吸着 | KiCad 標準のオブジェクトスナップを利用 |

※ Fusion 360 のような汎用の幾何拘束スケッチ機能ではありません。対応条件は「[7. 対応範囲と制約](#7-対応範囲と制約)」を参照してください。

## 2. ダウンロード：どのファイルを選ぶ？

**現在公開中：ネイティブ Source v1.0.2**

- [リリースページ](https://github.com/conmmitmentman/KiCad-SmartBoardDimension/releases/tag/native-source-v1.0.2)
- [ソース ZIP（KiCad10_NativeDrivingDimension_Source_v1.0.2.zip）](https://github.com/conmmitmentman/KiCad-SmartBoardDimension/releases/download/native-source-v1.0.2/KiCad10_NativeDrivingDimension_Source_v1.0.2.zip)
- [ZIP の SHA256 チェックサム](https://github.com/conmmitmentman/KiCad-SmartBoardDimension/releases/download/native-source-v1.0.2/KiCad10_NativeDrivingDimension_Source_v1.0.2.zip.sha256)

**この ZIP には `Install.exe` は含まれていません。** 現在の導入方法は次の「3. Windows でソースから導入する」です。

開発中の Windows 簡単導入方式については [native/INSTALL_JA.md](INSTALL_JA.md) に記録しています。開発用ランチャーのソースがあることと、一般向け Windows バイナリが公開されていることは別です。

### ダウンロードした ZIP が正しいか確認する（任意）

ZIP と `.zip.sha256` ファイルを同じフォルダーに保存し、PowerShell で以下を実行します。

```powershell
Set-Location "$env:USERPROFILE\Downloads"
Get-FileHash ".\KiCad10_NativeDrivingDimension_Source_v1.0.2.zip" -Algorithm SHA256
Get-Content ".\KiCad10_NativeDrivingDimension_Source_v1.0.2.zip.sha256"
```

表示された SHA256 の値と、チェックサムファイル冒頭の文字列が一致することを確認してください。ファイルを別の場所に保存した場合はパスを読み替えてください。

## 3. Windows でソースから導入する（現在利用できる方法）

以下は **`C:\dev` を作業フォルダーとする例**です。C++ のビルド環境が必要です。わからない箇所を飛ばすと起動できないため、順番に確認してください。

### STEP 1：必要なソフトを準備

| ソフト | 用途 |
| --- | --- |
| 64-bit Windows | 実行環境 |
| Visual Studio 2022（「C++ によるデスクトップ開発」＋ Windows SDK） | MSVC で KiCad をビルド |
| Git | GitHub / KiCad ソースの取得 |
| Python 3 | ソースパッチの適用・テスト |
| CMake、Ninja、SWIG、vcpkg など | KiCad ビルドの依存ツール |
| Developer PowerShell for VS 2022 | C++ コンパイラーを認識するターミナル |

**重要：まず [KiCad 公式 Windows MSVC ビルドガイド](https://dev-docs.kicad.org/en/build/windows-msvc/) に沿って、依存ライブラリ・vcpkg・CMake プリセットの設定を完了してください。** このリポジトリだけで、KiCad の全ビルド依存関係を自動セットアップすることはできません。

本プロジェクトの検証記録の環境は、Visual Studio 2022、MSVC 14.44.35207、CMake 3.31.10、PowerShell 7.5.4、SWIG 4.3.1、vcpkg `66c0373dc7fca549e5803087b9487edfe3aca0a1` です。他の環境での再現は未保証です。

> [!NOTE]
> 通常版 KiCad を削除する必要はありません。パッチ版は別フォルダーでビルド・起動します。

### STEP 2：リポジトリと KiCad 10.0.7 のソースを取得

**Developer PowerShell for VS 2022** を起動し、順に実行します。

```powershell
New-Item -ItemType Directory -Force C:\dev | Out-Null
Set-Location C:\dev

# このプロジェクトのソースを取得
git clone https://github.com/conmmitmentman/KiCad-SmartBoardDimension.git SmartBoardDimension

# 対応バージョンの KiCad 本体ソースを取得
git clone --depth 1 --branch 10.0.7 https://github.com/KiCad/kicad-source-mirror.git kicad
```

取得後の主要ファイル：

```text
C:\dev\
├─ SmartBoardDimension\
│  ├─ README.md
│  └─ native\
│     ├─ native_patch\
│     │  └─ apply_native_patch.py
│     ├─ examples\
│     │  └─ circle.kicad_pcb
│     └─ launch_windows.ps1
└─ kicad\
   └─ pcbnew\ ...
```

Git を使用せず、上記の Source ZIP を展開した場合は、コマンド中の `C:\dev\SmartBoardDimension` を実際の展開先に読み替えます。その場合も **KiCad 10.0.7 本体のソースは別途必要**です。

### STEP 3：パッチを適用できるか事前確認

まず `--dry-run` でソースとの一致をチェックします。この段階ではファイルを書き換えません。

```powershell
Set-Location C:\dev
py -3 .\SmartBoardDimension\native\native_patch\apply_native_patch.py C:\dev\kicad --with-tests --dry-run
```

成功時のメッセージ例：

```text
OK: KiCad dialog and canvas anchors match; no files changed.
```

失敗したら次に進まず、KiCad のタグが `10.0.7` か、パスが正しいか、すでに変更済みのソースではないかを確認してください。

### STEP 4：実際にパッチを適用

```powershell
py -3 .\SmartBoardDimension\native\native_patch\apply_native_patch.py C:\dev\kicad --with-tests
```

既存の編集対象ファイルの原本は `.smartboard-original` を付けてバックアップされ、C++ の追加ファイルとテストが登録されます。

**同じソースに2回適用しないでください。** 二重適用・バックアップの重複・想定外のソースに対しては停止する設計です。インストール済みの通常版 KiCad にこの Python スクリプトを実行しても、機能は追加されません。

### STEP 5：KiCad を C++ でビルド

**KiCad 公式ビルドガイドに従った MSVC / vcpkg / CMake プリセットの準備が完了してから**実行します。

```powershell
Set-Location C:\dev\kicad

# 設定済みのプリセットを確認
cmake --list-presets

# 検証時に使用したプリセットの例
cmake --preset msvc-win64-release -DKICAD_BUILD_QA_TESTS=ON
cmake --build --preset win64-release --target pcbnew qa_pcbnew bitmap_archive_build --parallel 4
```

上記プリセット名は本プロジェクトの検証環境で使われたものです。`cmake --list-presets` に表示されない場合は、KiCad 公式ガイドに従ってプリセットを設定してください。使用するビルド環境によって、ビルドディレクトリやプリセット名は変わる可能性があります。

成功後、次のファイルが生成されていることを確認します（上記ディレクトリ構成の場合）。

```text
C:\dev\kicad\build\msvc-win64-release\pcbnew\pcbnew.exe
C:\dev\kicad\build\msvc-win64-release\pcbnew\_pcbnew.dll
```

**通常版 KiCad の `Program Files` 内のファイルに上書きしないでください。**

### STEP 6：専用スクリプトで PCB エディタを起動

日常の起動には、ビルド完了後に **[初回設定](INSTALL_JA.md)** を一度行う方法を推奨します。次回から専用アイコンで起動でき、以下のコマンドを毎回入力する必要はありません。以下は開発者が直接起動する場合の方法です。

```powershell
Set-Location C:\dev\SmartBoardDimension

.\native\launch_windows.ps1 `
  -BuildDirectory "C:\dev\kicad\build\msvc-win64-release" `
  -Board ".\native\examples\circle.kicad_pcb"
```

サンプル基板が開けば起動確認は成功です。このスクリプトはビルドした KiCad の DLL / Python パスを設定し、通常の KiCad と別の設定フォルダーを使用します。

PowerShell のスクリプト実行が制限されている場合は、**入手元とスクリプト内容を確認したうえで**、今回のプロセスに限り次を利用できます。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\native\launch_windows.ps1 -BuildDirectory "C:\dev\kicad\build\msvc-win64-release" -Board ".\native\examples\circle.kicad_pcb"
```

開発版の設定保存先は既定で `%LOCALAPPDATA%\SmartBoardDimension\native-1.0` です。`pcbnew.exe` を直接ダブルクリックすると DLL / Python の検索パス不足で起動できない場合があるため、起動スクリプトを使用してください。

## 4. インストール成功を確認する（円のサンプル）

1. 起動スクリプトで `native/examples/circle.kicad_pcb` を開きます。サンプルをコピーするか別名保存してから編集してください。
2. `Edge.Cuts` に円と半径・直径の寸法があることを確認します。
3. **半径寸法の数字**をクリックします。
4. 入力欄で `2*15` を入力し、**Enter** で確定します。
5. 半径が **28 → 30 mm**、直径が **56 → 60 mm** となること、円の中心が動かないことを確認します。
6. **Ctrl+Z** で戻し、**Ctrl+Y** でやり直せることを確認します。

**通常版 KiCad でこの基板を開いても、寸法の数字から外形を変更する機能は使えません。** ビルドしたパッチ版を起動していることを確認してください。

## 5. 使い方：長方形と円

### 長方形の幅・高さを変更

1. `Edge.Cuts` に軸と平行な長方形を描きます（長方形1個、または端点が正確に接続した直線4本）。
2. KiCad 標準の **整列寸法**または **直交寸法**で、変更したい辺の両端の角を指定します。
3. 寸法の配置を終え、**数字**をクリックします。
4. 例：`2*(30+5)` と入力して Enter を押すと **70 mm** を指定できます。
5. 外形と対応する寸法が更新されたことを確認し、保存します。

横寸法では **左辺を固定して右辺を**、縦寸法では **上辺を固定して下辺を**移動します。角に接続した他の対応寸法の端点も更新します。

### 円の半径・直径を変更

1. `Edge.Cuts` に円を1個作成します。
2. **半径**：標準の「半径寸法」で **円中心 → 円周上の点**の順に指定します。
3. **直径**：標準の整列寸法で、円中心を通る向かい合った2点を指定します（上下・左右なら直交寸法も利用可能）。
4. 配置完了後、寸法の **数字**をクリックします。
5. 入力欄の「半径」または「直径」を確認して数値や計算式を入力し、Enter で確定します。

円の **中心は固定**されます。中心を通らない弦の寸法は外形変更には使えません。

### 点への吸着（スナップ）が効かない場合

`User.Drawings` レイヤーの寸法端点を `Edge.Cuts` の角・円中心・円周へ吸着させる場合：

- KiCad のオブジェクトスナップ対象を **「表示中の全レイヤー」** にします。
- キャンバス上で **Shift+S** を押して設定を切り替えます。
- 寸法点を指定する際に **Shift を押し続けないでください**（スナップが一時無効になります）。
- 寸法の端点が外形の対象点と一致していないと、編集が拒否される場合があります。

なお、通常の寸法プロパティ（`E`）から **「この寸法値で基板外形を変更（mm）」** を使う操作も実装されています。

## 6. 数式とショートカット

| 入力・操作 | 結果 |
| --- | --- |
| `56` | 56 mm |
| `2*(30+5)` | 70 mm |
| `1in+5mm` | 30.4 mm |
| `Enter` | 入力を確定 |
| `Esc` | 入力を取り消す |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+S` | 保存 |
| `Shift+S` | オブジェクトスナップ対象を切替 |

単位省略時は **mm** です。`1/0` などの不正な計算式は拒否します。

## 7. 対応範囲と制約

- **対象バージョン**：KiCad **10.0.7** の公式ソース（ベースコミット `69cafb907ebc09e7722a2a464b1d466fc2e3608d`）。
- **寸法値**：0.01 ～ 1000 mm。外形の変更前の幅・高さ、関連寸法の長さ、座標にも上限があります（詳細は [native/README.md](README.md)）。
- **対応外形**：軸に平行な長方形、単独の円。
- **未対応**：斜めの輪郭、円弧、穴、複数輪郭、開いた線分、汎用の拘束スケッチ。
- **寸法の関連付け**：端点が角・円中心・円周に一致するかで都度判定します。永続的な拘束ソルバーではありません。
- **部品・パッド・配線・ゾーン**：寸法変更に連動して移動する機能はありません。
- **ロック**：外形や移動対象の寸法がロックされている場合は変更を拒否します。
- **検証済み**：Windows のサンプル操作、数式入力、Undo/Redo、保存・再起動後の再編集と回帰テスト。
- **未検証**：他 OS・他 KiCad バージョン・複雑な実基板・開発環境のない別 PC への一般導入。

実基板へ利用する場合は **編集前のバックアップ**を取り、編集後も `Edge.Cuts` の接続と寸法を確認してください。

## 8. よくあるエラーと対処

| 症状 | 確認すること |
| --- | --- |
| Source ZIP に `Install.exe` がない | 正常です。現時点ではソース配布のみです。 |
| `git` / `py` コマンドが見つからない | Git / Python がインストール済みか確認し、ターミナルを開き直します。 |
| `Expected one occurrence` | KiCad ソースのタグが 10.0.7 か、ファイルが変更済みでないか確認します。 |
| `Already modified` / `Backup already exists` | 二重適用の防止です。クリーンな KiCad 10.0.7 ソースでやり直します。 |
| `cmake --preset` が失敗 | 公式 MSVC ビルドガイドの依存関係とプリセット設定を見直します。 |
| `pcbnew.exe` / `_pcbnew.dll` がない | ビルドが完了していません。ビルドログを確認します。 |
| `Missing build output` | `-BuildDirectory`、成果物、vcpkg の Python の配置を確認します。 |
| スクリプト実行が禁止される | STEP 6 の一時的な実行方法を確認します。 |
| 数字をクリックしても編集できない | パッチ版を起動しているか、寸法が対応する外形の点に接続しているか確認します。 |
| 点に吸着しない | Shift+S で「表示中の全レイヤー」へのスナップを設定します。 |
| 外形を変更できない | 対応形状・ロック状態・端点一致・入力範囲を確認します。 |

解決しない場合は [Issues](https://github.com/conmmitmentman/KiCad-SmartBoardDimension/issues) に、OS・使用した KiCad ソースのバージョン・コマンド・エラー全文・再現手順を記載してください。個人情報や API トークンは掲載しないでください。

## 9. 更新方法

### ソースから導入した場合

1. PCB ファイルをバックアップし、パッチ版 KiCad を終了します。
2. `C:\dev\SmartBoardDimension` で `git pull` し、このリポジトリの最新版を取得します。
3. **クリーンな KiCad 10.0.7 のソース**を別途用意します。既にパッチ済みのソースに重ねて適用しないでください。
4. STEP 3 ～ 6 の **dry-run → パッチ → 再ビルド → 起動確認**を行います。

**現在のソース版に「更新」ボタン1つでアプリ本体を更新する仕組みはありません。**

### 将来の Windows 簡単導入版（まだ未公開）

開発中の配布方式では、完成した Windows パッケージ内の `Install.exe` と `app` フォルダーを使う想定です。ユーザー別インストール先は `%LOCALAPPDATA%\Programs\SmartBoardDimension`、設定・サンプルは `%LOCALAPPDATA%\SmartBoardDimension` を想定しています。

ただし **現在の公開 Source ZIP では実行できません**。詳細は [導入方式の開発状況](INSTALL_JA.md) を参照してください。

## 10. アンインストール方法

### ソース版

1. パッチ版 PCB エディタを終了します。
2. 自分で編集した `.kicad_pcb` ファイルをバックアップします。
3. 作業用の `C:\dev\kicad` と `C:\dev\SmartBoardDimension` に他の必要なファイルがないことを確認したうえで、不要なら削除します。
4. 専用設定も消したい場合のみ `%LOCALAPPDATA%\SmartBoardDimension\native-1.0` を削除します。

**通常版 KiCad をアンインストールする必要はありません。**

### 将来の Windows 簡単導入版

公開後は該当バージョンのアンインストール案内に従ってください。開発中の想定では、専用ショートカット、ユーザー別アプリ配置先、必要に応じて専用設定を削除する方式です。**通常版 KiCad と制作した基板ファイルを誤って削除しないでください。**

## 11. 開発者向けのテスト

パッチ生成の Python テスト：

```powershell
Set-Location C:\dev\SmartBoardDimension
py -3 -m unittest discover -s native/tests -v
```

KiCad を QA 有効でビルドした後：

```powershell
Set-Location C:\dev\kicad
$env:BOOST_TEST_RUN_FILTERS = 'SmartBoardDrivingDimensions,SmartBoardDrivingCircles,BoardCommit'
ctest --preset win64-release -R '^qa_pcbnew$' --output-on-failure
```

Windows ランチャーのテストは `native/windows/`、配布物の生成処理は `tools/` に収録しています。テスト済みの機能範囲と公開配布の完成状況は区別してください。

## 12. リポジトリ内の資料

| ファイル・フォルダー | 内容 |
| --- | --- |
| [native/README.md](README.md) | 機能仕様、操作、制約、ビルドと検証記録 |
| [native/INSTALL_JA.md](INSTALL_JA.md) | Windows インストーラー方式の開発状況 |
| [native/native_patch/](native_patch/) | KiCad 10.0.7 用の C++ パッチと適用スクリプト |
| [native/examples/](examples/) | 動作確認用 PCB サンプル |
| [native/launch_windows.ps1](launch_windows.ps1) | ビルド版を起動する PowerShell スクリプト |
| [native/windows/](windows/) | Windows ランチャーと検証コード |
| [tools/（GitHub）](https://github.com/conmmitmentman/KiCad-SmartBoardDimension/tree/main/tools) | 開発者向け配布生成処理 |
| [CHANGELOG.md](../CHANGELOG.md) | 更新履歴 |
| [ATTRIBUTION.md](../ATTRIBUTION.md) | 参考元と来歴 |

## ライセンスと非公式プロジェクトについて

本プロジェクトは **KiCad 公式の製品・配布物ではありません**。操作感は [SolidCraft](https://github.com/tangency-labs/solidcraft) を参考にした独自実装です。SolidCraft のコード・画像・拘束ソルバーは取り込んでいません。

C++ 追加コードは [GPL-3.0-or-later](LICENSE_GPLv3.txt)。Windows ランチャー等のその他のファイルは、それぞれの表示と [LICENSE](../LICENSE) に従います。元の KiCad ソースや各依存関係には、それぞれのライセンスが適用されます。

