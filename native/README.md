# PCB上で編集するネイティブ寸法 — Source v1.0.0

KiCad 10.0.7 の標準PCBエディタに、寸法の数字をクリックして数値・計算式を入力する機能を追加するC++ソースパッチです。Pythonプラグインのインストーラーとは別のものです。

**KiCad 10.0.7向けの正式なソース配布版です。** Windowsでビルド・起動し、長方形と円の数字クリック、数式入力、Undo/Redoを確認しました。配布ZIPはソースパッチで、コンパイル済みアプリやインストーラーを含みません。既存のSource Preview 1を引き継ぎ、円対応と操作改善を追加しています。

## 実装した操作

1. `Edge.Cuts` に軸に平行な長方形を描きます。矩形1個、または端点が正確に接続した直線4本が対象です。
2. 標準の整列寸法または直交寸法で、長方形の隣り合う2つの角を指定します。角への吸着はKiCad標準のオブジェクトスナップを使います。
3. 配置を終え、寸法の数字をクリックします。近くに入力欄を表示する実装です。外部プラグインの起動操作はありません。
4. `56`、`2*(30+5)`、`1in+5mm` などを入力し、Enterで確定、Escで取り消します。単位を省略した値はmmです。
5. 横寸法は左辺を固定して右辺を、縦寸法は上辺を固定して下辺を移動します。他の整列・直交寸法も、四隅に合っている端点を更新します。四隅以外にある端点はその位置を保ちます。

通常の寸法プロパティ（E）にも「この寸法値で基板外形を変更（mm）」を追加します。数字以外の寸法線・ハンドルは標準の選択・編集操作に使えます。

## 円の半径・直径を変更する

1. `Edge.Cuts`に円を1個描きます。
2. 半径を編集する場合は、標準の半径寸法（Draw Radial Dimensions）で「円の中心→円周上の点」を指定します。2点目で寸法が確定します。Escでツールを終了し、文字位置は必要に応じて標準のハンドル操作で調整します。
3. 直径を編集する場合は、標準の整列寸法で円周上の向かい合う2点を指定します。上下・左右の端点には直交寸法も使えます。中心を通らない弦の寸法では円を変更しません。
4. 配置を終えて数字をクリックすると、「半径」または「直径」と明示した入力欄を開きます。数値・計算式を入力してEnterで確定します。
5. 円の中心を保ったままサイズを変更し、関連する半径・直径寸法も更新します。直径に`56`を入力した場合の半径は28 mmです。

### 点に吸着しない場合

`User.Drawings`上の寸法を`Edge.Cuts`の角・円中心・円周へ合わせるには、KiCadのオブジェクト吸着を「表示中の全レイヤー」にします。現在のレイヤー限定になっている場合は、キャンバス上で`Shift+S`を押して切り替えます。設定はKiCad側で保持されます。クリックするときにShiftを押したままにすると吸着を一時無効にするため、キーを離して指定してください。

## 対象と制約

- 入力できる長さは0.01～1000 mm、変更前の外形の幅・高さは0.01～2000 mm、座標は±2000 mm以内です。
- 追従する寸法の端点間距離も2000 mm以内に制限し、範囲外の場合は何も変更しません。
- 円弧、斜めの外形、穴、複数輪郭、開いた線分には対応しません。
- 寸法と外形の関連は、端点が長方形の角、または円の中心・円周に一致するかで毎回判定します。許容差は最大0.01 mmで、小さな外形では縮小します。永続的な拘束ソルバーではありません。
- 外形の端点を別の操作で動かした場合、寸法端点を自動追従させる機能はありません。寸法端点を角に合わせ直してから寸法値を編集します。
- 部品、パッド、配線、ゾーンを移動・変形する機能はありません。
- ロックされた外形や、変更で動くロック寸法がある場合は変更を拒否します。
- 外形と寸法を同じ `BOARD_COMMIT` に登録します。長方形と円のUndo/Redoを実画面で確認済みです。

## ソースへの適用

対象は公式KiCadのタグ `10.0.7`、コミット `69cafb907ebc09e7722a2a464b1d466fc2e3608d` です。

```powershell
git clone --depth 1 --branch 10.0.7 https://github.com/KiCad/kicad-source-mirror.git C:\dev\kicad
python native/native_patch/apply_native_patch.py C:\dev\kicad --with-tests --dry-run
python native/native_patch/apply_native_patch.py C:\dev\kicad --with-tests
```

既存ファイルには `.smartboard-original` を付けてバックアップします。挿入位置の不一致、二重適用、既存バックアップがあれば停止します。`--dry-run` はファイルを書き換えません。コンパイル済みのKiCadへこのスクリプトを実行しても機能は追加されません。

ビルドは[KiCad公式Windows MSVC手順](https://dev-docs.kicad.org/en/build/windows-msvc/)に従います。今回の環境はVS 2022、MSVC 14.44.35207、CMake 3.31.10、PowerShell 7.5.4、SWIG 4.3.1、vcpkg `66c0373dc7fca549e5803087b9487edfe3aca0a1` です。QAテストを有効にしてビルドしてください。公式インストール先への上書きは行わず、別のビルドディレクトリで検証しています。

公式の手順で依存ライブラリとMSVC用プリセットを設定後、Developer PowerShellから次を実行します。`VCPKG_ROOT`、SWIG、Visual Studioの場所は自分の環境に合わせてください。

```powershell
cd C:\dev\kicad
cmake --preset msvc-win64-release -DKICAD_BUILD_QA_TESTS=ON
cmake --build --preset win64-release --target pcbnew qa_pcbnew bitmap_archive_build --parallel 4
$env:BOOST_TEST_RUN_FILTERS = 'SmartBoardDrivingDimensions,SmartBoardDrivingCircles,BoardCommit'
ctest --preset win64-release -R '^qa_pcbnew$' --output-on-failure
```

配布ZIPを展開したフォルダーで、同梱の起動スクリプトを使えます。ビルドのDLL/Pythonを読み込み、通常のKiCadと別の設定フォルダーを使います。インストール済みKiCadの実行ファイルは置き換えません。

```powershell
.\native\launch_windows.ps1 -BuildDirectory C:\dev\kicad\build\msvc-win64-release -Board .\native\examples\circle.kicad_pcb
```

サンプルは中心(100.3, 100.4) mm、半径28 mm、直径56 mmです。コピーして試してください。テスト実行ファイルを直接起動する場合も、ビルド用DLLの検索パスが必要です。通常は上記のCTestプリセットを使ってください。

## テスト

```powershell
python -m unittest discover -s native/tests -v
# KiCadのQAビルド後：
qa_pcbnew.exe --run_test=SmartBoardDrivingDimensions,SmartBoardDrivingCircles --log_level=test_suite
```

- Pythonのパッチ生成テスト：6件成功（適用失敗時の復元を含む）。
- クリーンな10.0.7から生成した8ファイルをビルド対象へ反映。
- C++回帰テスト8件成功：数式、形状と寸法の更新、片側だけ接続した寸法の追従、非接続寸法、ロック、逆順端点、座標上限、4線分の接続。既存のBoardCommitテスト8件も成功。
- WindowsでビルドしたPCBエディタの起動と、テスト基板・寸法の表示を確認。
- 長方形の画面操作：50 mmをクリック→`2*(30+5)`で70 mm、Undoで50 mm、Redoで70 mm。高さ30→23 mm、`1/0`の拒否、Esc取消、保存後の実API読込、エディタ再起動後70→56 mmの再編集を確認。
- 円の回帰テスト9件成功：半径・直径、中心固定、斜めの半径、寸法追従、弦・非接続・ロックの拒否、座標上限、関連寸法の長さ上限、複数外形の拒否。長方形8件と既存BoardCommit8件を合わせて25件成功（2026-10-27）。
- 円の画面操作：半径20→`2*15`で30 mm、直径40→60 mmへの追従、Undo/Redoを確認。直径60の文字と円周が重なっていても入力でき、`2*28`で直径56・半径28 mmへ変更。保存後に実APIで中心(100.3, 100.4)と端点の一致を確認。
- 円を再起動後に編集し、半径28→30 mmへ変更。`1/0`を拒否し、Escで取り消せることと、確定・取消直後も1クリックで入力を再表示できることを確認。
- 1 mmグリッド上で、グリッドから外れた中心(100.3, 100.4)と円周(120.3, 100.4)に吸着して半径寸法を新規配置。数字から半径25 mmへ変更・保存し、円と寸法が中心(100.3, 100.4)／端点(125.3, 100.4)で一致することを実APIで確認。
- 最終ビルドで25→24 mmを確定後、キャンバスをクリックし直さずにCtrl+Zで25、Ctrl+Yで24、Ctrl+Sで保存できることを確認。保存データも中心を保ち、円と寸法の端点が(124.3, 100.4)で一致。
- 未検証：他OS・他KiCad版、部品や配線を含む実基板での運用、インストーラーによる導入。コンパイル済みアプリの一般配布は今後の対象です。

## 来歴とライセンス

提供された `KiCad10_NativeDrivingDimension_Prototype.zip` を元に、10.0.7のAPIへの修正、数字クリックからの編集、数式評価、変更前の検証、テストを追加しました。受領時の説明は [README_PROTOTYPE_JA.md](README_PROTOTYPE_JA.md) に記録しています。現在の動作・検証状況は本書を参照してください。

操作感は [SolidCraft](https://github.com/tangency-labs/solidcraft) を参考にした独自実装です。コード・画像・拘束ソルバーは取り込んでいません。SolidCraftの公式・提携・推奨製品ではありません。詳しくは [参考元・ライセンス](https://github.com/conmmitmentman/KiCad-SmartBoardDimension/blob/main/ATTRIBUTION.md) を参照してください。

C++追加コードはGPL-3.0-or-later（[全文](LICENSE_GPLv3.txt)）。KiCad本体のライセンスは元のソースに従います。パッチ生成用Pythonの元のライセンスは [LICENSE_PYTHON.txt](LICENSE_PYTHON.txt) に収録しています。
