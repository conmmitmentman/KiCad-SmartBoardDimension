# Rust版の構成とビルド

## 変更した範囲

- `rust-core/`：数式・数値計算と寸法の幾何処理をRustの静的ライブラリにしました。
- `rust-launcher/`：日本語の起動画面、配布物の検証、導入・修復、ビルド先の登録、専用ショートカットをRustで実装しました。C#やPowerShellを呼び出して動かす構成ではありません。
- `native_patch/`：KiCadの画面・基板オブジェクト・Undoと接続するC++部分を残し、RustをC ABIで呼び出します。

**KiCad本体はC++です。この変更はKiCad全体をRustへ書き直したものではありません。** パッチ適用と配布フォルダー生成の補助スクリプトはPython、従来の起動・初回設定スクリプトは互換用として残ります。

## 最初に必要な環境

Windows x64、Rust 1.88以降（MSVCツールチェーン）、Visual Studio 2022のC++開発環境が必要です。KiCad本体のビルドには別途CMake、Ninja、SWIG、vcpkg等も必要です。KiCadの基準版は10.0.7です。

**Source v1.0.2以前のビルド説明だけでは、このRust版はビルドできません。** 現在のリポジトリ一式を使い、Rustを導入して、次の新しいパッチとCMake連携を使用してください。旧ソースZIPと現在のパッチを混在させないでください。

## Rust部分をビルドする

リポジトリのルートで実行します。

```powershell
cargo test --workspace
cargo build --release -p sbd-rust-core
cargo build --release -p smartboard-launcher
```

Windowsでは `target/release/smartboard_dimension_core.lib` と `target/release/smartboard-launcher.exe` が生成されます。GUIはWindows専用です。Rustコアは静的ライブラリなので、ランチャーだけを置き換えてもKiCad本体の寸法計算は更新されません。

## KiCadへ組み込む

KiCad 10.0.7の**未変更のソース**を別フォルダーへ取得し、Developer PowerShellで `cargo --version` が成功する状態にします。旧パッチへ重ねて適用しないでください。

```powershell
python native/native_patch/apply_native_patch.py C:\dev\kicad --with-tests --dry-run
python native/native_patch/apply_native_patch.py C:\dev\kicad --with-tests
```

パッチはRustコアをKiCadソースへ配置し、最上位CMakeへ `smartboard-rust-core/kicad.cmake` を登録します。KiCadのPCBターゲットがRust静的ライブラリをビルド・リンクする構成です。CargoがPATHにない場合は構成時に停止します。

[KiCad公式Windowsビルド手順](https://dev-docs.kicad.org/en/build/windows-msvc/)に従い依存関係とプリセットを用意した後、構成・ビルドします。以下のプリセット名は例です。

```powershell
cmake --preset msvc-win64-release -DKICAD_BUILD_QA_TESTS=ON
cmake --build --preset win64-release --target pcbnew qa_pcbnew bitmap_archive_build --parallel 4
```

この段階のコマンドはKiCadソースのルートで実行します。**Rustへ移行した今回のKiCad全体の再ビルド・実画面動作は未検証です。** 以前のC++版のGUI検証記録を、そのままRust統合版の成功記録として扱うことはできません。

## 起動の登録は1回だけ

`smartboard-launcher.exe` を開き、「ネイティブ版のビルド先を登録／変更」でビルドフォルダーを選びます。通常版やパッチ適用前の本体は、バイナリ内の寸法機能の識別文字列を確認して拒否します。この検査はデジタル署名ではありません。

起動用ファイルと登録先をユーザー用フォルダーに保存し、デスクトップ／スタートメニューへ **スマート基板寸法（ネイティブ版）** を作成します。次回はアイコンを開くだけです。ビルドフォルダー自体は移動・削除せず残してください。

新規基板、保存済み基板、円サンプルをGUIから選べます。再起動ごとにビルドやコマンド入力を行う必要はありません。既存設定と編集済みサンプルは保持します。画面にはWindows標準のコントロールを使用し、PCBエディタの起動後はランチャーが終了します。

数式評価は入力を直接参照するか、最大256バイトの固定領域で全角文字を変換します。長方形の外形検査に使う点と辺も固定長にしました。Windows配布ファイルのハッシュは64 KiBずつ読み取ります。PCBエディタ本体を含むメモリ使用量は実機未計測です。

### ランチャーのメモリ測定

2026-11-18、同じWindows PCで、旧Rustランチャー（egui/OpenGL）とWin32版を同じデバッグ構成で比較しました。一時フォルダーの空の配布構成でランチャーだけを起動し、入力待ちから1秒後のプロセスを3回測った中央値です。

| ランチャー単体 | 旧Rust版 | Win32版 |
| --- | ---: | ---: |
| ワーキングセット（物理メモリにある分） | 118.02 MiB | 11.86 MiB |
| プライベートメモリ（プロセス専用のコミット量） | 70.18 MiB | 1.72 MiB |
| 実行ファイルサイズ | 9.36 MiB | 1.08 MiB |

インストール処理中やPCBエディタのメモリ使用量は、この比較の対象外です。

## 開発者向けの配布フォルダー生成

検証済みのKiCad本体、標準KiCadの配布リソース、コンパイル済みRustランチャーを指定します。これは開発用処理で、一般ユーザーの導入操作ではありません。

```powershell
python tools/build_native_windows.py --build C:\dev\kicad\build\msvc-win64-release --stock "C:\Program Files\KiCad\10.0" --launcher target\release\smartboard-launcher.exe --output dist\native-windows
```

`--launcher` は省略時に `target/release/smartboard-launcher.exe` を使います。C#コンパイラーは呼び出しません。生成後の `Install.exe` はRust実装の導入画面です。**この処理によるKiCad本体の一般向けバイナリ公開は未実施です。** 対応ソース・依存物の表示、別PCでの導入検証と公開作業が残ります。

## 検証の境界

Rustのテストでは、数式・幾何、配布物の破損拒否、修復と復元、設定保持、機能識別、起動引数を検査します。人工基板とCMakeプロジェクトでC++からRustを呼び出し、円・長方形の寸法とロック時の挙動も確認しました。実際のKiCad本体のビルド・操作は未検証です。
