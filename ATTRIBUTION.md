# 参考元・ライセンス

## SolidCraftの操作感を参考にした独自実装

本プロジェクトは [SolidCraft](https://github.com/tangency-labs/solidcraft) のスケッチ寸法編集の操作感を参考にしています。具体的には、図形の近くで寸法値を編集し、数値・単位・計算式を入力してEnterで確定、Escで取り消す操作です。円の半径・直径の編集も、この操作方針に沿ってKiCad用に独自実装しています。

SolidCraftのソースコード、画像、アイコン、ロゴ、フォント、拘束ソルバーは本プロジェクトへ取り込んでいません。SolidCraftおよびその開発者による公式製品・提携製品・推奨製品ではありません。名称は参考元を説明するために使用しています。

参照した公開仕様：

- [スケッチ・寸法操作の説明](https://github.com/tangency-labs/solidcraft/blob/main/docs/book/src/guide/sketching.md)
- [SolidCraft READMEのライセンス説明](https://github.com/tangency-labs/solidcraft#licence)
- [MITライセンス](https://github.com/tangency-labs/solidcraft/blob/main/LICENSE-MIT)
- [Apache-2.0ライセンス](https://github.com/tangency-labs/solidcraft/blob/main/LICENSE-APACHE)
- [第三者素材・名称の説明](https://github.com/tangency-labs/solidcraft/blob/main/NOTICE)

2026-10-26確認時、SolidCraftはMIT OR Apache-2.0の選択ライセンスです。今後コードを取り込む場合は、選択したライセンスの条件（MITなら著作権表示と許諾表示の保持など）と、対象ファイル固有の条件を確認し、その時点で実際の利用箇所と必要な表示を追記します。参考元の記載は、必要な許諾やライセンス条件の代わりにはなりません。

## 本プロジェクトの構成

- Pythonプラグイン：ルートの [LICENSE](LICENSE)。
- KiCad本体へ追加するC++コード：GPL-3.0-or-later。[ライセンス全文](native/LICENSE_GPLv3.txt)。
- 受領した試作パッチのPython部分：[元のMITライセンス](native/LICENSE_PYTHON.txt)。
- KiCad本体：公式ソース内のライセンス・著作権表示を保持してください。

この文書は実装の来歴と運用方針の説明で、特定の法域についての法的保証ではありません。
