# スマート基板寸法 — ネイティブ版

KiCad 10.0.7を基に、PCB上の寸法の数字から基板外形を直接編集できるようにした非公式のPCBエディタです。このリポジトリではネイティブ版のみを提供します。

- 長方形の幅・高さ、円の半径・直径を数値・計算式で編集
- 数字をクリックして入力、Enterで確定、Escで取消
- 円の中心固定、接続する寸法の追従、Undo/Redo
- 日本語のWindows導入・起動画面

## ダウンロードと導入

[ネイティブ Source v1.0.0](https://github.com/conmmitmentman/KiCad-SmartBoardDimension/releases/tag/native-source-v1.0.0) はソース配布です。コンパイル済みアプリや一般向けWindowsインストーラーはまだ公開していません。

[導入状況](native/INSTALL_JA.md) / [操作・対応範囲・ビルド・検証記録](native/README.md)

`native/` に実装・サンプル・テスト・Windowsランチャー、`tools/` にネイティブ版の配布生成処理を収録しています。Pythonで書かれたパッチ適用・配布生成ツールもネイティブ版に必要なため含みます。

## ライセンス

C++追加コードは [GPL-3.0-or-later](native/LICENSE_GPLv3.txt)。Windowsランチャー等は各ファイルの表示と [LICENSE](LICENSE) に従います。操作感はSolidCraftを参考にした独自実装です。[来歴・参考元](ATTRIBUTION.md)。
