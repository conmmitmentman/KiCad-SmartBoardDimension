# PCB上で編集するネイティブ寸法（開発版）

KiCad 10.0.7 の標準PCBエディタに、寸法の数字をクリックして数値・計算式を入力する機能を追加するC++ソースパッチです。Pythonプラグインのインストーラーとは別のものです。

**Source Preview 1：WindowsでKiCad本体とQA実行ファイルのビルドに成功し、PCBエディタの起動を確認しました。追加したC++テスト8件と既存のBoardCommitテスト8件が成功しています。数字クリック・スナップ・Undo/Redoなどの画面操作は検証中です。** 配布ZIPはソースパッチで、コンパイル済みアプリやインストーラーを含みません。

## 実装した操作

1. `Edge.Cuts` に軸に平行な長方形を描きます。矩形1個、または端点が正確に接続した直線4本が対象です。
2. 標準の整列寸法または直交寸法で、長方形の隣り合う2つの角を指定します。角への吸着はKiCad標準のオブジェクトスナップを使います。
3. 配置を終え、寸法の数字をクリックします。近くに入力欄を表示する実装です。外部プラグインの起動操作はありません。
4. `56`、`2*(30+5)`、`1in+5mm` などを入力し、Enterで確定、Escで取り消します。単位を省略した値はmmです。
5. 横寸法は左辺を固定して右辺を、縦寸法は上辺を固定して下辺を移動します。他の整列・直交寸法も、四隅に合っている端点を更新します。四隅以外にある端点はその位置を保ちます。

通常の寸法プロパティ（E）にも「この寸法値で基板外形を変更（mm）」を追加します。数字以外の寸法線・ハンドルは標準の選択・編集操作に使えます。

## 対象と制約

- 入力できる長さは0.01～1000 mm、変更前の外形の幅・高さは0.01～2000 mm、座標は±2000 mm以内です。
- 円弧、斜めの外形、穴、複数輪郭、開いた線分には対応しません。
- 寸法と外形の関連は、寸法端点が四隅に一致するかで毎回判定します。許容差は最大0.01 mmで、小さな外形では縮小します。永続的な拘束ソルバーではありません。
- 外形の端点を別の操作で動かした場合、寸法端点を自動追従させる機能はありません。寸法端点を角に合わせ直してから寸法値を編集します。
- 部品、パッド、配線、ゾーンを移動・変形する機能はありません。
- ロックされた外形や、変更で動くロック寸法がある場合は変更を拒否します。
- 外形と寸法を同じ `BOARD_COMMIT` に登録します。Undo/Redoの画面上の検証は未実施です。

## ソースへの適用

対象は公式KiCadのタグ `10.0.7`、コミット `69cafb907ebc09e7722a2a464b1d466fc2e3608d` です。

```powershell
git clone --depth 1 --branch 10.0.7 https://github.com/KiCad/kicad-source-mirror.git C:\dev\kicad
python native/native_patch/apply_native_patch.py C:\dev\kicad --with-tests --dry-run
python native/native_patch/apply_native_patch.py C:\dev\kicad --with-tests
```

既存ファイルには `.smartboard-original` を付けてバックアップします。挿入位置の不一致、二重適用、既存バックアップがあれば停止します。`--dry-run` はファイルを書き換えません。コンパイル済みのKiCadへこのスクリプトを実行しても機能は追加されません。

ビルドは[KiCad公式Windows MSVC手順](https://dev-docs.kicad.org/en/build/windows-msvc/)に従います。今回の環境はVS 2022、MSVC 14.44.35207、CMake 3.31.10、PowerShell 7.5.4、SWIG 4.3.1、vcpkg `66c0373dc7fca549e5803087b9487edfe3aca0a1` です。QAテストを有効にしてビルドしてください。公式インストール先への上書きは行わず、別のビルドディレクトリで検証しています。

## テスト

```powershell
python -m unittest discover -s native/tests -v
# KiCadのQAビルド後：
qa_pcbnew.exe --run_test=SmartBoardDrivingDimensions --log_level=test_suite
```

- Pythonのパッチ生成テスト：6件成功（適用失敗時の復元を含む）。
- クリーンな10.0.7から生成した7ファイルと、ビルド対象の7ファイルが一致することを確認。
- C++回帰テスト8件成功：数式、形状と寸法の更新、片側だけ接続した寸法の追従、非接続寸法、ロック、逆順端点、座標上限、4線分の接続。既存のBoardCommitテスト8件も成功。
- WindowsでビルドしたPCBエディタの起動と、テスト基板・寸法の表示を確認。
- 画面操作：クリック編集、角への吸着、Undo/Redo、保存後の再編集は未検証。

## 来歴とライセンス

提供された `KiCad10_NativeDrivingDimension_Prototype.zip` を元に、10.0.7のAPIへの修正、数字クリックからの編集、数式評価、変更前の検証、テストを追加しました。受領時の説明は [README_PROTOTYPE_JA.md](README_PROTOTYPE_JA.md) に記録しています。現在の動作・検証状況は本書を参照してください。

操作の参考は [SolidCraft](https://github.com/tangency-labs/solidcraft) です。SolidCraftの実装コードや拘束ソルバーを組み込んでいません。

C++追加コードはGPL-3.0-or-later（[全文](LICENSE_GPLv3.txt)）。KiCad本体のライセンスは元のソースに従います。パッチ生成用Pythonの元のライセンスは [LICENSE_PYTHON.txt](LICENSE_PYTHON.txt) に収録しています。
