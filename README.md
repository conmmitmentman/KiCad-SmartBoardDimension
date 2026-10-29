# スマート基板寸法 — ネイティブ版

本プロジェクトの主製品は、PCB上の寸法の数字から直接編集できるネイティブ版です。毎回プラグインを起動する操作は不要です。KiCad 10.0.7を基にした独立したPCBエディタで、KiCad公式製品ではありません。

## できること

- 長方形の幅・高さ、円の半径・直径を数字クリックから変更
- 数値・計算式・単位の入力、Enterで確定、Escで取消
- 中心・円周・角への標準スナップ、Undo/Redo

## 導入状況

現在公開中の[Source v1.0.0](https://github.com/conmmitmentman/KiCad-SmartBoardDimension/releases/tag/native-source-v1.0.0)はソース版です。ZIPを入れるだけでは使えません。

**一般ユーザー向けWindowsインストーラーは準備中です。** コマンド入力やビルドを不要にし、日本語の起動画面、必要な実行環境の同梱、専用デスクトップアイコンを提供する方針です。まだ公開済みのインストーラーはありません。

[導入と開発状況](native/INSTALL_JA.md) / [操作・対応範囲・検証記録](native/README.md)

## 従来版について

[Pythonプラグイン版](docs/PYTHON_PLUGIN_JA.md)は従来方式として残します。Python版のインストーラーでは、円対応を含むネイティブ機能は入りません。GitHubのLatestは互換性のため当面Python版を指します。

操作感はSolidCraftを参考にした独自実装です。[参考元・ライセンス](ATTRIBUTION.md)を参照してください。
