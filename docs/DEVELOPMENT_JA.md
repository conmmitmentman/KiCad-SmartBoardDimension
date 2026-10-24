# 開発者向けガイド

## 仕組み

`smart_board_dimension/__init__.py` が `pcbnew.ActionPlugin` を登録します。ダイアログは `wx` を使用し、`Edge.Cuts` の長方形外形のみを編集します。 `geometry.py` はKiCad依存を持たず、式解析、単位換算、矩形判定、基準点座標計算を担当します。

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

- `test_geometry.py`：式・単位・4線長方形・基準点を確認
- `test_plugin_mock.py`：偽の`pcbnew`/`wx`により図形生成・編集・非対応外形を確認
- `test_release_package.py`：配布ZIPに必須のファイルが入っているか確認

### モックテストにないもの

`wx.Dialog`の実際の表示、操作イベント、KiCadのPCBオブジェクトの実状態、SWIG固有の型変換、Undo動作、配線・ゾーン・DRC、Windows PowerShell実行自体はこの環境ではテストしていません。GUI実機検証は別途必要です。

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
