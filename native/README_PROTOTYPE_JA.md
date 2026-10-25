# KiCad 10 ネイティブ駆動寸法 — 実験的なC++ソースパッチ

**目的：** SolidCraft のお手本動画のように、**寸法値によって `Edge.Cuts` の長方形基板外形そのものを変更する**ことです。これは既存のKiCad 10標準「寸法」ツールに統合する方向の、**ビルド前・実機未検証の試作コード**です。

## 動画を踏まえた目標操作

1. PCBエディターの `Edge.Cuts` で長方形を作る（KiCadの矩形1つ、または直線4本）。
2. 右側の標準「整列寸法」を起動し、左上の角と右上の角をクリックする。**KiCad標準のスナップが働き、角に吸着します**。寸法線を置く。角に吸着しないときは、`Edge.Cuts` の表示と「編集オプション → グラフィックにスナップ」を確認し、`Shift+S` で全表示レイヤーへのスナップを選びます。
3. 寸法を選んで **E** キーを押す（KiCad標準の「寸法プロパティ」）。
4. 新設の `この寸法値で基板外形を変更（mm）` をオンにし、数値入力欄に `56` と入力して OK。
5. 幅が **56 mm** になるよう右側の基板外形が移動。左辺は固定です。
6. 高さ寸法で同様に `23` と入れると下辺が移動。上辺は固定です。

**外部プラグインメニューは使いません。** 既存の寸法ツール・寸法プロパティ画面から行います。寸法作成時の端点吸着はKiCadの標準機能を利用します。

**現在の未実装：** 寸法値を図面上でクリックしてその場で入力する **インライン編集ポップアップ**、任意の多角形・円弧の拘束ソルバー、自動で他のジオメトリ（部品、銅箔、配線、ゾーン）まで移動させる機能。寸法プロパティ `E` を経由します。動画の操作を完全再現する完成版ではありません。

## 対応する外形と安全チェック

- `Edge.Cuts` の **軸平行な矩形**、もしくは**継ぎ目が合致した4つの線分**のみ。
- 寸法の両端が対象長方形の **隣接する2頂点（誤差0.01 mm以内）** を指す場合だけ変更。
- 横寸法なら左辺を固定して右辺を更新。縦寸法なら上辺を固定して下辺を更新。
- 有効長は `0 < L <= 1000 mm`。長方形の不成立、穴・円弧・複数輪郭は拒否。
- 同じ四隅を参照する既存の整列・直交寸法も位置を追随（幾何学的な近さを使う簡易追随）。
- `BOARD_COMMIT` により、形状と寸法の変更は同じUndo履歴に統合するよう設計。
- **部品、パッド、配線、銅箔ゾーンは動きません。** 適用後は保存前に外形・DRCを必ず確認。
- チェックボックスの初期値はオフ。通常の寸法注記には一切作用しないように設計。

## 内容

```
KiCad10_NativeDrivingDimension/
├── README_日本語.md
├── native_patch/
│   ├── apply_native_patch.py                 # ソース改変＋バックアップ
│   └── smart_board_driving_dimension_impl.h  # 矩形拘束ロジック（C++）
└── tests/
    └── test_patch.py                        # スクリプトの単体テスト
```

## Windowsでの利用方法（ソースビルドが必要）

これは既存の KiCad 10 インストール先に ZIP をコピーするタイプのプラグインではありません。**KiCad本体を独自にビルドするためのソース変更パッチ**です。Windows上でKiCadをビルドするには Visual Studio、CMake、vcpkg などが必要です。

### 1. KiCad 10 のソースを用意

PowerShellまたはGit Bashの一例：

```powershell
git clone --branch 10.0 --depth 1 https://github.com/KiCad/kicad-source-mirror.git C:\dev\kicad-10
```

GitHubミラーは読み取り専用です。公式本体の更新情報やバージョンに注意してください。

### 2. 試作パッチを適用

```powershell
py -3 .\native_patch\apply_native_patch.py C:\dev\kicad-10 --dry-run
py -3 .\native_patch\apply_native_patch.py C:\dev\kicad-10
```

指定されたKiCadソース側の以下のファイルが変わります：

- `pcbnew/dialogs/dialog_dimension_properties.h`
- `pcbnew/dialogs/dialog_dimension_properties.cpp`
- 同じ場所に `smart_board_driving_dimension_impl.h` を新規追加

元の `.h`/`.cpp` はそれぞれ拡張子 `.smartboard-original` で保存されます。

### 3. ソースビルド

KiCad公式の Windows / Visual Studio ビルドガイドを読み、**「Building the 10.0 stable branch」**の手順に従ってビルドしてください。

https://dev-docs.kicad.org/en/build/windows-msvc/

**このZIPにビルド済みのexeやインストーラーは含まれません。** 現時点でWindows/KiCad 10 GUI実機・C++コンパイルの確認は行っていません。必要なライブラリがない本環境でのコンパイル成功を装うことはしません。

### 4. 復元・アンインストール

この機能を入れた独自KiCadビルドを使用中ならそのビルドの使用を停止し、元の公式KiCadを使用してください。ソースパッチのみ戻す場合、`.smartboard-original` の2ファイルをそれぞれ元の名前に戻し、追加した `.h` を削除して再ビルドします。

## 検証方法

```powershell
py -3 -m unittest discover -s tests -v
```

このテストは改変スクリプトの条件、バックアップを検証する**Pythonテストだけ**で、C++の機能・バイナリ動作保証ではありません。

## 技術上の制約と次段階

公式KiCadは寸法を計測用のグラフィックと定義し、寸法値のOverrideも表示文字だけを変えます。元のPython Action Pluginは独自ダイアログから外形を編集できますが、標準寸法のマウスイベントや内部値編集を置き換える公開APIはありません。したがって、ユーザー希望の「寸法機能から直接操作する」設計では C++ 本体側の統合が必要です。

インライン編集や連続したパラメトリック拘束を実現するには、寸法ツールの `DRAWING_TOOL::DrawDimension`、選択/ダブルクリック時のイベント処理、駆動寸法とエッジの関連をPCBファイルへ保存するモデル変更、制約解法、およびUndo/DRC/描画更新の統合が今後必要です。

- KiCad 10日本語PCBマニュアル: https://docs.kicad.org/10.0/ja/pcbnew/pcbnew.html
- KiCad公式ビルド: https://dev-docs.kicad.org/en/build/windows-msvc/
- KiCadソース参照: https://github.com/KiCad/kicad-source-mirror/tree/10.0
- 参考にしたSolidCraft: https://github.com/tangency-labs/solidcraft

この試作は SolidCraft のコードを移植・コピーしていません。振る舞いを参考にした別実装です。

## ライセンス

KiCadに組み込むC++追加コードは GPL-3.0-or-later として提供。標準KiCadライセンスに従って改変版ソースの配布要件を満たしてください。付属Pythonパッチ適用スクリプトはMITライセンスとして提供します。
