# 開発者向けガイド

## 仕組み

`smart_board_dimension/__init__.py` が `pcbnew.ActionPlugin` を登録します。ダイアログは `wx` を使用し、`Edge.Cuts` の長方形外形のみを編集します。 `direct_editor.py` がPCB上の寸法・クリック入力・Action Plugin経由の確定を担当します。寸法の識別はUUIDに保持します。`canvas.py` が補助ダイアログの図上入力・ドラッグ・固定点選択を担当します。`geometry.py` はKiCad依存を持たず、式解析、単位換算、矩形判定、基準点座標計算を担当します。

プラグインはKiCad 10のSWIG Pythonバインディングを利用します。公式はSWIG廃止とIPC APIへの移行を案内しています。KiCad 11対応は別作業です。

## 開発環境

- Python 3.10以上（単体テスト用。実行プラグインはKiCad付属Pythonが必要）
- 標準ライブラリ以外のPython依存はなし
- KiCad GUI実機検証には KiCad 10 / `wx` / `pcbnew` が必要

## テスト

```bash
python -m unittest discover -s tests -v
python -m compileall -q smart_board_dimension tests tools
python tools/build_release.py
```

WindowsでKiCadの実APIを検証するには、モックテストとは別プロセスで実行します。

```powershell
& 'C:\Program Files\KiCad\10.0\bin\python.exe' tools\check_kicad.py
```

この検証では登録処理と画面再描画のみを抑止し、実物のBOARD/PCB_SHAPEとwx.Dialogを使います。作成・変更・保存・再読込、4線外形と基準点、ダイアログ寸法と数式・上限入力を検査します。結果は[実機検証記録](VALIDATION_JA.md)を参照してください。

- `test_geometry.py`：式・単位・4線長方形・基準点を確認
- `test_plugin_mock.py`：偽の`pcbnew`/`wx`により図形生成・編集・非対応外形を確認
- `test_release_package.py`：配布ZIPに必須のファイルが入っているか確認

### モックテストにないもの

モックだけでは実際の表示、操作イベント、SWIG固有の型変換、Undo、配線・ゾーン・DRCを検証できません。実APIテストとPCBエディター上の確認を併用してください。今回の確認範囲は検証記録にまとめています。

## KiCad実機の確認項目

- [ ] KiCad 10.x / Windowsでメニューが表示される
- [ ] 外形ゼロ個：長方形を新規作成できる
- [ ] 単一長方形：左上固定で幅・高さを変更できる
- [ ] 4線長方形：線分向きに依存せず正しく変更できる
- [ ] 中心固定・右下固定の座標が正しい
- [ ] 単位・式入力と日本語エラーメッセージが正常
- [ ] 非対応外形で変更されない
- [ ] 変更後のファイル保存・再読込・DRCが行える
- [ ] v1.1.0からv1.2.0へバッチ更新できる
- [ ] v1.2.0からv1.3.0へKiCadダイアログ上のボタンで更新できる（GitHubにテストReleaseを公開した場合）
- [ ] ロールバックして以前の動作に戻る
- [ ] Windows再起動後もインストールが残る

## 機能追加の流れ

1. `geometry.py` へテスト可能な形で幾何計算を追加
2. `test_geometry.py` / `test_plugin_mock.py` にテスト追加
3. `__init__.py` に新しいUIや編集処理を追加
4. `PLUGIN_VERSION` と `CHANGELOG.md` を更新
5. `.ps1` のコピー対象ファイルが増えた場合は `$files` を更新
6. README / 使用方法 / 制限事項を修正し、リリース生成

## バージョン方針

- `MAJOR`：後方互換性のない変更
- `MINOR`：機能追加
- `PATCH`：互換性のある修正

v1.1.0でオフライン更新・復元を追加し、v1.2.0でオンライン更新を追加しました。外形編集アルゴリズム自体はほぼ同じです。

[READMEへ戻る](../README.md)

## ネイティブ版の開発

外部プラグインの起動操作を不要にするKiCad本体のC++パッチは `native/` で管理します。対応ソース、適用方法、ビルド条件と検証状況は [native/README.md](../native/README.md) を参照してください。Python版の配布・更新とは別です。
